# src/rag/pipeline.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Union

from src.config.logging import logger
from src.rag.fetcher import fetch_url
from src.rag.cleaner import clean_html_to_text
from src.rag.chunker import TextChunk, chunk_text
from src.rag.retriever import retrieve_tfidf


@dataclass
class RAGContext:
    ok: bool
    url: str
    focus: str
    query: str
    context: str
    chunks: List[TextChunk]
    top_chunks: List[TextChunk]
    error: Optional[str] = None


def _to_text(x: Union[str, List, None]) -> str:
    """Convert list/None to safe string."""
    if x is None:
        return ""
    if isinstance(x, list):
        return " ".join(str(v) for v in x if v is not None)
    return str(x)


def build_rag_context(
    url: str,
    query: Union[str, List, None],
    focus: Union[str, List, None] = None,
    *,
    top_k: int = 3,
    chunk_size: int = 1200,
    chunk_overlap: int = 150,
    min_clean_len: int = 400,
) -> RAGContext:
    """
    Fetch -> clean -> chunk -> retrieve top chunks by TF-IDF cosine similarity.
    Returns a compact text context to feed LLM (Analyzer/Writer).
    """

    q = _to_text(query).strip()
    f = _to_text(focus).strip()

    if f:
        q_full = f"{q} {f}".strip()
    else:
        q_full = q.strip()

    if not q_full:
        return RAGContext(
            ok=False,
            url=url,
            focus=f,
            query=q_full,
            context="",
            chunks=[],
            top_chunks=[],
            error="empty_query",
        )

    # 1) Fetch
    fetched = fetch_url(url)
    if not fetched.ok:
        logger.warning(f"[rag] fetch failed url={url} err={fetched.error}")
        return RAGContext(
            ok=False,
            url=url,
            focus=f,
            query=q_full,
            context="",
            chunks=[],
            top_chunks=[],
            error=fetched.error,
        )

    # 2) Clean
    cleaned = clean_html_to_text(fetched.text, url=url)
    if len(cleaned) < min_clean_len:
        logger.warning(f"[rag] cleaned text too short url={url} len={len(cleaned)}")
        return RAGContext(
            ok=False,
            url=url,
            focus=f,
            query=q_full,
            context="",
            chunks=[],
            top_chunks=[],
            error="clean_too_short",
        )

    # 3) Chunk
    chunks = chunk_text(cleaned, url=url, chunk_size=chunk_size, overlap=chunk_overlap)
    if not chunks:
        logger.warning(f"[rag] chunking produced 0 chunks url={url}")
        return RAGContext(
            ok=False,
            url=url,
            focus=f,
            query=q_full,
            context="",
            chunks=[],
            top_chunks=[],
            error="no_chunks",
        )

    # 4) Retrieve
    try:
        top = retrieve_tfidf(chunks, q_full, top_k=top_k)
    except Exception as e:
        logger.warning(f"[rag] retrieve failed url={url} err={e}")
        return RAGContext(
            ok=False,
            url=url,
            focus=f,
            query=q_full,
            context="",
            chunks=chunks,
            top_chunks=[],
            error=f"retrieve_error:{e}",
        )

    context = "\n\n---\n\n".join(c.text for c in top)

    return RAGContext(
        ok=True,
        url=url,
        focus=f,
        query=q_full,
        context=context,
        chunks=chunks,
        top_chunks=top,
        error=None,
    )
