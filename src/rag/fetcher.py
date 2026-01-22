# src/rag/fetcher.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict
import requests


@dataclass
class FetchResult:
    url: str
    ok: bool
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    text: Optional[str] = None        # for HTML/text
    raw_bytes: Optional[bytes] = None # for PDF/binary
    error: Optional[str] = None


DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Connection": "close",
}


def fetch_url(url: str, timeout: int = 15) -> FetchResult:
    """
    Fetch a URL and return HTML text or raw bytes (PDF).
    No exceptions raised: always returns FetchResult.
    """
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout, allow_redirects=True)
        ct = (resp.headers.get("Content-Type") or "").lower().strip()

        if resp.status_code >= 400:
            return FetchResult(
                url=url,
                ok=False,
                status_code=resp.status_code,
                content_type=ct or None,
                error=f"http_error_{resp.status_code}",
            )

        # PDF (or octet-stream)
        if "application/pdf" in ct or url.lower().endswith(".pdf"):
            return FetchResult(
                url=url,
                ok=True,
                status_code=resp.status_code,
                content_type=ct or "application/pdf",
                raw_bytes=resp.content,
            )

        # Default: treat as text/html
        # requests will guess encoding; keep safe fallback
        resp.encoding = resp.encoding or "utf-8"
        return FetchResult(
            url=url,
            ok=True,
            status_code=resp.status_code,
            content_type=ct or "text/html",
            text=resp.text,
        )

    except requests.exceptions.Timeout:
        return FetchResult(url=url, ok=False, error="timeout")
    except requests.exceptions.RequestException as e:
        return FetchResult(url=url, ok=False, error=f"request_error: {e}")
    except Exception as e:
        return FetchResult(url=url, ok=False, error=f"unexpected_error: {e}")
