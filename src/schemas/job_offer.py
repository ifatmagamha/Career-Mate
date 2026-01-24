# src/schemas/job_offer.py
from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, HttpUrl, ConfigDict


class OfferRaw(BaseModel):
    """Offre brute issue du collector (Google CSE ou autre)."""
    model_config = ConfigDict(extra="ignore")

    source: str = Field(default="google_cse")
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    url: HttpUrl


ContractType = Literal["internship", "full_time", "part_time", "apprenticeship", "freelance", "unknown"]
Seniority = Literal["intern", "junior", "unknown"]


class OfferAnalyzed(BaseModel):
    """Offre analysée (JSON strict) produite par Analyzer."""
    model_config = ConfigDict(extra="ignore")

    url: HttpUrl
    title: str
    company: Optional[str] = None
    location: Optional[str] = None

    contract_type: ContractType = "unknown"
    seniority: Seniority = "unknown"

    salary: Optional[str] = "Competitive"
    postedDate: Optional[str] = "Today"

    skills: List[str] = Field(default_factory=list, description="Compétences techniques & outils (liste normalisée)")
    missions: List[str] = Field(default_factory=list, description="Missions/responsabilités (phrases courtes)")
    requirements: List[str] = Field(default_factory=list, description="Critères/conditions (phrases courtes)")
    keywords: List[str] = Field(default_factory=list, description="Mots-clés utiles pour matching")

    summary: Optional[str] = Field(default=None, description="Résumé très court (1-2 phrases max)")


class MatchResult(BaseModel):
    """Résultat du matching candidat <-> offre."""
    model_config = ConfigDict(extra="ignore")

    url: HttpUrl
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    salary: Optional[str] = "Competitive"
    postedDate: Optional[str] = "Today"

    score: int = Field(ge=0, le=100, description="Score de matching 0..100")
    reasons: List[str] = Field(default_factory=list, description="Pourquoi ça match (bullet points)")
    missing_skills: List[str] = Field(default_factory=list, description="Compétences manquantes (bullet points)")
    strong_points: List[str] = Field(default_factory=list, description="Points forts du candidat vs l'offre")
