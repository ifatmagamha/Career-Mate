# src/rag/embeddings.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


def _normalize_texts(texts: List[str]) -> List[str]:
    out = []
    for t in texts:
        t = (t or "").strip()
        out.append(t)
    return out


@dataclass
class TfidfEmbedder:
    """
    Simple embedder basé sur TF-IDF (local, zéro API).
    - fit_transform(chunks) => matrix [n_chunks, dim]
    - transform([query]) => matrix [1, dim]
    """
    vectorizer: TfidfVectorizer

    @classmethod
    def default(cls) -> "TfidfEmbedder":
        vec = TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            max_features=50000,
            stop_words="english",  # OK pour offres EN; si FR mix, on peut enlever
        )
        return cls(vectorizer=vec)

    def fit_transform(self, chunk_texts: List[str]) -> np.ndarray:
        chunk_texts = _normalize_texts(chunk_texts)
        X = self.vectorizer.fit_transform(chunk_texts)
        return X

    def transform(self, texts: List[str]) -> np.ndarray:
        texts = _normalize_texts(texts)
        X = self.vectorizer.transform(texts)
        return X
