# src/rag/chunker.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class TextChunk:
    id: str
    url: str
    index: int
    text: str


def chunk_text(text: str, url: str, chunk_size: int = 1200, overlap: int = 150) -> List[TextChunk]:
    """
    Simple character-based chunking with overlap.
    """
    text = (text or "").strip()
    if not text:
        return []

    chunks: List[TextChunk] = []
    start = 0
    idx = 0

    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunk = text[start:end].strip()
        if chunk:
            cid = f"{abs(hash(url))}_{idx}"
            chunks.append(TextChunk(id=cid, url=url, index=idx, text=chunk))
            idx += 1

        if end >= len(text):
            break

        start = max(0, end - overlap)

    return chunks
