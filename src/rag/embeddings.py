from __future__ import annotations

from dataclasses import dataclass
from sentence_transformers import SentenceTransformer


@dataclass
class EmbeddingModel:
    model_name: str = "all-MiniLM-L6-v2"

    def __post_init__(self):
        self._model = SentenceTransformer(self.model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        # returns list of vectors
        vecs = self._model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vecs]
