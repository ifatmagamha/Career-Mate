# src/agents/test_analyzer.py
from __future__ import annotations

from src.agents.analyzer import analyze_offer
from src.schemas.job_offer import OfferRaw


def main() -> None:
    url = "https://careers.descartesunderwriting.com/jobs/6631557-data-scientist-intern"

    offer = OfferRaw(
        source="manual_test",
        title="Data Scientist - Intern - Descartes Underwriting",
        company="Descartes Underwriting",
        location="Paris",
        description="Test snippet: internship, python, ML, statistics.",
        url=url,
    )

    analyzed = analyze_offer(offer)
    print("✅ OfferAnalyzed OK")
    print(analyzed.model_dump())


if __name__ == "__main__":
    main()
