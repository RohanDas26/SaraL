"""
services/embedding_service.py — Local sentence-transformers wrapper.
Zero IBM quota cost. 384-dim vectors from all-MiniLM-L6-v2.
Optimized with low PyTorch thread count and small batches for 512MB RAM free containers.
"""

from typing import Optional
import gc
from sentence_transformers import SentenceTransformer
from backend.utils.logger import get_logger

log = get_logger(__name__)

# Limit PyTorch CPU threads so it doesn't allocate massive memory buffers or spike vCPU on 512MB containers
try:
    import torch
    torch.set_num_threads(1)
except Exception as exc:
    log.debug("Could not set torch thread count: %s", exc)

_MODEL_NAME = "all-MiniLM-L6-v2"
_model: Optional[SentenceTransformer] = None


def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        log.info("Loading embedding model %s ...", _MODEL_NAME)
        _model = SentenceTransformer(_MODEL_NAME)
        log.info("Embedding model ready.")
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    log.debug("Starting encoding of %d texts with batch_size=16...", len(texts))
    # batch_size=16 keeps peak RAM allocation well under 512MB limits on cloud containers
    embeddings = model.encode(
        texts,
        batch_size=16,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    gc.collect()
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
