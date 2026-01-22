# src/utils/http.py
from __future__ import annotations

import time
from typing import Any, Dict, Optional

import requests
from requests import Response
from src.config.logging import logger
from src.config.settings import settings


def get_json(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    *,
    timeout_s: int | None = None,
    retries: int = 3,
    backoff_s: float = 0.8,
) -> Dict[str, Any]:
    """
    GET JSON with retry/backoff. Raises RuntimeError on failure.
    """
    timeout = timeout_s or settings.HTTP_TIMEOUT_S
    last_err: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            resp: Response = requests.get(url, params=params, headers=headers, timeout=timeout)
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            return resp.json()
        except Exception as e:
            last_err = e
            logger.warning(f"[http] GET failed (attempt {attempt}/{retries}) url={url} err={e}")
            if attempt < retries:
                time.sleep(backoff_s * attempt)

    raise RuntimeError(f"GET JSON failed after {retries} retries: {last_err}")
