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
    Collect job offers using Google Custom Search API.
    Returns OfferRaw list (deduped by URL), filtered to likely job postings.
    """

    # Detect if user specifically wants internships
    is_internship_request = any(w in query.lower() for w in ["stage", "intern", "stagiaire", "apprenticeship", "alternance"])
    
    if is_internship_request:
        q = f'{query} {location} (intern OR internship OR stage OR stagiaire OR apprenticeship OR alternance)'
    else:
        # General job search: remove strict quotes to be more flexible
        # Add "hiring" and "career" to find actual postings
        q = f'{query} {location} (job OR hiring OR opening OR career OR recruitment)'

    items: List[OfferRaw] = []
    seen_urls = set()

    remaining = max(1, limit)
    start = 1

    if not settings.GOOGLE_API_KEY or not settings.GOOGLE_CSE_ID:
        raise RuntimeError("Web search needs GOOGLE_API_KEY and GOOGLE_CSE_ID in .env")

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

            # Must be internship ONLY if specifically requested
            if is_internship_request and not _is_internship(title, snippet, link):
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
    """Fallback when API quota is dead. Generates dynamic mock data from query."""
    logger.warning(f"Using Query-Injected Mock Data for: {query}")
    
    # Try to extract location if not provided
    q_lower = query.lower()
    
    # Dynamic titles based on query
    keywords = [w.capitalize() for w in query.split() if len(w) > 3]
    main_kw = keywords[0] if keywords else "Software"
    
    defaults = [
        {"title": f"Senior {main_kw} Specialist", "company": "GlobalTech", "location": "Paris"},
        {"title": f"{main_kw} Associate", "company": "Innovate AI", "location": "Remote"},
        {"title": f"Lead {main_kw} Developer", "company": "DataFlow", "location": "Lyon"},
        {"title": f"{main_kw} Internship", "company": "Startup Hub", "location": "Paris"},
        {"title": f"Consultant {main_kw}", "company": "Advisory Corp", "location": "London"},
    ]
    
    out = []
    for i, d in enumerate(defaults):
        if i >= limit: break
        out.append(OfferRaw(
            source="mock_fallback",
            title=d["title"],
            company=d["company"],
            location=d["location"],
            description=(
                f"We are looking for a {d['title']} at {d['company']}. "
                f"MISSIONS: Development of {main_kw} systems, deployment with Docker/Kubernetes, and performance optimization. "
                f"REQUIREMENTS: Expertise in {main_kw}, mastery of Python/SQL, and at least 2 years of relevant experience. "
                f"BENEFITS: Competitive salary, remote work options, and health insurance."
            ),
            url=f"https://mock-job-results.com/{i}?q={query.replace(' ', '+')}",
        ))
    return out
