# tests/smoke_pipeline.py
from __future__ import annotations

import os
import json

from src.agents.collector import collect_offers
from src.agents.analyzer import analyze_offers
from src.agents.matcher import match_offers
from src.schemas.candidate import CandidateProfile
from src.config.logging import logger


DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)


def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    # 1) Candidate (simple)
    candidate = CandidateProfile(
        full_name="John Doe",
        email="john@test.com",
        phone=None,
        location="Paris",
        cv_text=("Data Science student. Skills: Python, SQL, pandas, scikit-learn. "
                 "Built ML classification project and Streamlit dashboard. ") * 3,
        target_roles=["Data Scientist Intern"],
        target_keywords=["Python", "Machine Learning", "SQL"],
    )

    # 2) Collect (limit small)
    offers_raw = collect_offers(query="Data Science", location="Paris", limit=5)
    save_json(os.path.join(DATA_DIR, "smoke_raw.json"), [o.model_dump(mode="json") for o in offers_raw])

    # 3) Analyze
    offers_analyzed = analyze_offers(offers_raw)
    save_json(os.path.join(DATA_DIR, "smoke_analyzed.json"), [o.model_dump(mode="json") for o in offers_analyzed])

    # 4) Match
    matches = match_offers(candidate, offers_analyzed)
    save_json(os.path.join(DATA_DIR, "smoke_matches.json"), [m.model_dump(mode="json") for m in matches])

    logger.info("✅ SMOKE DONE")
    if matches:
        logger.info("TOP 3:")
        for m in matches[:3]:
            logger.info(f" - score={m.score} | {m.title} | {m.company} | {m.url}")
    else:
        logger.info("No matches found.")


if __name__ == "__main__":
    main()
