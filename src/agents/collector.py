from __future__ import annotations

import os
import time
import hashlib
from dataclasses import dataclass
from typing import Any, Protocol, Optional

import requests

from schemas.job import JobOfferRaw


class BaseCollector(Protocol):
    def collect(self, *, query: str, location: str, limit: int = 20) -> list[JobOfferRaw]:
        ...


def _make_id(source: str, url: str | None, title: str | None, company: str | None) -> str:
    s = f"{source}|{url or ''}|{title or ''}|{company or ''}".encode("utf-8")
    return hashlib.sha256(s).hexdigest()[:16]


@dataclass
class GoogleJobsCollector:
    api_key: str | None = None
    cse_id: str | None = None
    base_url: str = "https://www.googleapis.com/customsearch/v1"

    def __post_init__(self):
        self.api_key = self.api_key or os.getenv("GOOGLE_API_KEY")
        self.cse_id = self.cse_id or os.getenv("GOOGLE_CSE_ID")
        if not self.api_key:
            raise ValueError("Missing GOOGLE_API_KEY")
        if not self.cse_id:
            raise ValueError("Missing GOOGLE_CSE_ID")

    def collect(self, *, query: str, location: str, limit: int = 20) -> list[JobOfferRaw]:
        offers: list[JobOfferRaw] = []
        start = 1

        while len(offers) < limit:
            params = {
                "key": self.api_key,
                "cx": self.cse_id,
                "q": f"site:indeed.com {query} {location}",
                "num": 10,
                "start": start,
            }
            r = requests.get(self.base_url, params=params, timeout=30)
            r.raise_for_status()
            data: dict[str, Any] = r.json()

            items = data.get("items") or []
            if not items:
                break

            for item in items:
                title = item.get("title")
                url = item.get("link")
                company = item.get("displayLink")  # approximation (comme ton notebook)
                snippet = item.get("snippet") or ""
                job_id = _make_id("google_cse_indeed", url, title, company)

                offers.append(
                    JobOfferRaw(
                        id=job_id,
                        source="google_cse_indeed",
                        url=url,
                        title=title,
                        company=company,
                        location=location,
                        raw_text=snippet,
                        raw_payload=item,
                    )
                )

            start += 10
            time.sleep(1)  # respect quota

        return offers[:limit]


@dataclass
class CollectorAgent:
    collectors: list[BaseCollector]

    def run(self, *, query: str, location: str, limit: int = 20) -> list[JobOfferRaw]:
        all_offers: list[JobOfferRaw] = []
        for c in self.collectors:
            try:
                all_offers.extend(c.collect(query=query, location=location, limit=limit))
            except Exception as e:
                # tu peux logger proprement plus tard
                print(f"[CollectorAgent] Collector error: {e}")
        # dédoublonnage par id
        uniq: dict[str, JobOfferRaw] = {o.id: o for o in all_offers}
        return list(uniq.values())[:limit]
