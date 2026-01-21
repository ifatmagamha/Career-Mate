from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from schemas.candidate import CandidateProfile
from schemas.job import JobOfferParsed
from schemas.match import MatchResult, ScoreBreakdown


def _overlap(a: Iterable[str], b: Iterable[str]) -> tuple[list[str], list[str]]:
    sa = {x.strip().lower() for x in a if x}
    sb = {x.strip().lower() for x in b if x}
    matched = sorted(sa & sb)
    missing = sorted(sa - sb)
    return matched, missing


@dataclass
class MatcherAgent:
    weight_skills: float = 0.8
    weight_constraints: float = 0.2

    def score(self, offer: JobOfferParsed, cand: CandidateProfile) -> MatchResult:
        matched, missing = _overlap(offer.skills, cand.skills)

        # score simple: proportion de skills de l’offre couvertes par le candidat
        denom = max(1, len(set([s.lower() for s in offer.skills if s])))
        skill_score = len(matched) / denom  # 0..1

        # contraintes basiques (optionnel)
        constraints_score = 1.0
        if offer.location and cand.location:
            # si tu veux : pénaliser si villes différentes
            constraints_score = 1.0

        overall = (self.weight_skills * skill_score + self.weight_constraints * constraints_score) * 100

        reasons = []
        if matched:
            reasons.append(f"Compétences en commun: {', '.join(matched[:8])}" + ("..." if len(matched) > 8 else ""))
        if missing:
            reasons.append(f"Compétences manquantes (offre): {', '.join(missing[:8])}" + ("..." if len(missing) > 8 else ""))

        return MatchResult(
            job_id=offer.id,
            candidate_id=cand.id,
            score=round(overall, 2),
            breakdown=ScoreBreakdown(
                skills=round(skill_score * 100, 2),
                constraints=round(constraints_score * 100, 2),
                experience=0.0,
                overall=round(overall, 2),
            ),
            matched_skills=matched,
            missing_skills=missing,
            reasons=reasons,
            recommendations=[
                f"Renforcer: {ms}" for ms in missing[:5]
            ],
        )

    def rank(self, offers: list[JobOfferParsed], cand: CandidateProfile) -> list[MatchResult]:
        res = [self.score(o, cand) for o in offers]
        return sorted(res, key=lambda x: x.score, reverse=True)
