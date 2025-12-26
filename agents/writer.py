# agents/writer.py

import os
import json
from typing import Dict, Any

from google import genai


CV_PROMPT = r"""
Tu es un expert en recrutement.

Génère un CV PROFESSIONNEL en LaTeX pour le candidat suivant,
ciblé spécifiquement pour l'offre ci-dessous.

Contraintes :
- Format LaTeX uniquement
- Style clair, moderne, une page
- Mettre en avant les compétences pertinentes pour l'offre
- NE PAS inclure de texte hors LaTeX

Profil candidat :
{candidate}

Offre ciblée :
{offer}
"""


LETTER_PROMPT = r"""
Tu es un expert en recrutement.

Génère une LETTRE DE MOTIVATION professionnelle en LaTeX,
personnalisée pour l'offre suivante et le candidat donné.

Contraintes :
- Ton formel et professionnel
- Contenu personnalisé selon le matching
- Format LaTeX uniquement
- Pas de texte hors LaTeX

Profil candidat :
{candidate}

Offre ciblée :
{offer}
"""


class WriterAgent:
    def __init__(self, model: str = "gemini-2.5-pro"):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY manquante")

        self.client = genai.Client(api_key=api_key)
        self.model = model

    def _generate_cv(self, candidate: Dict[str, Any], offer: Dict[str, Any]) -> str:
        response = self.client.models.generate_content(
            model=self.model,
            contents=CV_PROMPT.format(
                candidate=json.dumps(candidate, indent=2),
                offer=json.dumps(offer, indent=2),
            ),
        )
        return response.text

    def _generate_letter(self, candidate: Dict[str, Any], offer: Dict[str, Any]) -> str:
        response = self.client.models.generate_content(
            model=self.model,
            contents=LETTER_PROMPT.format(
                candidate=json.dumps(candidate, indent=2),
                offer=json.dumps(offer, indent=2),
            ),
        )
        return response.text

    def run(self, state: dict) -> dict:
        """
        LangGraph node
        Expected state:
        {
            "matched_offers": list,
            "candidate_profile": dict
        }
        """

        matched_offers = state.get("matched_offers", [])
        candidate = state.get("candidate_profile")

        if not matched_offers:
            raise ValueError("matched_offers vide")
        if not candidate:
            raise ValueError("candidate_profile manquant")

        # On prend la meilleure offre (déjà triée par le Matcher)
        best_offer = matched_offers[0]

        cv_latex = self._generate_cv(candidate, best_offer)
        letter_latex = self._generate_letter(candidate, best_offer)

        state["final_output"] = {
            "target_offer": best_offer,
            "cv_latex": cv_latex,
            "cover_letter_latex": letter_latex,
        }

        return state
