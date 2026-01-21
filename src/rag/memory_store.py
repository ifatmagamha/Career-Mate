from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class MemoryVectorStore:
    path: str = "data/vectorstore/offers_index.pkl"

    def save(self, *, ids: list[str], vectors: list[list[float]], metadatas: list[dict[str, Any]], texts: list[str]) -> None:
        p = Path(self.path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ids": ids,
            "vectors": np.array(vectors, dtype=np.float32),
            "metadatas": metadatas,
            "texts": texts,
        }
        with open(p, "wb") as f:
            pickle.dump(payload, f)

    def load(self) -> dict[str, Any]:
        p = Path(self.path)
        if not p.exists():
            raise FileNotFoundError(f"Index not found: {self.path}")
        with open(p, "rb") as f:
            payload = pickle.load(f)
        return payload
