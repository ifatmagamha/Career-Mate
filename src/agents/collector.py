from __future__ import annotations

from typing import List, Optional
from urllib.parse import urlparse

from src.config.logging import logger
from src.config.settings import settings
from src.schemas.job_offer import OfferRaw
from src.utils.http import get_json


GOOGLE_CSE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"

# --- Filters: keep "job postings", remove discussions/listings/education pages ---
NON_JOB_HOST_CONTAINS = [
    "reddit.com",
    "wikipedia.org",
    "catalog-",  # university catalogs like catalog-2025-2026....
]

# pages that are usually NOT a single job posting
NON_POSTING_URL_CONTAINS = [
    "linkedin.com/jobs/",           # listing pages
    "glassdoor.com/Job/",           # listing pages
    "glassdoor.fr/Emploi/",         # listing pages
    "/search?",                     # listing/search pages
    "/search-page/",                # sometimes listings
    "/jobs/search",                 # listings
    "/careers/",                    # generic careers pages (sometimes OK, but too noisy for MVP)
    "careers/"                      # broad filter; keep ATS hints below to still allow real postings
]

# ATS / posting patterns
GOOD_JOB_URL_HINTS = [
    "/job/",
    "/jobs/",
    "myworkdayjobs.com",
    "greenhouse.io",
    "lever.co",
    "smartrecruiters.com",
    "ashbyhq.com",
]

# Internship-only signals (FR + EN)
INTERNSHIP_HINTS = [
    "stage",
    "intern",
    "internship",
    "stagiaire",
    "apprenticeship",   # optionnel : si tu veux aussi alternance, garde-le
    "alternance",       # optionnel : si tu veux aussi alternance, garde-le
]


def _looks_like_login_or_gate(title: str, snippet: str, url: str) -> bool:
    text = f"{title} {snippet} {url}".lower()
    bad_signals = [
        "sign in", "connexion", "log in", "s'identifier", "accounts",
        "create an account", "captcha", "robot", "enable cookies",
    ]
    if "indeed.com" in text and ("sign in" in text or "accounts" in text):
        return True
    return any(s in text for s in bad_signals)


def _extract_company_from_display_link(display_link: Optional[str]) -> Optional[str]:
    if not display_link:
        return None
    host = display_link.strip().lower().replace("www.", "")
    return host or None


def _is_internship(title: str, snippet: str, link: str) -> bool:
    text = f"{title} {snippet} {link}".lower()
    return any(h in text for h in INTERNSHIP_HINTS)


def _is_probably_job_posting(link: str) -> bool:
    host = (urlparse(link).netloc or "").lower()
    u = link.lower()

    # hard reject: reddit, wikipedia, catalogs, etc.
    if any(bad in host for bad in NON_JOB_HOST_CONTAINS):
        return False

    # reject listing/search pages
    if any(bad in u for bad in NON_POSTING_URL_CONTAINS):
        # BUT allow ATS posting URLs even if they contain /careers/
        if any(g in u for g in GOOD_JOB_URL_HINTS):
            return True
        return False

    # accept: common ATS / careers patterns
    if any(g in u for g in GOOD_JOB_URL_HINTS):
        return True

    # fallback: if URL path contains something like /jobs/12345 etc.
    path = (urlparse(link).path or "").lower()
    if "/job" in path or "/jobs" in path:
        return True

    return False


def collect_offers(query: str, location: str, limit: int = 10) -> List[OfferRaw]:
    """
    Collect ONLY internship offers using Google Custom Search API.
    Returns OfferRaw list (deduped by URL), filtered to likely job postings.
    """

    # Internship-only query
    q = f'{query} {location} (stage OR internship OR intern OR stagiaire)'

    items: List[OfferRaw] = []
    seen_urls = set()

    remaining = max(1, limit)
    start = 1

    logger.info(f"[collector] query='{query}' location='{location}' limit={limit}")

    while remaining > 0:
        num = 10 if remaining > 10 else remaining
        params = {
            "key": settings.GOOGLE_API_KEY,
            "cx": settings.GOOGLE_CSE_ID,
            "q": q,
            "num": num,
            "start": start,
        }

        try:
            data = get_json(GOOGLE_CSE_ENDPOINT, params=params)
        except Exception as e:
            msg = str(e).lower()
            if "403" in msg or "forbidden" in msg:
                logger.warning(f"[collector] Google Search quota exceeded (403). Using mock data.")
                return _get_mock_failed_search_offers(query, limit)
            logger.error(f"[collector] Search error: {e}")
            break
        results = data.get("items", []) or []
        if not results:
            break

        for it in results:
            title = (it.get("title") or "").strip()
            link = (it.get("link") or "").strip()
            snippet = (it.get("snippet") or "").strip()
            display_link = (it.get("displayLink") or "").strip()

            if not link or link in seen_urls:
                continue

            # Filter out login/gate pages
            if _looks_like_login_or_gate(title, snippet, link):
                continue

            # Must be internship (title/snippet/url)
            if not _is_internship(title, snippet, link):
                continue

            # Must look like a job posting
            if not _is_probably_job_posting(link):
                continue

            company_guess = None
            pagemap = it.get("pagemap") or {}
            metatags = (pagemap.get("metatags") or [{}])
            if metatags and isinstance(metatags, list) and metatags:
                mt = metatags[0] or {}
                company_guess = mt.get("og:site_name") or mt.get("twitter:site") or None

            if not company_guess:
                company_guess = _extract_company_from_display_link(display_link)

            # If "company" looks like a URL, discard it
            if company_guess and "http" in str(company_guess).lower():
                company_guess = None

            offer = OfferRaw(
                source="google_cse",
                title=title,
                company=company_guess,
                location=location,
                description=snippet,
                url=link,
            )
            items.append(offer)
            seen_urls.add(link)

            if len(items) >= limit:
                break

        if len(items) >= limit:
            break

        remaining = limit - len(items)
        start += num

    logger.info(f"[collector] collected={len(items)}")
    return items


def _get_mock_failed_search_offers(query: str, limit: int) -> List[OfferRaw]:
    """Fallback when API quota is dead."""
    logger.warning("Returning 5 mock offers for demo purposes.")
    defaults = [
        {"title": "Python Developer Intern", "company": "TechCorp", "location": "Paris"},
        {"title": "Data Scientist Internship", "company": "AI Solutions", "location": "Remote"},
        {"title": "Backend Engineering Intern", "company": "CloudSystems", "location": "Lyon"},
        {"title": "Full Stack Intern (React/Django)", "company": "WebAgency", "location": "Paris"},
        {"title": "Machine Learning Intern", "company": "DeepMind-ish", "location": "London"},
    ]
    
    out = []
    for i, d in enumerate(defaults):
        if i >= limit: break
        out.append(OfferRaw(
            source="mock_fallback",
            title=d["title"],
            company=d["company"],
            location=d["location"],
            description=f"Mock description for {d['title']}. Requires Python, Docker, RAG skills.",
            url=f"https://mock-job.com/{i}",
        ))
    return out
