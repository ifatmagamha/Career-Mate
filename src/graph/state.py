from __future__ import annotations

from typing import Optional, TypedDict, Any

from schemas.candidate import CandidateProfile
from schemas.job import JobOfferRaw, JobOfferParsed
from schemas.match import MatchResult
from schemas.tracking import ApplicationEvent


class RecruitAIState(TypedDict, total=False):
    # Inputs
    candidate: CandidateProfile
    query: str
    location: str
    limit: int

    # Collector / Analyzer
    offers_raw: list[JobOfferRaw]
    offers_parsed: list[JobOfferParsed]

    # RAG
    rag_k: int
    rag_indexed_count: int
    rag_query_result: dict[str, Any]
    rag_top_offer_ids: list[str]

    # Matching
    matches: list[MatchResult]
    selected_job_id: Optional[str]

    # Generated docs
    generated_cv_path: Optional[str]
    generated_letter_path: Optional[str]

    # Tracking
    tracking_events: list[ApplicationEvent]
    last_application_row: dict[str, Any]

    # Errors
    errors: list[str]
    fetched_count: int
    filtered_count: int
