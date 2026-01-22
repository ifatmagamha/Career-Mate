# src/agents/analyzer.py
from __future__ import annotations

from typing import List, Optional, Any, Dict

from pydantic import BaseModel, Field

from src.config.logging import logger
from src.llm.gemini_client import llm
from src.schemas.job_offer import OfferRaw, OfferAnalyzed, ContractType, Seniority

# RAG is optional: if it fails, analyzer still works
try:
    from src.rag.pipeline import build_rag_context
except Exception:  # pragma: no cover
    build_rag_context = None


# -------------------------------------------------------------------
# 1) Permissive schema for LLM output (avoid strict Literal failures)
# -------------------------------------------------------------------
class OfferAnalyzedLLM(BaseModel):
    # url optional here -> we will force it from OfferRaw
    url: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None

    contract_type: Optional[str] = "unknown"
    seniority: Optional[str] = "unknown"

    skills: List[str] = Field(default_factory=list)
    missions: List[str] = Field(default_factory=list)
    requirements: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)

    summary: Optional[str] = None


ANALYZER_SYSTEM_PROMPT = """
You are an information extraction system.
Extract structured information from the job offer text.

STRICT RULES:
- Output ONLY a valid JSON object (no markdown, no extra keys)
- Do NOT invent information
- Use ONLY the provided text + RAG context
- If missing, use "unknown" or empty lists []
- Skills must be short and normalized (e.g. "Python", "SQL", "Machine Learning")

IMPORTANT ENUMS:
- contract_type must be one of: internship, full_time, part_time, apprenticeship, freelance, unknown
- seniority must be one of: intern, junior, unknown

Return a JSON matching exactly the provided schema.
""".strip()


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _safe_str(x: Optional[str]) -> str:
    return (x or "").strip()


def _build_query(offer: OfferRaw) -> str:
    parts = [_safe_str(offer.title), _safe_str(offer.company), _safe_str(offer.location)]
    return " ".join([p for p in parts if p])


def _normalize_contract(x: Optional[str]) -> ContractType:
    if not x:
        return "unknown"
    v = x.strip().lower()

    mapping = {
        # internships
        "intern": "internship",
        "internship": "internship",
        "stage": "internship",
        "stagiaire": "internship",
        # apprenticeship
        "alternance": "apprenticeship",
        "apprenticeship": "apprenticeship",
        # full time
        "full-time": "full_time",
        "full time": "full_time",
        "full_time": "full_time",
        "cdi": "full_time",
        "cdd": "full_time",
        # part time
        "part-time": "part_time",
        "part time": "part_time",
        "part_time": "part_time",
        # freelance
        "freelance": "freelance",
    }
    return mapping.get(v, "unknown")


def _normalize_seniority(x: Optional[str]) -> Seniority:
    if not x:
        return "unknown"
    v = x.strip().lower()

    mapping = {
        "intern": "intern",
        "internship": "intern",
        "stage": "intern",
        "stagiaire": "intern",
        "junior": "junior",
        "entry": "junior",
        "entry level": "junior",
        "entry-level": "junior",
    }
    # everything else (mid/senior/etc) => unknown
    return mapping.get(v, "unknown")


def _build_rag_block(offer: OfferRaw) -> str:
    if build_rag_context is None:
        return ""

    query = _build_query(offer)
    url = str(offer.url)

    blocks: List[str] = []
    for focus in ("skills", "missions", "requirements"):
        try:
            res = build_rag_context(url, query, focus)
            if getattr(res, "ok", False) and getattr(res, "text", ""):
                txt = str(res.text).strip()
                if txt:
                    blocks.append(f"[{focus.upper()} CONTEXT]\n{txt}")
        except Exception as e:
            logger.warning(f"[rag] build_rag_context failed focus={focus} url={url} err={e}")

    return "\n\n".join(blocks).strip()


# -------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------
def analyze_offer(offer: OfferRaw) -> OfferAnalyzed:
    """
    Analyze a single OfferRaw and return OfferAnalyzed.
    IMPORTANT: We do NOT ask the LLM to directly output OfferAnalyzed (too strict).
    We ask for OfferAnalyzedLLM then normalize + validate to OfferAnalyzed.
    """
    rag_block = _build_rag_block(offer)

    prompt = f"""
{ANALYZER_SYSTEM_PROMPT}

JOB OFFER (snippet):
Title: {_safe_str(offer.title) or "unknown"}
Company: {_safe_str(offer.company) or "unknown"}
Location: {_safe_str(offer.location) or "unknown"}
Snippet:
{_safe_str(offer.description)}

RAG CONTEXT (from the job page, may be partial):
{rag_block if rag_block else "[NO RAG CONTEXT AVAILABLE]"}
""".strip()

    # ✅ KEY FIX: schema=OfferAnalyzedLLM (NOT OfferAnalyzed)
    llm_out: OfferAnalyzedLLM = llm.generate_json(
        prompt=prompt,
        schema=OfferAnalyzedLLM,
        temperature=0.1,
        max_output_tokens=900,
    )

    data: Dict[str, Any] = llm_out.model_dump()

    # Force these fields from OfferRaw (LLM must not change them)
    data["url"] = str(offer.url)
    data["title"] = offer.title
    data["company"] = offer.company
    data["location"] = offer.location

    # Normalize enums (avoid Literal crash)
    data["contract_type"] = _normalize_contract(data.get("contract_type"))
    data["seniority"] = _normalize_seniority(data.get("seniority"))

    # Final strict validation
    return OfferAnalyzed.model_validate(data)


def analyze_offers(offers: List[OfferRaw]) -> List[OfferAnalyzed]:
    logger.info(f"[analyzer] analyzing {len(offers)} offers")

    analyzed: List[OfferAnalyzed] = []
    for i, offer in enumerate(offers, start=1):
        try:
            result = analyze_offer(offer)
            analyzed.append(result)
            logger.info(f"[analyzer] ✔ {i}. {offer.title}")
        except Exception as e:
            logger.warning(f"[analyzer] ✖ {i}. failed title='{offer.title}' err={e}")

    return analyzed
