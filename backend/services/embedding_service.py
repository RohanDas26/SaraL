"""
services/embedding_service.py — Local sentence-transformers wrapper.
Zero IBM quota cost. 384-dim vectors from all-MiniLM-L6-v2.
"""

from typing import Optional
from sentence_transformers import SentenceTransformer
from backend.utils.logger import get_logger

log = get_logger(__name__)

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
    embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
