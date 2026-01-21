from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rag.embeddings import EmbeddingModel
from rag.memory_store import MemoryVectorStore
from schemas.job import JobOfferParsed


def offer_to_text(o: JobOfferParsed) -> str:
    parts = [
        f"Title: {o.title}",
        f"Company: {o.company or ''}",
        f"Location: {o.location or ''}",
        f"Contract: {o.contract_type or ''}",
        f"Remote: {o.remote_policy or ''}",
        f"Seniority: {o.seniority or ''}",
        "Skills: " + ", ".join(o.skills or []),
        "Tools: " + ", ".join(o.tools_stack or []),
        "Missions:\n- " + "\n- ".join(o.missions or []),
        "Requirements:\n- " + "\n- ".join(o.requirements or []),
        "Summary: " + (o.summary or ""),
        "Keywords: " + ", ".join(o.keywords or []),
    ]
    return "\n".join(parts)


@dataclass
class OfferIndexer:
    store: MemoryVectorStore
    embedder: EmbeddingModel

    def index_offers(self, offers: list[JobOfferParsed]) -> int:
        ids: list[str] = []
        texts: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for o in offers:
            ids.append(o.id)
            texts.append(offer_to_text(o))
            metadatas.append({
                "source": o.source,
                "title": o.title,
                "company": o.company,
                "location": o.location,
            })

        if not ids:
            return 0

        vectors = self.embedder.embed(texts)
        self.store.save(ids=ids, vectors=vectors, metadatas=metadatas, texts=texts)
        return len(ids)
