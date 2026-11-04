from pathlib import Path
from typing import Dict, Any, Tuple, List

from src.config.settings import settings
from src.export.pdf import render_structured_pdf
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


def _fallback_structured_cv(candidate: CandidateProfile, offer: OfferAnalyzed) -> Dict[str, Any]:
    # generic fallback (English/French neutral or mixed)
    return {
        "header": {
            "name": candidate.full_name or "Unknown",
            "email": candidate.email,
            "phone": candidate.phone or "[Phone]",
            "location": candidate.location,
        },
        "title": f"Application — {offer.title}",
        "summary": ["Profile summary to be completed."],
        "skills": _safe_list(offer.skills)[:10],
        "experience": ["- Experience 1...", "- Experience 2..."],
        "projects": [],
        "education": [],
        "languages": [],
        "match_rationale": "Fallback mode: AI generation failed."
    }


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


def generate_structured_cv(candidate: CandidateProfile, offer: OfferAnalyzed) -> Dict[str, Any]:
    """
    Returns a STRICT JSON structure for a full CV, grounded in candidate.cv_text.
    """
    cv_raw = _clip(candidate.cv_text, 9000)

    prompt_template = load_prompt("writer_cv")
    # SAFE INJECTION: Avoid .format() because CV text has braces
    prompt = prompt_template.replace("{title}", offer.title) \
                           .replace("{company}", offer.company or "Unknown") \
                           .replace("{location}", offer.location or "Unknown") \
                           .replace("{skills}", ", ".join(_safe_list(offer.skills))) \
                           .replace("{missions}", ", ".join(_safe_list(offer.missions))) \
                           .replace("{cv_raw}", cv_raw)

    try:
        text = llm.complete(prompt, role="write", prompt_version=prompt_version(prompt_template), temperature=0.2) or ""
        data = extract_json(text)

        # minimal safety defaults
        data.setdefault("header", {})
        data["header"].setdefault("name", candidate.full_name)
        data["header"].setdefault("email", candidate.email)
        
        return data
    except Exception as e:
        print(f"Error generating CV: {e}")
        return _fallback_structured_cv(candidate, offer)


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
        print(f"Error generating Letter: {e}")
        return _fallback_letter(candidate, offer)


def generate_cv_and_letter_pdfs(
    user_id: str,
    candidate: CandidateProfile,
    offer: OfferAnalyzed,
) -> Tuple[Path, Path]:
    """
    Main API to call from Streamlit/graph:
    outputs:
      data/generated/{user_id}_cv.pdf
      data/generated/{user_id}_lettre.pdf
    """
    out_dir = Path(settings.DATA_DIR) / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)

    cv_data = generate_structured_cv(candidate, offer)
    letter_data = generate_structured_letter(candidate, offer)

    # Save debug json/text (useful)
    (out_dir / f"{user_id}_cv.json").write_text(str(cv_data), encoding="utf-8")
    (out_dir / f"{user_id}_lettre.json").write_text(str(letter_data), encoding="utf-8")

    # Build PDF blocks for CV
    header = cv_data.get("header", {})
    header_lines = [
        f"{header.get('name','À compléter')}",
        f"Email: {header.get('email','À compléter')}",
        f"Tél: {header.get('phone','À compléter')}",
        f"Localisation: {header.get('location','À compléter')}",
    ]
    links = header.get("links") or []
    if links:
        header_lines.append("Liens: " + " | ".join([str(x) for x in links]))

    blocks = [
        ("Coordonnées", header_lines),
        ("Titre", [cv_data.get("title", f"Candidature — {offer.title}")]),
        ("Profil", _safe_list(cv_data.get("summary")) or ["À compléter"]),
        ("Compétences", [f"- {s}" for s in _safe_list(cv_data.get("skills"))] or ["À compléter"]),
        ("Expériences", _safe_list(cv_data.get("experience")) or ["À compléter"]),
        ("Projets", _safe_list(cv_data.get("projects")) or ["À compléter"]),
        ("Formation", _safe_list(cv_data.get("education")) or ["À compléter"]),
        ("Langues", _safe_list(cv_data.get("languages")) or ["À compléter"]),
    ]

    certs = _safe_list(cv_data.get("certifications"))
    if certs:
        blocks.append(("Certifications", certs))

    kws = _safe_list(cv_data.get("keywords_aligned"))
    if kws:
        blocks.append(("Mots-clés alignés", [", ".join(kws)]))

    cv_pdf = out_dir / f"{user_id}_cv.pdf"
    letter_pdf = out_dir / f"{user_id}_lettre.pdf"

    render_structured_pdf(
        cv_pdf,
        title=f"CV — {offer.title}",
        blocks=blocks,
    )

    # Letter PDF blocks
    letter_lines = _safe_list(letter_data.get("body")) or ["À compléter"]
    render_structured_pdf(
        letter_pdf,
        title=f"Lettre de motivation — {offer.title}",
        blocks=[("Objet", [letter_data.get("subject", f"Candidature – {offer.title}")]),
                ("Lettre", letter_lines)],
    )


    return cv_pdf, letter_pdf


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
        cv_data = generate_structured_cv(candidate, offer)
        letter_data = generate_structured_letter(candidate, offer)
        return f"SUBJECT: {letter_data.get('subject')}\n\n" + "\n".join(_safe_list(letter_data.get('body')))
    elif doc_type == "cold-email":
        return generate_cold_email(candidate, offer, tone=extra)
    elif doc_type == "interview":
        return generate_interview_prep(candidate, offer, difficulty=extra)
    return "Unknown document type."
