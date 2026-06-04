"""
Clean raw PDF text before chunking:
  - Rejoin soft-hyphenated words split across lines
  - Collapse excessive whitespace
  - Drop lines that are pure noise (page numbers, header/footer artifacts)
"""

import re


# Lines that are just a number (page numbers) or very short noise
_NOISE_LINE = re.compile(r"^\s*(\d{1,4}|[-–—|]{1,5})\s*$")


def _drop_noise_lines(text: str) -> str:
    lines = [l for l in text.splitlines() if not _NOISE_LINE.match(l)]
    return "\n".join(lines)


def _fix_hyphenation(text: str) -> str:
    # "bene-\nfit" → "benefit"
    return re.sub(r"-\n(\w)", lambda m: m.group(1), text)


def _normalize_whitespace(text: str) -> str:
    # Collapse runs of spaces/tabs; preserve single newlines as sentence breaks
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse 3+ newlines to 2 (paragraph break)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean(raw_text: str) -> str:
    text = _drop_noise_lines(raw_text)
    text = _fix_hyphenation(text)
    text = _normalize_whitespace(text)
    return text


def clean_pages(pages: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Apply clean() to each (page_num, raw_text) pair."""
    return [(page_num, clean(text)) for page_num, text in pages if clean(text)]
