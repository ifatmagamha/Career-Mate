# src/rag/vector_store.py
from __future__ import annotations

import os
import pickle
from dataclasses import dataclass
from typing import List, Tuple, Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from src.rag.embeddings import TfidfEmbedder


@dataclass
class StoredChunk:
    id: str
    text: str


@dataclass
class VectorStore:
    """
    VectorStore local (pickle) basé sur TF-IDF.
    """
    embedder: TfidfEmbedder
    chunks: List[StoredChunk]
    matrix: any  # sparse matrix (scipy)

    @classmethod
    def build(cls, chunks: List[StoredChunk], embedder: Optional[TfidfEmbedder] = None) -> "VectorStore":
        if embedder is None:
            embedder = TfidfEmbedder.default()

        texts = [c.text for c in chunks]
        X = embedder.fit_transform(texts)
        return cls(embedder=embedder, chunks=chunks, matrix=X)

    def search(self, query: str, top_k: int = 3) -> List[Tuple[float, StoredChunk]]:
        q = (query or "").strip()
        if not q:
            return []

        qv = self.embedder.transform([q])  # [1, dim]
        sims = cosine_similarity(qv, self.matrix).flatten()  # [n_chunks]

        if sims.size == 0:
            return []

        idxs = np.argsort(-sims)[:top_k]
        out: List[Tuple[float, StoredChunk]] = []
        for i in idxs:
            out.append((float(sims[i]), self.chunks[int(i)]))
        return out

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load(path: str) -> "VectorStore":
        with open(path, "rb") as f:
            obj = pickle.load(f)
        if not isinstance(obj, VectorStore):
            raise TypeError("Loaded object is not a VectorStore")
        return obj
