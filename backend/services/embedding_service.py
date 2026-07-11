"""
services/embedding_service.py — Local embedding service wrapper.
Zero IBM quota cost. 384-dim vectors from all-MiniLM-L6-v2.
Uses ChromaDB's DefaultEmbeddingFunction (ONNX C++ engine) to keep peak RAM well under 512MB on cloud containers.
"""

from typing import Optional, Any
import gc
from backend.utils.logger import get_logger

log = get_logger(__name__)

# Limit PyTorch CPU threads just in case fallback is triggered
try:
    import torch
    torch.set_num_threads(1)
except Exception as exc:
    log.debug("Could not set torch thread count: %s", exc)

_embed_fn: Optional[Any] = None
_model: Optional[Any] = None


def get_embedding_engine() -> Any:
    global _embed_fn, _model
    if _embed_fn is None and _model is None:
        try:
            log.info("Loading ONNX C++ embedding engine (DefaultEmbeddingFunction)...")
            from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
            _embed_fn = DefaultEmbeddingFunction()
            log.info("ONNX C++ embedding engine ready.")
            return _embed_fn
        except Exception as exc:
            log.warning("ONNX embedding engine failed (%s), falling back to SentenceTransformer...", exc)
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("all-MiniLM-L6-v2")
            log.info("SentenceTransformer embedding model ready.")
            return _model
    return _embed_fn if _embed_fn is not None else _model


def unload_embedding_engine() -> None:
    """
    Explicitly destroy the ONNX / SentenceTransformer model singleton and
    force garbage collection.  Call this immediately after document ingestion
    completes to free 150-200 MB of RAM on Render's 512 MB free-tier container.
    """
    global _embed_fn, _model
    if _embed_fn is not None:
        log.info("Unloading ONNX embedding engine to free RAM...")
        del _embed_fn
        _embed_fn = None
    if _model is not None:
        log.info("Unloading SentenceTransformer model to free RAM...")
        del _model
        _model = None
    gc.collect()
    log.info("Embedding engine unloaded. RAM freed.")


def embed_texts(texts: list[str], progress_callback: Optional[Any] = None) -> list[list[float]]:
    engine = get_embedding_engine()
    log.debug("Starting encoding of %d texts...", len(texts))
    
    batch_size = 16
    all_embeddings = []
    total = len(texts)
    
    if _embed_fn is not None:
        for i in range(0, total, batch_size):
            batch = texts[i:i + batch_size]
            batch_emb = _embed_fn(batch)
            if hasattr(batch_emb, "tolist"):
                batch_emb = batch_emb.tolist()
            all_embeddings.extend([list(map(float, vec)) for vec in batch_emb])
            del batch_emb
            if progress_callback and total > 0:
                progress_callback(min(1.0, (i + len(batch)) / total))
        gc.collect()
        return all_embeddings
    else:
        for i in range(0, total, batch_size):
            batch = texts[i:i + batch_size]
            batch_emb = engine.encode(
                batch,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            all_embeddings.extend(batch_emb.tolist())
            del batch_emb
            if progress_callback and total > 0:
                progress_callback(min(1.0, (i + len(batch)) / total))
        gc.collect()
        return all_embeddings


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
