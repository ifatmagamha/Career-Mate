from __future__ import annotations

from urllib.parse import urlparse, parse_qs


def is_probably_listing_page(url: str) -> bool:
    """
    Detect pages that are not a single job offer (search/list pages).
    Works decently for Indeed/LinkedIn/Google results etc.
    """
    u = url.lower()
    parsed = urlparse(u)
    path = parsed.path or ""
    qs = parse_qs(parsed.query)

    # Indeed: listing/search pages often include /jobs or /emplois with q/l params
    if "indeed." in parsed.netloc:
        if path.endswith("/jobs") or "/jobs" in path:
            # viewjob pages usually have jk= in query
            if "jk" not in qs:
                return True
        if "viewjob" not in path and "jk" not in qs and ("q" in qs or "l" in qs):
            return True

    # LinkedIn: /jobs/search is listing; job view often contains /jobs/view/
    if "linkedin." in parsed.netloc:
        if "/jobs/search" in path:
            return True
        if "/jobs/view" not in path and "currentJobId" not in qs:
            # many linkedin urls without /view are not direct job pages
            return True

    # Generic listing hints
    listing_markers = [
        "/search", "/recherche", "/jobs/search", "/results", "/emplois", "/jobsearch",
        "q=", "query=", "search?",
    ]
    # Heuristic: if path looks like search and has query params, likely listing
    if any(m in u for m in listing_markers) and len(qs) > 0:
        return True

    return False
