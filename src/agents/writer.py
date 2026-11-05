from typing import Dict, Any, List

from src.config.logging import logger
from src.llm.port import llm, extract_json, prompt_version
from src.schemas.candidate import CandidateProfile
from src.schemas.job_offer import OfferAnalyzed
from src.utils.prompts import load_prompt


def _clip(text: str, n: int = 12000) -> str:
    return (text or "").strip()[:n]


def _safe_list(x) -> List[str]:
    if isinstance(x, list):
        return [str(i).strip() for i in x if str(i).strip()]
    if isinstance(x, str):
        # If the LLM returned a single string instead of a list, split by lines
        return [s.strip() for s in x.split('\n') if s.strip()]
    return []


def _fallback_letter(candidate: CandidateProfile, offer: OfferAnalyzed) -> Dict[str, Any]:
    return {
        "subject": f"Application for {offer.title}",
        "body": [
            "Dear Hiring Manager,",
            "",
            f"I am writing to express my interest in the {offer.title} position at {offer.company}.",
            "Please find my resume attached.",
            "",
            "Best regards,",
            f"{candidate.full_name or 'Candidate'}",
        ]
    }


def generate_structured_letter(candidate: CandidateProfile, offer: OfferAnalyzed) -> Dict[str, Any]:
    """
    Returns a structured letter (subject + lines), grounded in CV raw.
    """
    cv_raw = _clip(candidate.cv_text, 7000)

    prompt_template = load_prompt("writer_letter")
    # SAFE INJECTION
    prompt = prompt_template.replace("{title}", offer.title) \
                           .replace("{company}", offer.company or "Unknown") \
                           .replace("{location}", offer.location or "Unknown") \
                           .replace("{skills}", ", ".join(_safe_list(offer.skills))) \
                           .replace("{missions}", ", ".join(_safe_list(offer.missions))) \
                           .replace("{cv_raw}", cv_raw)

    try:
        text = llm.complete(prompt, role="write", prompt_version=prompt_version(prompt_template), temperature=0.3) or ""
        data = extract_json(text)
        if not isinstance(data.get("body"), list):
            data["body"] = []
        return data
    except Exception as e:
        logger.error(f"Error generating Letter: {e}")
        return _fallback_letter(candidate, offer)


def generate_cold_email(candidate: CandidateProfile, offer: OfferAnalyzed, tone: str = "professional") -> str:
    cv_raw = _clip(candidate.cv_text, 7000)
    prompt_template = load_prompt("writer_email.md")
    # SAFE INJECTION
    prompt = prompt_template.replace("{title}", offer.title) \
                           .replace("{company}", offer.company or "Unknown") \
                           .replace("{missions}", ", ".join(_safe_list(offer.missions))) \
                           .replace("{requirements}", ", ".join(_safe_list(offer.requirements))) \
                           .replace("{tone}", tone) \
                           .replace("{cv_raw}", cv_raw)
    try:
        text = llm.complete(prompt, role="write", prompt_version=prompt_version(prompt_template), temperature=0.4) or ""
        return text
    except Exception as e:
        logger.error(f"Error generating Email: {e}")
        return f"Generated cold email for {offer.title} at {offer.company}."

def generate_interview_prep(candidate: CandidateProfile, offer: OfferAnalyzed, difficulty: str = "medium") -> str:
    cv_raw = _clip(candidate.cv_text, 7000)
    prompt_template = load_prompt("writer_interview.md")
    # SAFE INJECTION
    prompt = prompt_template.replace("{title}", offer.title) \
                           .replace("{company}", offer.company or "Unknown") \
                           .replace("{missions}", ", ".join(_safe_list(offer.missions))) \
                           .replace("{requirements}", ", ".join(_safe_list(offer.requirements))) \
                           .replace("{difficulty}", difficulty) \
                           .replace("{cv_raw}", cv_raw)
    try:
        text = llm.complete(prompt, role="write", prompt_version=prompt_version(prompt_template), temperature=0.5) or ""
        return text
    except Exception as e:
        logger.error(f"Error generating Interview Prep: {e}")
        return f"Generated interview questions for {offer.title} at {offer.company}."

def generate_documents(candidate: CandidateProfile, offer: OfferAnalyzed, doc_type: str = "cover-letter", extra: str = "professional") -> str:
    """
    Unified entry point for UI generation.
    """
    if doc_type == "cover-letter":
        letter_data = generate_structured_letter(candidate, offer)
        return f"SUBJECT: {letter_data.get('subject')}\n\n" + "\n".join(_safe_list(letter_data.get('body')))
    elif doc_type == "cold-email":
        return generate_cold_email(candidate, offer, tone=extra)
    elif doc_type == "interview":
        return generate_interview_prep(candidate, offer, difficulty=extra)
    return "Unknown document type."
