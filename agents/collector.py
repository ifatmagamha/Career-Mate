# agents/collector.py

import time
import requests
from abc import ABC, abstractmethod
from typing import List, Dict


class BaseCollector(ABC):
    @abstractmethod
    def collect(self, query: str, location: str, limit: int) -> List[Dict]:
        pass


class GoogleJobsCollector(BaseCollector):
    def __init__(self, api_key: str, cse_id: str):
        self.api_key = api_key
        self.cse_id = cse_id
        self.base_url = "https://www.googleapis.com/customsearch/v1"

    def collect(self, query: str, location: str, limit: int) -> List[Dict]:
        offers = []
        start = 1

        while len(offers) < limit:
            params = {
                "key": self.api_key,
                "cx": self.cse_id,
                "q": f"site:indeed.com {query} {location}",
                "num": 10,
                "start": start,
            }

            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "items" not in data:
                break

            for item in data["items"]:
                offers.append({
                    "source": "Indeed (Google Jobs)",
                    "title": item.get("title"),
                    "company": item.get("displayLink"),
                    "location": location,
                    "description": item.get("snippet"),
                    "url": item.get("link"),
                })

            start += 10
            time.sleep(1)

        return offers[:limit]


class CollectorAgent:
    def __init__(self, collectors: List[BaseCollector]):
        self.collectors = collectors

    def run(self, state: dict) -> dict:
        """
        LangGraph node
        Expected state:
        {
            "query": str,
            "location": str,
            "limit": int
        }
        """

        all_offers = []

        for collector in self.collectors:
            offers = collector.collect(
                query=state["query"],
                location=state["location"],
                limit=state.get("limit", 20),
            )
            all_offers.extend(offers)

        state["raw_offers"] = all_offers
        return state
