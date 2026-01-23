from __future__ import annotations

import re
from typing import List, Tuple

import numpy as np
import numpy as np


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


from langchain_google_genai import GoogleGenerativeAIEmbeddings
from src.config.settings import settings

class SemanticMatcher:
    """
    Semantic similarity matcher using Google Gemini Embeddings.
    """

    def __init__(self):
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=settings.GEMINI_API_KEY
        )

    def score(self, candidate_text: str, offer_texts: List[str]) -> List[float]:
        if not candidate_text:
            return [0.0] * len(offer_texts)
            
        try:
            # Optimize: In heavy prod, do batch embedding.
            # Here simplicity is key.
            cand_vec = self.embeddings.embed_query(candidate_text)
            
            scores = []
            for t in offer_texts:
                if not t:
                    scores.append(0.0)
                    continue
                t_vec = self.embeddings.embed_query(t)
                
                # Manual Cosine Similarity to avoid sklearn dep if needed, but sklearn is present
                # Cosine = (A . B) / (||A|| * ||B||)
                dot_product = np.dot(cand_vec, t_vec)
                norm_a = np.linalg.norm(cand_vec)
                norm_b = np.linalg.norm(t_vec)
                
                if norm_a == 0 or norm_b == 0:
                    scores.append(0.0)
                else:
                    scores.append(float(dot_product / (norm_a * norm_b)))
            return scores
        except Exception as e:
            # log err
            return [0.0] * len(offer_texts)
