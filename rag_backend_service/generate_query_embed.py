"""
Embed a user question using the same model used at ingestion time.
Returns a list[float] embedding vector.
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sentence_transformers import SentenceTransformer
from config import EMBED_MODEL

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def embed_query(question: str) -> list[float]:
    model = _get_model()
    return model.encode(question, normalize_embeddings=True).tolist()
