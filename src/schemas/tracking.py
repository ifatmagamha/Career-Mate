from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ApplicationStatus(str, Enum):
    SAVED = "saved"
    APPLIED = "applied"
    INTERVIEW = "interview"
    REJECTED = "rejected"
    OFFER = "offer"


class ApplicationEvent(BaseModel):
    job_id: str
    candidate_id: str
    status: ApplicationStatus
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None
