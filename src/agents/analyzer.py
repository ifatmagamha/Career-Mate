# src/agents/analyzer.py
from __future__ import annotations

import re
from typing import Any, Dict, List

from src.config.logging import logger
from src.config.settings import settings
from src.llm.gemini_client import llm, extract_json_dict
from src.schemas.job_offer import OfferRaw, OfferAnalyzed
from src.utils.prompts import load_prompt





# --- Normalizers to match YOUR enums (strict) ---
def _norm_contract_type(v: Any) -> str:
    t = str(v or "").strip().lower()
    if t in {"internship", "stage"}:
        return "internship"
    if t in {"apprenticeship", "alternance"}:
        return "apprenticeship"
    if t in {"part_time", "part-time", "temps partiel"}:
        return "part_time"
    if t in {"full_time", "full-time", "temps plein", "cdi"}:
        return "full_time"
    if t in {"freelance", "contractor"}:
        return "freelance"
    return "unknown"


def _norm_seniority(v: Any) -> str:
    s = str(v or "").strip().lower()

    # your schema is strict: only intern/junior/unknown
    if s in {"intern", "internship", "stage", "stagiaire"}:
        return "intern"
    if s in {"junior", "entry", "entry-level", "graduate"}:
        return "junior"
    return "unknown"


COMMON_SKILLS = [
    "Python", "SQL", "Pandas", "NumPy", "Scikit-learn", "TensorFlow", "PyTorch",
    "Machine Learning", "Deep Learning", "NLP", "LLM", "RAG",
    "Power BI", "Tableau", "Spark", "Airflow", "Docker", "Kubernetes",
    "Git", "AWS", "GCP", "Azure", "BigQuery", "Snowflake",
    "Statistics", "A/B Testing", "ETL", "Data Engineering"
]


def _extract_skills_heuristic(text: str) -> List[str]:
    low = text.lower()
    out, seen = [], set()
    for s in COMMON_SKILLS:
        if s.lower() in low and s not in seen:
            out.append(s)
            seen.add(s)
    return out


def heuristic_analyze_offer(offer: OfferRaw) -> OfferAnalyzed:
    """Fallback: 0 hallucination, works without LLM."""
    text = f"{offer.title}\n{offer.description or ''}"

    # internship-only pipeline => mostly intern
    contract_type = "internship" if any(k in text.lower() for k in ["stage", "intern"]) else "unknown"
    seniority = "intern" if "intern" in text.lower() or "stage" in text.lower() else "unknown"

    skills = _extract_skills_heuristic(text)
    keywords = list(dict.fromkeys([w.lower() for w in re.findall(r"[A-Za-z][A-Za-z+\-]{2,}", text)][:25]))

    return OfferAnalyzed(
        url=offer.url,
        title=offer.title,
        company=offer.company,
        location=offer.location,
        contract_type=contract_type,
        seniority=seniority,
        skills=skills,
        missions=[],
        requirements=[],
        keywords=keywords,
        summary=None,
    )


def analyze_offer_llm(offer: OfferRaw) -> OfferAnalyzed:
    """
    LLM analyzer but validated safely:
    - parse JSON dict first (no schema crash)
    - force trusted fields from OfferRaw
    - normalize enums to your strict schema
    """
    prompt_template = load_prompt("analyzer")
    prompt = prompt_template.replace("{raw_text}", f"Title: {offer.title}\nCompany: {offer.company}\nLocation: {offer.location}\nDescription: {offer.description or ''}")

    logger.info(f"[analyzer] Using SMART model: {settings.GEMINI_MODEL_SMART}")
    text = llm.generate_text(prompt, model=settings.GEMINI_MODEL_SMART, temperature=0.1, max_output_tokens=650)
    data: Dict[str, Any] = extract_json_dict(text)

    # Force trusted fields (prevents missing url + prevents LLM from changing them)
    data["url"] = str(offer.url)
    data["title"] = offer.title
    data["company"] = offer.company
    data["location"] = offer.location

    # Normalize enums to YOUR allowed values
    data["contract_type"] = _norm_contract_type(data.get("contract_type"))
    data["seniority"] = _norm_seniority(data.get("seniority"))

    # Ensure lists
    for k in ["skills", "missions", "requirements", "keywords"]:
        if not isinstance(data.get(k), list):
            data[k] = []
    if not isinstance(data.get("summary"), (str, type(None))):
        data["summary"] = None

    # Anti-hallucination: if snippet is short, forbid long fabricated content
    snippet_len = len((offer.description or "").strip())
    if snippet_len < 160:
        data["missions"] = []
        data["requirements"] = []
        data["summary"] = None

    # If skills empty, use heuristic to help matcher
    if not data["skills"]:
        data["skills"] = _extract_skills_heuristic(f"{offer.title}\n{offer.description or ''}")

    return OfferAnalyzed.model_validate(data)


def analyze_offers(offers: List[OfferRaw], *, llm_max: int = 3) -> List[OfferAnalyzed]:
    """
    Analyze a batch of offers.
    - First llm_max offers: try LLM (better extraction)
    - The rest: heuristic only (prevents quota issues)
    - Always fallback to heuristic if LLM fails
    """
    logger.info(f"[analyzer] analyzing {len(offers)} offers (llm_max={llm_max})")
    analyzed: List[OfferAnalyzed] = []

    for i, offer in enumerate(offers, start=1):
        try:
            if i <= llm_max:
                result = analyze_offer_llm(offer)
            else:
                result = heuristic_analyze_offer(offer)

            analyzed.append(result)
            logger.info(f"[analyzer] ✔ {i}. {offer.title}")
        except Exception as e:
            logger.warning(f"[analyzer] ✖ {i}. failed title='{offer.title}' err={e}")
            # last-resort: do not break the pipeline
            analyzed.append(heuristic_analyze_offer(offer))
            logger.info(f"[analyzer] ↪ fallback heuristic ✔ {i}. {offer.title}")

    return analyzed
