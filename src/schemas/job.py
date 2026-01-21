from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, HttpUrl


class JobOfferRaw(BaseModel):
    id: str = Field(..., description="Unique id (hash url+title+company or uuid)")
    source: str = Field(..., description="e.g. linkedin, indeed, welcome_to_the_jungle")
    url: Optional[HttpUrl] = None
    collected_at: datetime = Field(default_factory=datetime.utcnow)

    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None

    raw_text: str = Field(..., description="Full job offer text (cleaned HTML or plain text)")
    raw_payload: Optional[dict[str, Any]] = Field(default=None, description="Optional original JSON/HTML metadata")


class JobOfferParsed(BaseModel):
    id: str
    source: str
    url: Optional[HttpUrl] = None

    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    contract_type: Optional[str] = Field(default=None, description="internship, full-time, part-time, etc.")
    remote_policy: Optional[str] = Field(default=None, description="onsite/hybrid/remote")
    seniority: Optional[str] = Field(default=None, description="junior/mid/senior")

    missions: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)

    skills: list[str] = Field(default_factory=list, description="Normalized skills (e.g. python, langchain)")
    tools_stack: list[str] = Field(default_factory=list, description="Tools/tech stack if separated from skills")
    languages: list[str] = Field(default_factory=list, description="Human languages if mentioned")

    education_level: Optional[str] = None
    years_experience_min: Optional[float] = None

    keywords: list[str] = Field(default_factory=list)
    summary: Optional[str] = None
