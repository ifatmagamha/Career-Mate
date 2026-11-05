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


SheetContract = Literal["permanent", "fixed_term", "internship", "apprenticeship", "freelance", "part_time", "unknown"]
SheetRemote = Literal["onsite", "hybrid", "remote", "unknown"]
SheetSeniority = Literal["intern", "junior", "mid", "senior", "lead", "unknown"]


class OfferSheet(BaseModel):
    """Fiche offre synthétique produite par la capture (lien ou texte collé)."""
    model_config = ConfigDict(extra="ignore")

    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    remote_policy: str = Field(default="unknown", description="One of SheetRemote")
    contract_type: str = Field(default="unknown", description="One of SheetContract")
    seniority: str = Field(default="unknown", description="One of SheetSeniority")
    salary: Optional[str] = None
    deadline: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    skills: List[str] = Field(default_factory=list, description="Required skills")
    nice_to_have: List[str] = Field(default_factory=list, description="Optional / bonus skills")
    missions: List[str] = Field(default_factory=list)
    requirements: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
