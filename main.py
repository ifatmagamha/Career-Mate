# main.py
from __future__ import annotations

import json
import os
from typing import List

from src.config.logging import logger
from src.agents.collector import collect_offers
from src.agents.analyzer import analyze_offers
from src.agents.matcher import match_offers
from src.agents.writer import generate_pdfs_for_offer

from src.schemas.candidate import CandidateProfile
from src.schemas.job_offer import OfferRaw, OfferAnalyzed, MatchResult


DATA_DIR = "data"
GEN_DIR = os.path.join(DATA_DIR, "generated")


def save_json(path: str, data) -> None:
    """Save already-JSON-serializable data (dict/list with str/int/etc.)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def dump_models_json(models) -> list:
    """Convert Pydantic models (HttpUrl, etc.) to JSON-ready dicts."""
    return [m.model_dump(mode="json") for m in models]


def main():
    # -------------------------
    # 0) Candidate (MVP example)
    # -------------------------
    user_id = "user_001"

    candidate = CandidateProfile(
        full_name="John Doe",
        email="john@test.com",
        phone="0600000000",
        location="Paris",
        cv_text=(
            "Data Science student. Skills: Python, SQL, pandas, scikit-learn. "
            "Built ML classification project and Streamlit dashboard. "
        ) * 4,
        target_roles=["Data Scientist Intern"],
        target_keywords=["Python", "SQL", "Machine Learning", "pandas", "scikit-learn"],
    )

    # -------------------------
    # 1) Collect
    # -------------------------
    query = "Data Science"
    location = "Paris"
    limit = 10

    offers_raw: List[OfferRaw] = collect_offers(query=query, location=location, limit=limit)
    save_json(os.path.join(DATA_DIR, "job_offers_raw.json"), dump_models_json(offers_raw))

    # -------------------------
    # 2) Analyze (RAG inside analyzer)
    # -------------------------
    offers_analyzed: List[OfferAnalyzed] = analyze_offers(offers_raw)
    save_json(os.path.join(DATA_DIR, "job_offers_analyzed.json"), dump_models_json(offers_analyzed))

    # -------------------------
    # 3) Match
    # -------------------------
    matches: List[MatchResult] = match_offers(candidate, offers_analyzed, top_k=10)
    save_json(os.path.join(DATA_DIR, "matches.json"), dump_models_json(matches))

    if not matches:
        logger.info("[main] no matches found.")
        return

    # -------------------------
    # 4) Best offer + Generate PDFs
    # -------------------------
    best = matches[0]
    best_offer = next((o for o in offers_analyzed if str(o.url) == str(best.url)), None)
    if not best_offer:
        logger.warning("[main] best offer not found in analyzed list.")
        return

    cv_path, letter_path = generate_pdfs_for_offer(
        candidate=candidate,
        offer=best_offer,
        user_id=user_id,
        output_dir=GEN_DIR,
    )

    logger.info("[main] DONE ✅")
    logger.info(f"[main] TOP match score={best.score} | {best.title} | {best.url}")
    logger.info(f"[main] CV PDF saved -> {cv_path}")
    logger.info(f"[main] LETTER PDF saved -> {letter_path}")


if __name__ == "__main__":
    main()
