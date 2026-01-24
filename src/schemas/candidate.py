from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr, ConfigDict


class CandidateProfile(BaseModel):
    """Profil candidat minimal pour MVP."""
    model_config = ConfigDict(extra="ignore")

    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    social_links: List[str] = Field(default_factory=list, description="Social account URLs")

    # IMPORTANT: on garde le CV en texte brut (ex: contenu PDF déjà extrait ou copié-collé)
    cv_text: str = Field("", description="CV du candidat en texte brut")

    # Optionnel MVP: si l'utilisateur veut aider le matching
    target_roles: List[str] = Field(default_factory=list, description="Ex: ['Data Scientist', 'ML Engineer']")
    target_keywords: List[str] = Field(default_factory=list, description="Ex: ['NLP', 'Python', 'TensorFlow']")
    
    # Editable Fields (Added for Profile Editor)
    summary: Optional[str] = None
    skills: List[str] = Field(default_factory=list, description="Hard skills")
    soft_skills: List[str] = Field(default_factory=list, description="Soft skills and languages")
    experience: List[dict] = Field(default_factory=list, description="List of role objects")
    education: List[dict] = Field(default_factory=list, description="List of education objects")
    projects: List[dict] = Field(default_factory=list, description="Academic or professional projects")
    certifications: List[dict] = Field(default_factory=list, description="Obtained certificates")
    volunteer_experience: List[dict] = Field(default_factory=list, description="Volunteer roles")
