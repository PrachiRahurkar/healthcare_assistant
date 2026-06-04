"""
Ingestion orchestrator:
  mapping file → extract → preprocess → chunk → embed (child chunks) → store in ChromaDB

Run:
  python ingest.py
"""

import os
import re
import chromadb
from chromadb.utils import embedding_functions

from text_extraction import extract_pages
from preprocessing import clean_pages
from chunking import build_chunks

BASE_DIR     = os.path.dirname(__file__)
MAPPING_FILE = os.path.join(BASE_DIR, "data", "mapping")
VECTOR_DIR   = os.path.join(BASE_DIR, "data", "vectordb")
EMBED_MODEL  = "all-MiniLM-L6-v2"
BATCH_SIZE   = 100


def parse_mapping(path: str) -> list[tuple[str, str]]:
    plans = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("Plan_ID") or line.startswith("---"):
                continue
            parts = re.split(r"\s*\|\s*", line)
            if len(parts) == 2:
                plan_id, rel_path = parts
                plans.append((plan_id.strip(), os.path.join(BASE_DIR, rel_path.strip())))
    return plans


def ingest_plan(client, embed_fn, plan_id: str, pdf_path: str):
    print(f"\n[{plan_id}] {os.path.basename(pdf_path)}")

    pages = extract_pages(pdf_path)
    print(f"  {len(pages)} pages extracted")

    pages = clean_pages(pages)
    print(f"  {len(pages)} pages after preprocessing")

    chunks = build_chunks(pages, plan_id)
    print(f"  {len(chunks)} child chunks created")

    col = client.get_or_create_collection(
        name=plan_id,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        col.upsert(
            ids=[c["child_id"] for c in batch],
            documents=[c["child_text"] for c in batch],
            metadatas=[{
                "parent_id":   c["parent_id"],
                "parent_text": c["parent_text"],
                "page_num":    c["page_num"],
            } for c in batch],
        )

    print(f"  Stored in collection '{plan_id}'")


def main():
    os.makedirs(VECTOR_DIR, exist_ok=True)
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    client   = chromadb.PersistentClient(path=VECTOR_DIR)

    plans = parse_mapping(MAPPING_FILE)
    print(f"Ingesting {len(plans)} benefit booklets...")

    for plan_id, pdf_path in plans:
        ingest_plan(client, embed_fn, plan_id, pdf_path)

    print("\nIngestion complete.")


if __name__ == "__main__":
    main()
