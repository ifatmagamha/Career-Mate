from __future__ import annotations

from typing import TypedDict, List, Dict, Optional, Any
from src.schemas.job_offer import OfferRaw, OfferAnalyzed, MatchResult
from src.schemas.candidate import CandidateProfile


from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing import Annotated

class RecruitAIState(TypedDict, total=False):
    # Chat History
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Inputs user
    query: str
    location: str
    limit: int
    candidate: CandidateProfile

    # Pipeline data
    offers_raw: List[OfferRaw]
    offers_analyzed: List[OfferAnalyzed]
    matches: List[MatchResult]

    # Writer outputs (paths)
    generated_docs: Dict[str, str]  # {"cv": ".../cv.md", "letter": ".../letter.md"}

    # Tracking
    tracking_ids: List[str]

    # Debug / errors
    errors: List[str]
    retrieved_chunks: List[str]  # Chunks retrieved by RAG
    meta: Dict[str, Any]  # place pour infos annexes (timings, tokens, etc.)


def new_state(
    *,
    query: str,
    location: str,
    limit: int = 10,
    candidate: Optional[CandidateProfile] = None,
) -> RecruitAIState:
    """Factory safe pour init un state."""
    state: RecruitAIState = {
        "query": query,
        "location": location,
        "limit": limit,
        "errors": [],
        "meta": {},
    }
    if candidate is not None:
        state["candidate"] = candidate
    return state
