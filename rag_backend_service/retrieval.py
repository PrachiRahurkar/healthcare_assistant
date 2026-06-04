"""
Retrieve top-k child chunks from the plan's ChromaDB collection.
Returns the *parent* text for each hit (richer context for the LLM).
Cosine similarity is used (collection was created with hnsw:space=cosine).
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chromadb
from chromadb.utils import embedding_functions
from config import EMBED_MODEL

VECTOR_DIR = os.path.join(os.path.dirname(__file__), "..", "rag_data_ingestion_service", "data", "vectordb")

_client: chromadb.PersistentClient | None = None
_embed_fn = None


def _get_client():
    global _client, _embed_fn
    if _client is None:
        _client   = chromadb.PersistentClient(path=VECTOR_DIR)
        _embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    return _client, _embed_fn


def retrieve(plan_id: str, query_embedding: list[float], top_k: int = 5) -> list[dict]:
    """
    Returns list of dicts:
      { child_text, parent_text, page_num, distance }
    Raises ValueError if plan_id collection doesn't exist.
    """
    client, embed_fn = _get_client()

    try:
        col = client.get_collection(name=plan_id, embedding_function=embed_fn)
    except Exception:
        raise ValueError(f"No benefit booklet found for plan ID '{plan_id}'.")

    results = col.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "child_text":  doc,
            "parent_text": meta.get("parent_text", doc),
            "page_num":    meta.get("page_num", "?"),
            "distance":    dist,
        })

    return chunks
