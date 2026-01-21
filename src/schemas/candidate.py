# src/schemas/candidate.py
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr, ConfigDict


class CandidateProfile(BaseModel):
    """Profil candidat minimal pour MVP."""
    model_config = ConfigDict(extra="ignore")

    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    location: Optional[str] = None

    # IMPORTANT: on garde le CV en texte brut (ex: contenu PDF déjà extrait ou copié-collé)
    cv_text: str = Field(..., min_length=50, description="CV du candidat en texte brut")

    # Optionnel MVP: si l'utilisateur veut aider le matching
    target_roles: List[str] = Field(default_factory=list, description="Ex: ['Data Scientist', 'ML Engineer']")
    target_keywords: List[str] = Field(default_factory=list, description="Ex: ['NLP', 'Python', 'TensorFlow']")
