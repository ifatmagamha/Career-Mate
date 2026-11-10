from typing import Dict, Any, List

from src.config.logging import logger
from src.llm.port import llm, extract_json, prompt_version
from src.schemas.candidate import CandidateProfile
from src.schemas.job_offer import OfferAnalyzed
from src.utils.prompts import load_prompt

DOC_TYPES = ("cover-letter", "cold-email", "interview")


def _clip(text: str, n: int = 12000) -> str:
    return (text or "").strip()[:n]


def _safe_list(x) -> List[str]:
    if isinstance(x, list):
        return [str(i).strip() for i in x if str(i).strip()]
    if isinstance(x, str):
        # If the LLM returned a single string instead of a list, split by lines
        return [s.strip() for s in x.split('\n') if s.strip()]
    return []


def _instructions_block(instructions: str) -> str:
    """The user's own instructions, or an explicit 'None.' so the prompt section is never empty."""
    return _clip(instructions, 2000) or "None."


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


def generate_structured_letter(candidate: CandidateProfile, offer: OfferAnalyzed, instructions: str = "") -> Dict[str, Any]:
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
                           .replace("{cv_raw}", cv_raw) \
                           .replace("{instructions}", _instructions_block(instructions))

    try:
        text = llm.complete(prompt, role="write", prompt_version=prompt_version(prompt_template), temperature=0.3) or ""
        data = extract_json(text)
        if not isinstance(data.get("body"), list):
            data["body"] = []
        return data
    except Exception as e:
        logger.error(f"Error generating Letter: {e}")
        return _fallback_letter(candidate, offer)


def generate_cold_email(candidate: CandidateProfile, offer: OfferAnalyzed, tone: str = "professional",
                        instructions: str = "") -> str:
    cv_raw = _clip(candidate.cv_text, 7000)
    prompt_template = load_prompt("writer_email.md")
    # SAFE INJECTION
    prompt = prompt_template.replace("{title}", offer.title) \
                           .replace("{company}", offer.company or "Unknown") \
                           .replace("{missions}", ", ".join(_safe_list(offer.missions))) \
                           .replace("{requirements}", ", ".join(_safe_list(offer.requirements))) \
                           .replace("{tone}", tone) \
                           .replace("{cv_raw}", cv_raw) \
                           .replace("{instructions}", _instructions_block(instructions))
    try:
        text = llm.complete(prompt, role="write", prompt_version=prompt_version(prompt_template), temperature=0.4) or ""
        return text
    except Exception as e:
        logger.error(f"Error generating Email: {e}")
        return f"Generated cold email for {offer.title} at {offer.company}."

def generate_interview_prep(candidate: CandidateProfile, offer: OfferAnalyzed, difficulty: str = "medium",
                            instructions: str = "") -> str:
    cv_raw = _clip(candidate.cv_text, 7000)
    prompt_template = load_prompt("writer_interview.md")
    # SAFE INJECTION
    prompt = prompt_template.replace("{title}", offer.title) \
                           .replace("{company}", offer.company or "Unknown") \
                           .replace("{missions}", ", ".join(_safe_list(offer.missions))) \
                           .replace("{requirements}", ", ".join(_safe_list(offer.requirements))) \
                           .replace("{difficulty}", difficulty) \
                           .replace("{cv_raw}", cv_raw) \
                           .replace("{instructions}", _instructions_block(instructions))
    try:
        text = llm.complete(prompt, role="write", prompt_version=prompt_version(prompt_template), temperature=0.5) or ""
        return text
    except Exception as e:
        logger.error(f"Error generating Interview Prep: {e}")
        return f"Generated interview questions for {offer.title} at {offer.company}."

def generate_documents(candidate: CandidateProfile, offer: OfferAnalyzed, doc_type: str = "cover-letter",
                       extra: str = "professional", instructions: str = "") -> str:
    """
    Unified entry point for UI generation.
    """
    if doc_type == "cover-letter":
        letter_data = generate_structured_letter(candidate, offer, instructions)
        return f"SUBJECT: {letter_data.get('subject')}\n\n" + "\n".join(_safe_list(letter_data.get('body')))
    elif doc_type == "cold-email":
        return generate_cold_email(candidate, offer, tone=extra, instructions=instructions)
    elif doc_type == "interview":
        return generate_interview_prep(candidate, offer, difficulty=extra, instructions=instructions)
    return "Unknown document type."


def revise_document(candidate: CandidateProfile, offer: OfferAnalyzed, doc_type: str, current: str, feedback: str,
                    instructions: str = "") -> str:
    """A new version of `current` that applies the user's feedback. Raises on model errors (nothing to save)."""
    template = load_prompt("writer_revise")
    prompt = template.replace("{doc_type}", doc_type.replace("-", " ")) \
                     .replace("{title}", offer.title) \
                     .replace("{company}", offer.company or "Unknown") \
                     .replace("{missions}", ", ".join(_safe_list(offer.missions))) \
                     .replace("{requirements}", ", ".join(_safe_list(offer.requirements))) \
                     .replace("{cv_raw}", _clip(candidate.cv_text, 7000)) \
                     .replace("{instructions}", _instructions_block(instructions)) \
                     .replace("{current}", _clip(current, 12000)) \
                     .replace("{feedback}", _clip(feedback, 2000))
    text = (llm.complete(prompt, role="write", prompt_version=prompt_version(template), temperature=0.3) or "").strip()
    if not text:
        raise ValueError("The model returned an empty revision")
    return text


if __name__ == "__main__":
    # The instructions and the feedback reach the prompts; no real model call (llm.complete is replaced).
    sent = []
    llm.complete = lambda prompt, **kw: (sent.append(prompt), '{"subject": "S", "body": ["Hi"]}')[1]
    cand = CandidateProfile(full_name="Ada", cv_text="SQL, dbt")
    offer = OfferAnalyzed(url="https://x.io/1", title="Data Engineer", company="Acme")
    for doc in DOC_TYPES:
        generate_documents(cand, offer, doc, instructions="Write in French. Sign as Ada L.")
        assert "Write in French. Sign as Ada L." in sent[-1] and "{instructions}" not in sent[-1], doc
    generate_documents(cand, offer, "cold-email")
    assert "personal instructions" in sent[-1] and "None." in sent[-1]  # no instructions: explicit 'None.'
    assert generate_documents(cand, offer, "cover-letter").startswith("SUBJECT: S")

    llm.complete = lambda prompt, **kw: (sent.append(prompt), "  Revised text  ")[1]
    out = revise_document(cand, offer, "cover-letter", "Old letter", "Shorter, mention dbt", "Sign as Ada L.")
    assert out == "Revised text"
    assert all(s in sent[-1] for s in ("Old letter", "Shorter, mention dbt", "Sign as Ada L.", "cover letter"))
    assert "{" + "current}" not in sent[-1] and "{" + "feedback}" not in sent[-1]
    llm.complete = lambda prompt, **kw: ""
    try:
        revise_document(cand, offer, "cold-email", "x", "y")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    print("writer ok")
