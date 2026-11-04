# src/agents/capture.py
"""
Capture d'une offre : lien (ou texte collé) -> fiche offre.

1. JSON-LD schema.org/JobPosting si la page en contient (WTTJ, Greenhouse, Lever, Workday...)
2. Texte de la page -> Gemini complète les champs manquants (compétences, missions, résumé...)
Les champs JSON-LD priment sur ceux du LLM.
"""
from __future__ import annotations

import html as html_lib
import json
import re
import uuid
from typing import Any, Dict, Optional, get_args

import requests
from bs4 import BeautifulSoup

from src.config.logging import logger
from src.config.settings import settings
from src.llm.port import llm, prompt_version
from src.schemas.job_offer import OfferSheet, SheetContract, SheetRemote, SheetSeniority

MAX_TEXT_CHARS = 15000
MIN_TEXT_CHARS = 200
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

_EMPLOYMENT_TYPES = {
    "FULL_TIME": "permanent",
    "PART_TIME": "part_time",
    "INTERN": "internship",
    "CONTRACTOR": "freelance",
    "TEMPORARY": "fixed_term",
}


class CaptureError(Exception):
    """Page illisible (login wall, page vide...) : l'utilisateur doit coller le texte."""


def fetch_html(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=settings.HTTP_TIMEOUT_S)
    if resp.status_code >= 400:
        raise CaptureError(f"HTTP {resp.status_code} en récupérant la page")
    return resp.text


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "svg"]):
        tag.decompose()
    text = soup.get_text("\n")
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def _iter_jsonld(node: Any):
    if isinstance(node, list):
        for n in node:
            yield from _iter_jsonld(n)
    elif isinstance(node, dict):
        yield node
        yield from _iter_jsonld(node.get("@graph", []))


def find_job_posting(html: str) -> Optional[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "", strict=False)
        except ValueError:
            continue
        for node in _iter_jsonld(data):
            types = node.get("@type")
            if types == "JobPosting" or (isinstance(types, list) and "JobPosting" in types):
                return node
    return None


def _first(v: Any) -> Any:
    return v[0] if isinstance(v, list) and v else v


def job_posting_to_fields(jp: Dict[str, Any]) -> Dict[str, Any]:
    """Map schema.org JobPosting -> champs de OfferSheet (+ description texte)."""
    org = _first(jp.get("hiringOrganization"))
    company = org.get("name") if isinstance(org, dict) else org

    location = None
    if jp.get("jobLocationType") == "TELECOMMUTE":
        location = "Remote"
    loc = _first(jp.get("jobLocation"))
    if isinstance(loc, dict):
        addr = loc.get("address")
        if isinstance(addr, dict):
            country = addr.get("addressCountry")
            country = country.get("name") if isinstance(country, dict) else country
            location = ", ".join(p for p in (addr.get("addressLocality"), country) if p) or location
        elif isinstance(addr, str):
            location = addr

    emp = _first(jp.get("employmentType"))
    contract = _EMPLOYMENT_TYPES.get(str(emp).upper().replace("-", "_")) if emp else None

    salary = None
    base = jp.get("baseSalary")
    if isinstance(base, dict):
        val = base.get("value")
        if isinstance(val, dict):
            lo, hi = val.get("minValue"), val.get("maxValue")
            amount = f"{lo}–{hi}" if lo and hi else (lo or hi or val.get("value"))
            unit = val.get("unitText")
        else:
            amount, unit = val, None
        if amount:
            salary = " ".join(str(p) for p in (amount, base.get("currency"), f"/ {unit.lower()}" if unit else None) if p)

    skills = jp.get("skills") or []
    if isinstance(skills, str):
        skills = [s.strip() for s in re.split(r"[,;\n]", skills) if s.strip()]

    desc = jp.get("description") or ""
    return {
        "title": jp.get("title"),
        "company": company,
        "location": location,
        "remote_policy": "remote" if jp.get("jobLocationType") == "TELECOMMUTE" else None,
        "contract_type": contract,
        "salary": salary,
        "deadline": (jp.get("validThrough") or "")[:10] or None,
        "skills": skills,
        "description": html_to_text(html_lib.unescape(desc)) if "<" in html_lib.unescape(desc) else desc,
    }


_GREENHOUSE_RE = re.compile(r"https?://(?:job-)?boards(?:\.eu)?\.greenhouse\.io/([^/?#]+)/jobs/(\d+)")


def fetch_greenhouse(url: str) -> Optional[Dict[str, Any]]:
    """Greenhouse renders job pages client-side: use its public Job Board API instead."""
    m = _GREENHOUSE_RE.match(url)
    if not m:
        return None
    resp = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{m[1]}/jobs/{m[2]}", timeout=settings.HTTP_TIMEOUT_S)
    if resp.status_code >= 400:
        raise CaptureError(f"Offre Greenhouse introuvable (HTTP {resp.status_code})")
    j = resp.json()
    return {
        "title": j.get("title"),
        "company": j.get("company_name"),
        "location": (j.get("location") or {}).get("name"),
        "deadline": (j.get("application_deadline") or "")[:10] or None,
        "description": html_to_text(html_lib.unescape(j.get("content") or "")),
    }


EXTRACT_PROMPT = """You extract a structured job sheet from a job posting.
Return ONLY a JSON object with keys:
title, company, location, remote_policy, contract_type, seniority, salary, deadline,
skills, nice_to_have, missions, requirements, summary.

Rules:
- remote_policy: one of {remotes}. Use "unknown" unless the posting says it.
- contract_type: one of {contracts}. CDI=permanent, CDD=fixed_term, stage=internship, alternance=apprenticeship.
- seniority: one of {seniorities}. Use "unknown" unless the posting states a level or years of experience.
- salary: as written in the posting (with currency and period), else null. Never guess.
- deadline: application deadline as YYYY-MM-DD if stated, else null.
- skills: REQUIRED technical skills and tools, short normalized names (max 15).
- nice_to_have: skills marked as a plus, bonus, preferred or optional (max 10). Never repeat a required skill.
- missions: main responsibilities, short phrases (max 8).
- requirements: requirements and qualifications, short phrases (max 8).
- summary: 1-2 sentences, same language as the posting.
- Use only information present in the posting. Unknown -> null or [].

Already known (keep these values): {known}

Job posting:
\"\"\"
{text}
\"\"\"
"""


PROMPT_VERSION = prompt_version(EXTRACT_PROMPT)
_ENUMS = {"remote_policy": SheetRemote, "contract_type": SheetContract, "seniority": SheetSeniority}


def extract_sheet(text: str, known: Dict[str, Any], offer_id: Optional[str] = None) -> OfferSheet:
    prompt = EXTRACT_PROMPT.format(
        remotes=", ".join(get_args(SheetRemote)),
        contracts=", ".join(get_args(SheetContract)),
        seniorities=", ".join(get_args(SheetSeniority)),
        known=json.dumps({k: v for k, v in known.items() if v}, ensure_ascii=False),
        text=text[:MAX_TEXT_CHARS],
    )
    sheet = llm.structured(prompt, OfferSheet, role="extract", prompt_version=PROMPT_VERSION, offer_id=offer_id)

    # Values fixed by the page (ATS API / JSON-LD) win over LLM ones
    merged = sheet.model_dump()
    merged.update({k: v for k, v in known.items() if v and k in merged})
    for k, allowed in _ENUMS.items():
        if merged[k] not in get_args(allowed):
            merged[k] = "unknown"
    return OfferSheet.model_validate(merged)


def capture_offer(url: Optional[str] = None, text: Optional[str] = None) -> Dict[str, Any]:
    """Retourne les champs à enregistrer : fiche + url, raw_text, source, provenance."""
    text, known, source = collect(url, text)
    logger.info(f"[capture] source={source} chars={len(text)} url={url}")
    offer_id = str(uuid.uuid4())  # known before the LLM call, so llm_calls can be linked to the offer
    sheet = extract_sheet(text, known, offer_id)
    return {**sheet.model_dump(), "id": offer_id, "url": url, "raw_text": text, "source": source,
            "model": llm.config("extract").model, "prompt_version": PROMPT_VERSION}


def collect(url: Optional[str] = None, text: Optional[str] = None) -> tuple[str, Dict[str, Any], str]:
    """Deterministic part of the capture (no LLM): text to extract from, fields fixed by the page, source."""
    known: Dict[str, Any] = {}
    source = "paste"

    if not text:
        if not url:
            raise CaptureError("Fournis un lien ou le texte de l'offre")
        known = fetch_greenhouse(url) or {}
        if known:
            text = known.pop("description")
            source = "greenhouse"
        else:
            html = fetch_html(url)
            jp = find_job_posting(html)
            if jp:
                known = job_posting_to_fields(jp)
                text = known.pop("description") or html_to_text(html)
                source = "jsonld"
            else:
                text = html_to_text(html)
                source = "page"

    if len(text) < MIN_TEXT_CHARS:
        raise CaptureError("Page vide ou protégée (ex. LinkedIn) : colle le texte de l'offre")
    return text, known, source


if __name__ == "__main__":
    sample = """<html><head><script type="application/ld+json">
    {"@context":"https://schema.org","@graph":[{"@type":"Organization","name":"X"},
     {"@type":"JobPosting","title":"Data Engineer","hiringOrganization":{"@type":"Organization","name":"Acme"},
      "jobLocation":{"@type":"Place","address":{"addressLocality":"Paris","addressCountry":"FR"}},
      "employmentType":["FULL_TIME"],"validThrough":"2026-12-01T00:00:00Z","skills":"SQL, Airflow",
      "baseSalary":{"currency":"EUR","value":{"minValue":45000,"maxValue":55000,"unitText":"YEAR"}},
      "description":"&lt;p&gt;Build &lt;b&gt;pipelines&lt;/b&gt;&lt;/p&gt;"}]}
    </script></head><body>hello</body></html>"""
    jp = find_job_posting(sample)
    assert jp is not None
    f = job_posting_to_fields(jp)
    assert f["title"] == "Data Engineer" and f["company"] == "Acme", f
    assert f["location"] == "Paris, FR" and f["contract_type"] == "permanent", f
    assert f["deadline"] == "2026-12-01" and f["skills"] == ["SQL", "Airflow"], f
    assert f["salary"] == "45000–55000 EUR / year", f
    assert f["description"] == "Build \npipelines", repr(f["description"])
    assert find_job_posting("<html><body>no ld</body></html>") is None
    assert _GREENHOUSE_RE.match("https://job-boards.greenhouse.io/doctolib/jobs/7648796003").groups() == ("doctolib", "7648796003")
    assert _GREENHOUSE_RE.match("https://boards.eu.greenhouse.io/acme/jobs/42?gh_src=x")
    assert not _GREENHOUSE_RE.match("https://jobs.lever.co/acme/123")
    print("capture ok")
