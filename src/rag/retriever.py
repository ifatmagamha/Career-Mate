from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from rag.embeddings import EmbeddingModel
from rag.memory_store import MemoryVectorStore
from schemas.candidate import CandidateProfile


def candidate_to_query(c: CandidateProfile) -> str:
    parts = [
        f"Headline: {c.headline or ''}",
        f"Summary: {c.summary or ''}",
        f"Location: {c.location or ''}",
        "Skills: " + ", ".join(c.skills or []),
    ]
    if c.experiences:
        exp_lines = []
        for e in c.experiences[:3]:
            exp_lines.append(f"{e.role} at {e.company or ''}: " + "; ".join(e.bullets[:3]))
        parts.append("Experience: " + " | ".join(exp_lines))
    return "\n".join(parts)


def cosine_top_k(matrix: np.ndarray, query: np.ndarray, k: int) -> tuple[list[int], list[float]]:
    # matrix: (N, D), query: (D,)
    # assume embeddings normalized -> cosine = dot
    sims = matrix @ query
    idx = np.argsort(-sims)[:k]
    return idx.tolist(), sims[idx].tolist()


@dataclass
class OfferRetriever:
    store: MemoryVectorStore
    embedder: EmbeddingModel

    def retrieve(self, candidate: CandidateProfile, k: int = 10) -> dict[str, Any]:
        payload = self.store.load()
        ids = payload["ids"]
        vectors = payload["vectors"]  # np.ndarray
        metadatas = payload["metadatas"]
        texts = payload["texts"]

        q = candidate_to_query(candidate)
        q_vec = np.array(self.embedder.embed([q])[0], dtype=np.float32)

        idxs, sims = cosine_top_k(vectors, q_vec, k=min(k, len(ids)))

        top_ids = [ids[i] for i in idxs]
        top_meta = [metadatas[i] for i in idxs]
        top_texts = [texts[i] for i in idxs]

        return {
            "ids": [top_ids],
            "metadatas": [top_meta],
            "documents": [top_texts],
            "distances": [[float(1 - s) for s in sims]],  # distance ~ 1 - similarity
            "similarities": [sims],
        }
