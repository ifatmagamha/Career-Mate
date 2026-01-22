# src/pipelines/run.py
from __future__ import annotations

from pathlib import Path
from typing import Tuple, List

from src.agents.collector import collect_offers
from src.agents.analyzer import analyze_offers
from src.agents.matcher import match_offers
from src.config.settings import settings
from src.schemas.candidate import CandidateProfile
from src.schemas.job_offer import OfferRaw, OfferAnalyzed, MatchResult
from src.storage.io import save_json


def run_pipeline(
    candidate: CandidateProfile,
    *,
    query: str,
    location: str,
    limit: int = 10,
    llm_max: int = 2,
    top_k: int = 10,
    persist: bool = True,
) -> Tuple[List[OfferRaw], List[OfferAnalyzed], List[MatchResult]]:
    offers_raw = collect_offers(query=query, location=location, limit=limit)
    offers_analyzed = analyze_offers(offers_raw, llm_max=llm_max)
    matches = match_offers(candidate, offers_analyzed, top_k=top_k)

    if persist:
        data_dir = Path(settings.DATA_DIR)
        save_json(data_dir / "job_offers_raw.json", offers_raw)
        save_json(data_dir / "job_offers_analyzed.json", offers_analyzed)
        save_json(data_dir / "matches.json", matches)

    return offers_raw, offers_analyzed, matches
