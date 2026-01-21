from __future__ import annotations

from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl


class Experience(BaseModel):
    role: str
    company: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    location: Optional[str] = None
    bullets: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class Project(BaseModel):
    name: str
    description: Optional[str] = None
    bullets: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    link: Optional[HttpUrl] = None


class Education(BaseModel):
    school: str
    degree: Optional[str] = None
    field: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None


class CandidateProfile(BaseModel):
    id: str = Field(..., description="Unique id for the candidate (uuid)")
    full_name: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None

    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None

    links: list[HttpUrl] = Field(default_factory=list)

    skills: list[str] = Field(default_factory=list, description="Normalized skills list")
    languages: list[str] = Field(default_factory=list)

    experiences: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
