# src/rag/retriever.py
from __future__ import annotations

from typing import List, Union

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.rag.chunker import TextChunk


def _safe_query(query: Union[str, List, None]) -> str:
    if query is None:
        return ""
    if isinstance(query, list):
        return " ".join(str(x) for x in query if x is not None).strip()
    return str(query).strip()


def retrieve_tfidf(chunks: List[TextChunk], query: Union[str, List, None], top_k: int = 3) -> List[TextChunk]:
    q = _safe_query(query)
    if not q:
        return chunks[:top_k]

    docs = [c.text for c in chunks]
    vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
    X = vectorizer.fit_transform(docs)
    qv = vectorizer.transform([q])

    sims = cosine_similarity(qv, X).flatten()
    ranked = sorted(range(len(chunks)), key=lambda i: sims[i], reverse=True)[:top_k]
    return [chunks[i] for i in ranked]
