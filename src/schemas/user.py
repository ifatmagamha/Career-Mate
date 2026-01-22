# src/schemas/user.py
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field, HttpUrl, EmailStr, ConfigDict


class UserProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: str = Field(description="Internal user id")
    email: EmailStr
    full_name: str = ""
    location: str = "Paris"

    github_url: Optional[HttpUrl] = None
    linkedin_url: Optional[HttpUrl] = None
    portfolio_url: Optional[HttpUrl] = None

    # Candidate content
    cv_text: str = ""

    # Search preferences
    target_roles: List[str] = Field(default_factory=list)
    target_keywords: List[str] = Field(default_factory=list)

    # Simple constraints (MVP)
    preferred_locations: List[str] = Field(default_factory=list)
    remote_ok: bool = False
    language: str = "fr"   # fr/en

    created_at: Optional[str] = None
    updated_at: Optional[str] = None
