"""
Hierarchical chunking — two levels:

  Parent chunk (~1200 chars, overlapping)
    └── Child chunks (~300 chars, overlapping)

The vector DB stores *child* chunks (precise retrieval).
Each child carries a `parent_id` and the full parent text so the LLM
receives rich context at generation time.

Chunk schema:
  {
    "child_id":    "<plan_id>_p<page>_par<par_idx>_ch<ch_idx>",
    "parent_id":   "<plan_id>_p<page>_par<par_idx>",
    "child_text":  str,   ← embedded & stored in vector DB
    "parent_text": str,   ← returned to LLM as context
    "page_num":    int,
    "par_idx":     int,
    "ch_idx":      int,
  }
"""

import re

PARENT_SIZE    = 1200
PARENT_OVERLAP = 200
CHILD_SIZE     = 300
CHILD_OVERLAP  = 50


def _split(text: str, size: int, overlap: int) -> list[str]:
    """Split text into overlapping character windows."""
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start : start + size])
        start += size - overlap
    return chunks


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def build_chunks(pages: list[tuple[int, str]], plan_id: str) -> list[dict]:
    """
    pages: list of (page_num, cleaned_text)
    Returns flat list of child-chunk dicts.
    """
    all_chunks = []

    for page_num, text in pages:
        text = _normalize(text)
        if not text:
            continue

        parents = _split(text, PARENT_SIZE, PARENT_OVERLAP)

        for par_idx, parent_text in enumerate(parents):
            parent_id = f"{plan_id}_p{page_num}_par{par_idx}"
            children = _split(parent_text, CHILD_SIZE, CHILD_OVERLAP)

            for ch_idx, child_text in enumerate(children):
                if not child_text.strip():
                    continue
                all_chunks.append({
                    "child_id":    f"{parent_id}_ch{ch_idx}",
                    "parent_id":   parent_id,
                    "child_text":  child_text,
                    "parent_text": parent_text,
                    "page_num":    page_num,
                    "par_idx":     par_idx,
                    "ch_idx":      ch_idx,
                })

    return all_chunks
