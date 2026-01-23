from pathlib import Path
from typing import Dict, Any, Tuple, List

from src.config.settings import settings
from src.export.pdf import render_structured_pdf
from src.llm.gemini_client import llm, extract_json_dict
from src.schemas.candidate import CandidateProfile
from src.schemas.job_offer import OfferAnalyzed


def _clip(text: str, n: int = 8000) -> str:
    return (text or "").strip()[:n]


def _safe_list(x) -> List[str]:
    if isinstance(x, list):
        return [str(i).strip() for i in x if str(i).strip()]
    return []


def _fallback_structured_cv(candidate: CandidateProfile, offer: OfferAnalyzed) -> Dict[str, Any]:
    # deterministic, no hallucinations
    return {
        "header": {
            "name": candidate.full_name,
            "email": candidate.email,
            "phone": candidate.phone or "À compléter",
            "location": candidate.location,
        },
        "title": f"Candidature — {offer.title}",
        "summary": [
            "Profil à compléter (fallback).",
            "Objectif : stage ciblé en lien avec l’offre.",
        ],
        "skills": _safe_list(offer.skills)[:10],
        "experience": [
            "À compléter : expériences/projets depuis le CV brut.",
        ],
        "projects": [
            "À compléter : projets pertinents depuis le CV brut.",
        ],
        "education": [
            "À compléter : formation depuis le CV brut.",
        ],
        "languages": [
            "À compléter : langues.",
        ],
        "certifications": [],
        "links": [],
    }


def _fallback_letter(candidate: CandidateProfile, offer: OfferAnalyzed) -> Dict[str, Any]:
    return {
        "subject": f"Candidature – {offer.title}",
        "body": [
            "Madame, Monsieur,",
            "",
            f"Je vous adresse ma candidature pour le poste de {offer.title} au sein de {offer.company or 'votre entreprise'}.",
            "Mon parcours et mes compétences (décrites dans mon CV) m’ont permis de développer une base solide et une forte motivation pour contribuer à vos missions.",
            "",
            "Je serais ravi(e) d’échanger avec vous lors d’un entretien.",
            "",
            f"Cordialement,",
            f"{candidate.full_name}",
        ]
    }


def generate_structured_cv(candidate: CandidateProfile, offer: OfferAnalyzed) -> Dict[str, Any]:
    """
    Returns a STRICT JSON structure for a full CV, grounded in candidate.cv_text.
    No invention allowed; if missing -> 'À compléter'.
    """
    cv_raw = _clip(candidate.cv_text, 9000)

    prompt = f"""
Tu es un assistant RH expert ATS.
Tu dois produire un CV COMPLET, bien structuré et ciblé pour l'offre.

RÈGLES ANTI-HALLUCINATION (STRICTES) :
- Tu n'as le droit d'utiliser QUE des informations présentes dans le CV brut.
- Interdit d'inventer : entreprises, dates, diplômes, projets, outils, réalisations.
- Si une info est manquante, mets exactement: "À compléter".
- Tu peux réécrire/structurer, mais sans ajouter de nouveaux faits.

SORTIE :
- Retourne UNIQUEMENT un JSON valide (pas de markdown).
- Le JSON doit contenir exactement ces clés :

{{
  "header": {{
    "name": "...",
    "email": "...",
    "phone": "...",
    "location": "...",
    "links": ["..."]
  }},
  "title": "Candidature — <titre du poste>",
  "summary": ["...", "..."],
  "skills": ["...", "..."],
  "experience": ["- ...", "- ..."],
  "projects": ["- ...", "- ..."],
  "education": ["- ...", "- ..."],
  "languages": ["- ...", "- ..."],
  "certifications": ["- ..."],
  "keywords_aligned": ["...","..."]
}}

CONTRAINTES DE STYLE :
- experience/projects/education/languages : éléments en bullets (préfixe "- ")
- skills : 8 à 14 items max
- keywords_aligned : 8 à 12 mots max, issus de l'offre

OFFRE (structurée) :
Titre: {offer.title}
Entreprise: {offer.company or "unknown"}
Lieu: {offer.location or "unknown"}
Compétences: {offer.skills}
Missions: {offer.missions}
Exigences: {offer.requirements}
Keywords: {offer.keywords}
Résumé: {offer.summary or "unknown"}

CV BRUT :
{cv_raw}
""".strip()

    try:
        text = llm.generate_text(prompt, temperature=0.2, max_output_tokens=1400) or ""
        data = extract_json_dict(text)

        # minimal safety defaults
        data.setdefault("header", {})
        data["header"].setdefault("name", candidate.full_name)
        data["header"].setdefault("email", candidate.email)
        data["header"].setdefault("phone", candidate.phone or "À compléter")
        data["header"].setdefault("location", candidate.location)
        data["header"].setdefault("links", [])

        for k in ["summary", "skills", "experience", "projects", "education", "languages", "certifications", "keywords_aligned"]:
            if k not in data or not isinstance(data[k], list):
                data[k] = []

        if not data.get("title"):
            data["title"] = f"Candidature — {offer.title}"

        return data
    except Exception:
        return _fallback_structured_cv(candidate, offer)


def generate_structured_letter(candidate: CandidateProfile, offer: OfferAnalyzed) -> Dict[str, Any]:
    """
    Returns a structured letter (subject + lines), grounded in CV raw.
    """
    cv_raw = _clip(candidate.cv_text, 7000)

    prompt = f"""
Tu es un assistant RH.
Rédige une lettre de motivation EN FRANÇAIS, ciblée pour l'offre.

RÈGLES STRICTES :
- Ne pas inventer d'expériences/projets/diplômes.
- Utiliser uniquement ce qui est présent dans le CV brut.
- 180 à 260 mots environ.
- Ton pro, simple, pas de blabla.

SORTIE (UNIQUEMENT JSON) :
{{
  "subject": "...",
  "body": ["ligne1", "ligne2", "..."]
}}

OFFRE :
Titre: {offer.title}
Entreprise: {offer.company or "unknown"}
Lieu: {offer.location or "unknown"}
Compétences: {offer.skills}
Missions: {offer.missions}
Exigences: {offer.requirements}

CV BRUT :
{cv_raw}
""".strip()

    try:
        text = llm.generate_text(prompt, temperature=0.3, max_output_tokens=900) or ""
        data = extract_json_dict(text)
        if not isinstance(data.get("body"), list):
            data["body"] = []
        if not data.get("subject"):
            data["subject"] = f"Candidature – {offer.title}"
        return data
    except Exception:
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


def generate_documents(candidate: CandidateProfile, offer: OfferAnalyzed) -> Tuple[str, str]:
    """
    Simpler wrapper that returns text content (Markdown-like) for UI use.
    Does not write PDFs locally (that is done by generate_cv_and_letter_pdfs).
    """
    cv_data = generate_structured_cv(candidate, offer)
    letter_data = generate_structured_letter(candidate, offer)
    
    # Convert JSON data to simple text representation for UI display/edit
    cv_text = f"TITLE: {cv_data.get('title')}\n\nSUMMARY:\n" + "\n".join(_safe_list(cv_data.get('summary')))
    cv_text += "\n\nSKILLS:\n" + ", ".join(_safe_list(cv_data.get('skills')))
    cv_text += "\n\nEXPERIENCE:\n" + "\n".join(_safe_list(cv_data.get('experience')))
    
    letter_text = f"SUBJECT: {letter_data.get('subject')}\n\n" + "\n".join(_safe_list(letter_data.get('body')))
    
    return cv_text, letter_text
