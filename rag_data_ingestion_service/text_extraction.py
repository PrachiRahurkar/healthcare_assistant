"""
Extract raw text from a PDF, returning a list of (page_num, raw_text) tuples.
"""

import pdfplumber


def extract_pages(pdf_path: str) -> list[tuple[int, str]]:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text and text.strip():
                pages.append((i, text))
    return pages
