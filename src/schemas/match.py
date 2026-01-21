from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class ScoreBreakdown(BaseModel):
    skills: float = 0.0
    experience: float = 0.0
    constraints: float = 0.0  # location/contract/remote
    overall: float = 0.0


class MatchResult(BaseModel):
    job_id: str
    candidate_id: str

    score: float = Field(..., ge=0, le=100)
    breakdown: Optional[ScoreBreakdown] = None

    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)

    reasons: list[str] = Field(default_factory=list, description="Short explainability bullets")
    recommendations: list[str] = Field(default_factory=list, description="How to improve profile for this job")
