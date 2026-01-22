# src/agents/collector.py
from __future__ import annotations

from typing import List, Optional
from urllib.parse import urlparse

from src.config.logging import logger
from src.config.settings import settings
from src.schemas.job_offer import OfferRaw
from src.utils.http import get_json


GOOGLE_CSE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"

# hard reject sources
NON_JOB_HOST_CONTAINS = [
    "reddit.com",
    "wikipedia.org",
    "catalog-",  # university catalogs
]

# listing/search pages (not a single job)
NON_POSTING_URL_CONTAINS = [
    "linkedin.com/jobs/",           # LinkedIn listings (we will allow /jobs/view/ below)
    "glassdoor.com/Job/",           # Glassdoor listing pages
    "glassdoor.fr/Emploi/",         # Glassdoor listing pages
    "/search?",                     # generic search pages
    "/jobs/search",                 # generic job searches
    "/search-page/",                # often listings
]

# real job posting patterns / ATS
GOOD_POSTING_HINTS = [
    "/job/",
    "/jobs/",
    "/position/",
    "/vacancies/",
    "myworkdayjobs.com",
    "greenhouse.io",
    "lever.co",
    "smartrecruiters.com",
    "ashbyhq.com",
    "teamtailor.com",
]

# internship signals
INTERNSHIP_HINTS = [
    "stage",
    "intern",
    "internship",
    "stagiaire",
    # optional (keep if you want alternance too)
    "alternance",
    "apprenticeship",
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

    # hard reject: reddit, wikipedia, catalogs...
    if any(bad in host for bad in NON_JOB_HOST_CONTAINS):
        return False

    # LinkedIn special rule:
    # allow ONLY real job pages: /jobs/view/...
    if "linkedin.com" in host:
        return "/jobs/view/" in u

    # Glassdoor special rule:
    # block listing pages; allow only when it looks like a direct posting (rare)
    if "glassdoor." in host:
        if "/job/" in u or "/Job/" in link:
            return False
        # if you want to fully exclude glassdoor for MVP:
        return False

    # reject known listing/search pages (unless ATS/posting hint says it's a real posting)
    if any(bad in u for bad in NON_POSTING_URL_CONTAINS):
        if any(g in u for g in GOOD_POSTING_HINTS):
            return True
        return False

    # accept ATS patterns
    if any(g in u for g in GOOD_POSTING_HINTS):
        return True

    # fallback: path contains /jobs/123 or /job/123
    path = (urlparse(link).path or "").lower()
    if "/job" in path or "/jobs" in path:
        return True

    return False


def collect_offers(query: str, location: str, limit: int = 10) -> List[OfferRaw]:
    """
    Collect ONLY internship offers using Google Custom Search API.
    Returns OfferRaw list (deduped by URL), filtered to likely job postings.
    """

    # Internship-only query + exclude noisy sites (optional but recommended)
    q = (
        f'{query} {location} (stage OR internship OR intern OR stagiaire) '
        f'-site:reddit.com -site:wikipedia.org -site:glassdoor.com'
    )

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

        data = get_json(GOOGLE_CSE_ENDPOINT, params=params)
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

            if _looks_like_login_or_gate(title, snippet, link):
                continue

            if not _is_internship(title, snippet, link):
                continue

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
