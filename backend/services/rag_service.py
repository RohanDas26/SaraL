"""
services/rag_service.py — Retrieval-Augmented Generation core.

Reuses the singleton ChromaDB client from document_service to avoid
opening multiple handles to the same persistent database.
"""

from typing import Optional

from backend.config import Config
from backend.utils.logger import get_logger
# Lazy import — avoid loading torch/sentence-transformers at startup
def _embed_query(text):
    from backend.services.embedding_service import embed_query
    return embed_query(text)

log = get_logger(__name__)


def _get_collection():
    """Reuse the singleton client managed by document_service."""
    from backend.services.document_service import _get_chroma_client
    client = _get_chroma_client()
    return client.get_or_create_collection(
        name="saral_documents",
        metadata={"hnsw:space": "cosine"},
    )


def retrieve_context(
    question: str,
    doc_ids: Optional[list] = None,
    top_k: Optional[int] = None,
) -> tuple[str, list[dict]]:
    """
    Embed the question, search ChromaDB, return (context_string, sources).
    Returns ("", []) when no relevant chunks are found.
    """
    top_k = top_k or Config.RAG_TOP_K

    collection = _get_collection()
    total = collection.count()
    if total == 0:
        return "", []

    # Build where-filter for doc scoping
    where_filter = None
    if doc_ids:
        ids_as_str = [str(d) for d in doc_ids]
        if len(ids_as_str) == 1:
            where_filter = {"doc_id": ids_as_str[0]}
        else:
            where_filter = {"$or": [{"doc_id": s} for s in ids_as_str]}

    query_embedding = _embed_query(question)

    kwargs: dict = {
        "query_embeddings": [query_embedding],
        "n_results":        min(top_k, total),
        "include":          ["documents", "metadatas", "distances"],
    }
    if where_filter:
        kwargs["where"] = where_filter

    results = collection.query(**kwargs)

    if not results["documents"] or not results["documents"][0]:
        return "", []

    chunks    = results["documents"][0]
    metadatas = results["metadatas"][0]

    context_parts = []
    for i, (chunk, meta) in enumerate(zip(chunks, metadatas), start=1):
        context_parts.append(
            f"[Source {i}: {meta.get('doc_name', 'Unknown')}, "
            f"page {meta.get('page_num', '?')}]\n{chunk}"
        )
    context_string = "\n\n---\n\n".join(context_parts)

    sources = [
        {
            "doc_name": meta.get("doc_name", "Unknown"),
            "page_num":  meta.get("page_num", "?"),
        }
        for meta in metadatas
    ]

    log.debug("RAG retrieved %d chunks for query: '%s...'", len(chunks), question[:40])
    return context_string, sources


def has_indexed_documents() -> bool:
    """Return True if at least one chunk exists in ChromaDB."""
    try:
        return _get_collection().count() > 0
    except Exception:
        return False
