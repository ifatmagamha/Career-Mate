from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import requests


def html_to_text(html: str) -> str:
    # remove scripts/styles
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    # remove tags
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    # decode common entities (minimal)
    html = html.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
    # normalize whitespace
    html = re.sub(r"\s+", " ", html).strip()
    return html


@dataclass
class WebFetcher:
    timeout: int = 20
    user_agent: str = "Mozilla/5.0 (RecruitAI/1.0; +https://example.com)"

    def fetch_text(self, url: str) -> Optional[str]:
        try:
            r = requests.get(
                url,
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout,
                allow_redirects=True,
            )
            if r.status_code >= 400:
                return None
            return html_to_text(r.text)
        except Exception:
            return None
