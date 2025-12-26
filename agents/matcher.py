# agents/matcher.py

import numpy as np
from typing import List, Dict, Any
from sklearn.metrics.pairwise import cosine_similarity


def text_to_vector(text: str, vocabulary: List[str]) -> np.ndarray:
    text = text.lower()
    return np.array([1 if word.lower() in text else 0 for word in vocabulary])


class MatcherAgent:
    def __init__(
        self,
        skill_weight: float = 0.7,
        soft_skill_weight: float = 0.3,
        top_k: int = 5,
    ):
        self.skill_weight = skill_weight
        self.soft_skill_weight = soft_skill_weight
        self.top_k = top_k

    def _match_offer(
        self,
        job: Dict[str, Any],
        candidate: Dict[str, Any],
        skill_vocab: List[str],
        soft_skill_vocab: List[str],
    ) -> Dict[str, Any]:

        job_skills_text = " ".join(job.get("skills", []))
        job_soft_text = " ".join(job.get("soft_skills", []))

        cand_skills_text = " ".join(candidate.get("skills", []))
        cand_soft_text = " ".join(candidate.get("soft_skills", []))

        job_skill_vec = text_to_vector(job_skills_text, skill_vocab)
        cand_skill_vec = text_to_vector(cand_skills_text, skill_vocab)

        job_soft_vec = text_to_vector(job_soft_text, soft_skill_vocab)
        cand_soft_vec = text_to_vector(cand_soft_text, soft_skill_vocab)

        skill_score = cosine_similarity(
            job_skill_vec.reshape(1, -1),
            cand_skill_vec.reshape(1, -1),
        )[0][0]

        soft_skill_score = cosine_similarity(
            job_soft_vec.reshape(1, -1),
            cand_soft_vec.reshape(1, -1),
        )[0][0]

        final_score = round(
            (self.skill_weight * skill_score + self.soft_skill_weight * soft_skill_score) * 100,
            2,
        )

        return {
            "offer_title": job.get("title"),
            "company": job.get("company"),
            "source_url": job.get("source_url"),
            "matching_score": final_score,
            "details": {
                "skill_similarity": round(skill_score, 2),
                "soft_skill_similarity": round(soft_skill_score, 2),
                "matched_skills": list(set(job.get("skills", [])) & set(candidate.get("skills", []))),
                "missing_skills": list(set(job.get("skills", [])) - set(candidate.get("skills", []))),
            },
        }

    def run(self, state: dict) -> dict:
        """
        LangGraph node
        Expected state:
        {
            "analyzed_offers": list,
            "candidate_profile": dict
        }
        """

        analyzed_offers = state.get("analyzed_offers", [])
        candidate = state.get("candidate_profile")

        if not candidate:
            raise ValueError("candidate_profile manquant dans le state")

        skill_vocab = list(set(candidate.get("skills", [])))
        soft_skill_vocab = list(set(candidate.get("soft_skills", [])))

        matched = [
            self._match_offer(job, candidate, skill_vocab, soft_skill_vocab)
            for job in analyzed_offers
        ]

        matched_sorted = sorted(
            matched, key=lambda x: x["matching_score"], reverse=True
        )

        state["matched_offers"] = matched_sorted[: self.top_k]
        return state
