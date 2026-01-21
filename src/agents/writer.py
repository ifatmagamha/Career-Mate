from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from schemas.candidate import CandidateProfile
from schemas.job import JobOfferParsed
from schemas.match import MatchResult


class LLMClient(Protocol):
    def generate(self, *, model: str, prompt: str) -> str:
        ...


CV_PROMPT = r"""Tu es un expert en recrutement.
Génère un CV PROFESSIONNEL en LaTeX (une page), adapté à l'offre.

Règles STRICTES :
- Format LaTeX uniquement (pas de texte hors LaTeX)
- Ne jamais inventer d'expérience, d'école, de projet, de dates ou d'entreprises
- Utiliser uniquement les infos du profil candidat fourni
- Mettre en avant ce qui est pertinent pour l'offre et le matching

Profil candidat (JSON):
{candidate_json}

Offre analysée (JSON):
{offer_json}

Matching (JSON):
{match_json}
"""

LETTER_PROMPT = r"""Tu es un expert en recrutement.
Génère une LETTRE DE MOTIVATION en LaTeX, personnalisée pour l'offre.

Règles STRICTES :
- Format LaTeX uniquement (pas de texte hors LaTeX)
- Ne jamais inventer des faits sur le candidat
- Faire référence aux compétences et expériences réellement présentes dans le profil

Profil candidat (JSON):
{candidate_json}

Offre analysée (JSON):
{offer_json}

Matching (JSON):
{match_json}
"""


@dataclass
class WriterAgent:
    llm: LLMClient
    model: str = "gemini-2.5-pro"

    def generate_cv_latex(self, *, candidate: CandidateProfile, offer: JobOfferParsed, match: MatchResult) -> str:
        return self.llm.generate(
            model=self.model,
            prompt=CV_PROMPT.format(
                candidate_json=candidate.model_dump_json(indent=2),
                offer_json=offer.model_dump_json(indent=2),
                match_json=match.model_dump_json(indent=2),
            ),
        )

    def generate_letter_latex(self, *, candidate: CandidateProfile, offer: JobOfferParsed, match: MatchResult) -> str:
        return self.llm.generate(
            model=self.model,
            prompt=LETTER_PROMPT.format(
                candidate_json=candidate.model_dump_json(indent=2),
                offer_json=offer.model_dump_json(indent=2),
                match_json=match.model_dump_json(indent=2),
            ),
        )

    def save_outputs(self, *, out_dir: str, cv_tex: str, letter_tex: str) -> tuple[str, str]:
        p = Path(out_dir)
        p.mkdir(parents=True, exist_ok=True)
        cv_path = p / "cv_generated.tex"
        letter_path = p / "cover_letter_generated.tex"
        cv_path.write_text(cv_tex, encoding="utf-8")
        letter_path.write_text(letter_tex, encoding="utf-8")
        return str(cv_path), str(letter_path)
