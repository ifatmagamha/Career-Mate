# src/matching/vectorizer.py
from __future__ import annotations

import re
from typing import List, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _normalize_text(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9+\-#/ ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def build_offer_text(title: str, skills: List[str], keywords: List[str], description: str | None = None) -> str:
    parts = [title or ""]
    if description:
        parts.append(description)
    if skills:
        parts.append(" ".join(skills))
    if keywords:
        parts.append(" ".join(keywords))
    return _normalize_text(" ".join(parts))


def build_candidate_text(cv_text: str, target_keywords: List[str] | None = None, target_roles: List[str] | None = None) -> str:
    parts = [cv_text or ""]
    if target_roles:
        parts.append(" ".join(target_roles))
    if target_keywords:
        parts.append(" ".join(target_keywords))
    return _normalize_text(" ".join(parts))


class CosineTfidfMatcher:
    """
    TF-IDF cosine similarity matcher.
    Fit on [candidate_text] + offer_texts to build a shared vector space.
    """

    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.95,
        )

    def score(self, candidate_text: str, offer_texts: List[str]) -> List[float]:
        corpus = [candidate_text] + offer_texts
        X = self.vectorizer.fit_transform(corpus)
        cand_vec = X[0:1]
        offer_vecs = X[1:]
        sims = cosine_similarity(cand_vec, offer_vecs).flatten()
        return sims.tolist()
