# src/agents/matcher.py
from __future__ import annotations

from typing import List, Tuple

from src.config.logging import logger
from src.matching.vectorizer import (
    CosineTfidfMatcher,
    build_candidate_text,
    build_offer_text,
)
from src.schemas.candidate import CandidateProfile
from src.schemas.job_offer import OfferAnalyzed, MatchResult


def _overlap(items: List[str], text: str) -> List[str]:
    low = (text or "").lower()
    hits = []
    for x in items or []:
        if x and x.lower() in low:
            hits.append(x)
    # dedup preserve order
    out, seen = [], set()
    for h in hits:
        if h not in seen:
            out.append(h)
            seen.add(h)
    return out


def _is_listing(url: str) -> bool:
    """
    Detect non-job-posting listing/search pages.
    (Even after collector filtering, some can slip in.)
    """
    u = (url or "").lower()
    return (
        "linkedin.com/jobs/" in u
        or "glassdoor.com/job/" in u
        or "glassdoor.fr/emploi/" in u
        or "srch_" in u
        or ("/search" in u and "job" in u)
        or ("jobs/search" in u)
    )


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def match_offers(
    candidate: CandidateProfile,
    offers: List[OfferAnalyzed],
    *,
    top_k: int = 10,
    w_global: float = 0.6,
    w_skills: float = 0.4,
    listing_penalty: int = 15,
    location_bonus: int = 5,
) -> List[MatchResult]:
    """
    Rank offers with TF-IDF cosine similarity.

    Score pipeline:
      sim_global = cosine(TF-IDF(candidate_text), TF-IDF(offer_text))
      sim_skills = cosine(TF-IDF(candidate_skills_text), TF-IDF(offer_skills_text))
      sim = w_global*sim_global + w_skills*sim_skills
      score = round(sim*100) with penalties/bonuses

    Returns top_k MatchResult.
    """
    if not offers:
        return []

    logger.info(f"[matcher] matching candidate vs {len(offers)} offers")

    tfidf = CosineTfidfMatcher()

    # --- Candidate representations ---
    candidate_text = build_candidate_text(
        cv_text=candidate.cv_text,
        target_keywords=candidate.target_keywords,
        target_roles=candidate.target_roles,
    )

    candidate_skills_text = " ".join(candidate.target_keywords or [])
    cv_text = candidate.cv_text or ""
    cv_low = cv_text.lower()

    # --- Offer representations ---
    offer_texts = [
        build_offer_text(o.title, o.skills, o.keywords, description=None)
        for o in offers
    ]
    offer_skills_texts = [" ".join(o.skills or []) for o in offers]

    # --- Cosine similarities ---
    sims_global = tfidf.score(candidate_text, offer_texts)
    sims_skills = tfidf.score(candidate_skills_text, offer_skills_texts)

    # --- Rank by composite similarity ---
    composite = []
    for i in range(len(offers)):
        sim = (w_global * _clamp01(sims_global[i])) + (w_skills * _clamp01(sims_skills[i]))
        composite.append(sim)

    ranked = sorted(list(enumerate(composite)), key=lambda x: x[1], reverse=True)
    ranked = ranked[: min(top_k, len(ranked))]

    results: List[MatchResult] = []

    for idx, sim in ranked:
        offer = offers[idx]

        # Base score
        score = int(round(_clamp01(sim) * 100))

        # Penalty: listing pages (less trustworthy)
        if _is_listing(str(offer.url)):
            score = max(0, score - listing_penalty)

        # Bonus: location match
        if candidate.location and offer.location:
            if candidate.location.lower() in offer.location.lower():
                score = min(100, score + location_bonus)

        # Overlaps for explainability
        offer_skill_hits = _overlap(offer.skills, cv_text)
        offer_kw_hits = _overlap(offer.keywords, cv_text)

        strong_points = []
        if offer_skill_hits:
            strong_points.append(f"Skills match: {', '.join(offer_skill_hits[:6])}")
        if offer_kw_hits:
            strong_points.append(f"Keywords overlap: {', '.join(offer_kw_hits[:8])}")
        if candidate.location and offer.location and candidate.location.lower() in offer.location.lower():
            strong_points.append("Location match")

        # Missing skills
        missing = []
        for s in offer.skills or []:
            if s and s.lower() not in cv_low:
                missing.append(s)
        # dedup keep order
        missing_unique, seen = [], set()
        for m in missing:
            if m not in seen:
                missing_unique.append(m)
                seen.add(m)

        reasons = [
            f"Cosine TF-IDF (global) = {sims_global[idx]:.3f}",
            f"Cosine TF-IDF (skills) = {sims_skills[idx]:.3f}",
            f"Composite = {sim:.3f} (w_global={w_global}, w_skills={w_skills})",
        ]
        if offer.contract_type != "unknown":
            reasons.append(f"Contract type: {offer.contract_type}")
        if offer.seniority != "unknown":
            reasons.append(f"Seniority: {offer.seniority}")
        if _is_listing(str(offer.url)):
            reasons.append(f"Listing penalty: -{listing_penalty}")
        if candidate.location and offer.location and candidate.location.lower() in offer.location.lower():
            reasons.append(f"Location bonus: +{location_bonus}")

        results.append(
            MatchResult(
                url=offer.url,
                title=offer.title,
                company=offer.company,
                location=offer.location,
                score=score,
                reasons=reasons[:8],
                missing_skills=missing_unique[:10],
                strong_points=strong_points[:8],
            )
        )

    return results
