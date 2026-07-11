"""
services/document_service.py — Document ingestion pipeline.

Flow (per document):
  1. (Route layer) Validate file → compute hash → check dedup → save bytes to disk
  2. SQLite record created with status='pending'
  3. Background thread calls process_document(doc_id)
  4. process_document: extract → clean → chunk → embed → store in ChromaDB
  5. SQLite updated: status='indexed', chunk_count, page_count, progress_pct=100

Async strategy:
  - Python threading.Thread is used (not multiprocessing or Celery).
  - Appropriate for 1–5 concurrent users and local deployment.
  - The frontend polls GET /api/documents/<id>/status for live progress.

No IBM watsonx API calls.  No network requests.  100% local.
"""

import os
import threading
from typing import Optional

import chromadb
from chromadb.config import Settings

from backend.config import Config
from backend.database import get_db
from backend.utils.logger import get_logger
from backend.utils.text_utils import extract_text, clean_text, chunk_text
# Lazy import — avoid loading torch/sentence-transformers at startup
def _embed(texts):
    from backend.services.embedding_service import embed_texts
    return embed_texts(texts)

log = get_logger(__name__)

# ── ChromaDB client ────────────────────────────────────────────────────
# A single client per process; ChromaDB is thread-safe for reads/writes.
_chroma_lock = threading.Lock()
_chroma_client: Optional[chromadb.PersistentClient] = None


def _get_chroma_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        with _chroma_lock:
            if _chroma_client is None:
                os.makedirs(Config.CHROMA_PATH, exist_ok=True)
                _chroma_client = chromadb.PersistentClient(
                    path=Config.CHROMA_PATH,
                    settings=Settings(anonymized_telemetry=False),
                )
                log.info("ChromaDB initialised at %s", Config.CHROMA_PATH)
    return _chroma_client


def _get_collection(client: chromadb.PersistentClient):
    """Get or create the single shared collection."""
    return client.get_or_create_collection(
        name="saral_documents",
        metadata={"hnsw:space": "cosine"},
    )


# ══════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════

def start_processing(doc_id: int) -> None:
    """
    Launch document processing in a background thread.
    Returns immediately; the caller should poll /status.
    """
    thread = threading.Thread(
        target=_safe_process,
        args=(doc_id,),
        daemon=True,
        name=f"doc-ingestion-{doc_id}",
    )
    thread.start()
    log.info("Started background ingestion thread for document %d", doc_id)


def process_document(doc_id: int) -> None:
    """
    Full synchronous ingestion pipeline.
    Call this directly in tests; use start_processing() in the web context.
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()

        if not row:
            raise ValueError(f"Document {doc_id} not found in database.")

        log.info(
            "Ingestion started: doc_id=%d name='%s' type=%s size=%d KB",
            doc_id, row["display_name"], row["file_type"], row["file_size_kb"],
        )

        # ── Step 1: mark as processing ─────────────────────────────────
        _update_status(conn, doc_id, "processing", progress=5)

        # ── Step 2: extract text ───────────────────────────────────────
        log.debug("Extracting text from %s", row["file_path"])
        full_text, page_count, page_map = extract_text(
            row["file_path"], row["file_type"]
        )
        _update_status(conn, doc_id, "processing", progress=30)

        # ── Step 3: clean ──────────────────────────────────────────────
        full_text = clean_text(full_text)

        if not full_text.strip():
            raise ValueError(
                "No readable text could be extracted from this document. "
                "It may be a scanned image PDF, password-protected, or corrupt."
            )

        log.debug("Cleaned text: %d characters", len(full_text))
        _update_status(conn, doc_id, "processing", progress=45)

        # ── Step 4: chunk ──────────────────────────────────────────────
        chunks = chunk_text(full_text)

        if not chunks:
            raise ValueError(
                "The document produced no usable text chunks after cleaning. "
                "It may contain only images or formatting."
            )

        # Hard cap: prevent OOM on 512MB free-tier containers
        if len(chunks) > Config.MAX_CHUNKS:
            log.warning(
                "Document produced %d chunks — capping to %d to prevent OOM on cloud container",
                len(chunks), Config.MAX_CHUNKS,
            )
            chunks = chunks[:Config.MAX_CHUNKS]

        log.info("Chunked into %d chunks", len(chunks))
        _update_status(conn, doc_id, "processing", progress=55)


        # ── Step 5: embed (local, no API cost) ────────────────────────
        log.debug("Embedding %d chunks with sentence-transformers...", len(chunks))
        import gc
        gc.collect()  # Free PyMuPDF memory before embedding starts
        from backend.services.embedding_service import embed_texts, unload_embedding_engine
        embeddings = embed_texts(chunks)
        # Immediately unload ONNX from RAM — frees 150-200MB on 512MB container
        unload_embedding_engine()
        gc.collect()
        _update_status(conn, doc_id, "processing", progress=80)


        # ── Step 6: store in ChromaDB ──────────────────────────────────
        log.debug("Storing vectors in ChromaDB...")
        client     = _get_chroma_client()
        collection = _get_collection(client)

        # Build chunk character offsets so we can map to page numbers
        # We track cumulative position through the original text
        chunk_ids       = []
        chunk_metadatas = []
        char_offset     = 0

        for i, chunk in enumerate(chunks):
            # Estimate which page this chunk came from
            page_num = _estimate_page(char_offset, page_map)

            chunk_ids.append(f"doc{doc_id}_chunk{i}")
            chunk_metadatas.append({
                "doc_id":      str(doc_id),
                "doc_name":    row["display_name"],
                "chunk_index": str(i),
                "page_num":    str(page_num),
            })
            char_offset += len(chunk)

        # Delete any existing vectors for this doc (re-upload scenario)
        _delete_doc_vectors(collection, doc_id)

        # Batch ChromaDB add() in slices of 10 to prevent memory spikes or SQLite locks on 512MB free tier
        batch_size = 10
        for i in range(0, len(chunks), batch_size):
            collection.add(
                ids=chunk_ids[i:i + batch_size],
                embeddings=embeddings[i:i + batch_size],
                documents=chunks[i:i + batch_size],
                metadatas=chunk_metadatas[i:i + batch_size],
            )
            import gc; gc.collect()
        log.debug("Stored %d vectors in ChromaDB", len(chunks))
        _update_status(conn, doc_id, "processing", progress=95)

        # ── Step 7: finalise SQLite ────────────────────────────────────
        conn.execute(
            """UPDATE documents
               SET status='indexed',
                   chunk_count=?,
                   page_count=?,
                   progress_pct=100,
                   error_message=NULL,
                   updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (len(chunks), page_count, doc_id),
        )
        conn.commit()

        log.info(
            "Ingestion complete: doc_id=%d chunks=%d pages=%d",
            doc_id, len(chunks), page_count,
        )

    except Exception as exc:
        log.error("Ingestion failed for doc_id=%d: %s", doc_id, exc, exc_info=True)
        _update_status(conn, doc_id, "failed", error_message=str(exc), progress=0)
        conn.commit()
        raise

    finally:
        conn.close()


def delete_document(doc_id: int) -> None:
    """
    Remove a document from ChromaDB, disk, and SQLite.
    Also invalidates in-memory response cache entries.
    """
    from backend.services.cache_service import invalidate_doc

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        if not row:
            log.warning("delete_document called for non-existent doc_id=%d", doc_id)
            return

        # Remove vectors
        client     = _get_chroma_client()
        collection = _get_collection(client)
        _delete_doc_vectors(collection, doc_id)

        # Remove file from disk
        file_path = row["file_path"]
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            log.debug("Deleted file: %s", file_path)

        # Remove SQLite row
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()

        # Invalidate cache
        invalidate_doc(doc_id)

        log.info("Document %d deleted: '%s'", doc_id, row["display_name"])

    finally:
        conn.close()


def get_all_documents() -> list[dict]:
    """Return all documents ordered by most recently uploaded."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM documents ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_document(doc_id: int) -> Optional[dict]:
    """Return a single document dict, or None if not found."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════
# PRIVATE HELPERS
# ══════════════════════════════════════════════════════════════════════

def _safe_process(doc_id: int) -> None:
    """Wrapper so thread exceptions are logged and don't silently vanish."""
    try:
        process_document(doc_id)
    except Exception:
        pass   # already logged inside process_document


def _update_status(
    conn,
    doc_id: int,
    status: str,
    error_message: Optional[str] = None,
    progress: int = 0,
) -> None:
    """Update document status and optional progress percentage in SQLite."""
    conn.execute(
        """UPDATE documents
           SET status=?,
               error_message=?,
               progress_pct=?,
               updated_at=CURRENT_TIMESTAMP
           WHERE id=?""",
        (status, error_message, progress, doc_id),
    )
    conn.commit()


def _delete_doc_vectors(collection, doc_id: int) -> None:
    """Remove all ChromaDB vectors belonging to a document."""
    try:
        existing = collection.get(where={"doc_id": str(doc_id)})
        if existing and existing.get("ids"):
            collection.delete(ids=existing["ids"])
            log.debug("Deleted %d vectors for doc_id=%d", len(existing["ids"]), doc_id)
    except Exception as exc:
        # Non-fatal: log and continue (vectors may not exist yet)
        log.warning("Could not delete vectors for doc_id=%d: %s", doc_id, exc)


def _estimate_page(char_offset: int, page_map: list[tuple[int, int]]) -> int:
    """
    Walk the page_map to find which page a character offset belongs to.
    page_map is [(char_start, page_num), ...] sorted ascending.
    """
    if not page_map:
        return 1
    page_num = 1
    for char_start, pnum in page_map:
        if char_offset >= char_start:
            page_num = pnum
        else:
            break
    return page_num
