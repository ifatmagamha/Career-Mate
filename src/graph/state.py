# src/graph/state.py
from __future__ import annotations

from typing import List, Optional, TypedDict, Dict, Any

from src.schemas.candidate import CandidateProfile
from src.schemas.job_offer import OfferRaw, OfferAnalyzed, MatchResult


class RecruitAIState(TypedDict, total=False):
    # session / user
    user_id: str

    # search inputs
    query: str
    location: str
    limit: int

    # candidate profile
    candidate: CandidateProfile

    # pipeline artifacts
    offers_raw: List[OfferRaw]
    offers_analyzed: List[OfferAnalyzed]
    matches: List[MatchResult]

    # selection + generation
    selected_offer_url: Optional[str]
    generated: Dict[str, Any]  # { "cv_pdf": "...", "letter_pdf": "...", "offer_url": "..." }

    # tracking
    tracking: Dict[str, Any]  # record dump
