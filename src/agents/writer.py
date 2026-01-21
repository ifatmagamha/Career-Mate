# src/agents/writer.py
from __future__ import annotations

from src.llm.gemini_client import llm
from src.schemas.candidate import CandidateProfile
from src.schemas.job_offer import OfferAnalyzed


def generate_documents(candidate: CandidateProfile, offer: OfferAnalyzed) -> tuple[str, str]:
    """
    Generate a targeted CV summary + motivation letter for ONE offer.
    Keep token usage small.
    """
    prompt_cv = f"""
You are a recruiting assistant.
Rewrite a SHORT targeted CV (max 12 bullet points) for the candidate to match this internship offer.
Do not invent experiences. Only rephrase and highlight what exists in the CV text.
Output plain text.

CANDIDATE CV TEXT:
{candidate.cv_text}

OFFER:
Title: {offer.title}
Company: {offer.company or "unknown"}
Location: {offer.location or "unknown"}
Skills: {offer.skills}
Keywords: {offer.keywords}
"""

    prompt_letter = f"""
Write a personalized motivation letter in French for this internship.
Constraints:
- 180 to 250 words
- Professional tone
- Mention 2-3 relevant skills from candidate CV
- Do NOT invent projects/companies
Output plain text.

CANDIDATE CV TEXT:
{candidate.cv_text}

OFFER:
Title: {offer.title}
Company: {offer.company or "unknown"}
Location: {offer.location or "unknown"}
Skills: {offer.skills}
Keywords: {offer.keywords}
"""

    cv_out = llm.generate_text(prompt_cv, temperature=0.2, max_output_tokens=600)
    letter_out = llm.generate_text(prompt_letter, temperature=0.3, max_output_tokens=700)

    return cv_out.strip(), letter_out.strip()
