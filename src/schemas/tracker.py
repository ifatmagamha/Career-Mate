# src/schemas/tracker.py
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict, HttpUrl


ApplicationStatus = Literal[
    "to_apply",
    "applied",
    "interview",
    "rejected",
    "accepted",
]


class ApplicationEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    action: str = Field(description="e.g. 'created', 'status_changed', 'note_added'")
    meta: Dict[str, str] = Field(default_factory=dict)


class ApplicationRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: str
    offer_url: HttpUrl
    offer_title: str
    company: Optional[str] = None
    location: Optional[str] = None

    status: ApplicationStatus = "to_apply"
    cv_pdf: Optional[str] = None
    letter_pdf: Optional[str] = None

    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    notes: List[str] = Field(default_factory=list)
    events: List[ApplicationEvent] = Field(default_factory=list)


class TrackingDB(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # user_id -> list of applications
    applications: Dict[str, List[ApplicationRecord]] = Field(default_factory=dict)
