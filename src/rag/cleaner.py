# src/rag/cleaner.py
from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup


_WS_RE = re.compile(r"[ \t]+")
_MANY_NL_RE = re.compile(r"\n{3,}")


# Markers that often start non-relevant sections (job lists, footer, cookies...)
CUT_MARKERS = [
    "\nJob Offers\n",
    "\nOther jobs\n",
    "\nOpen positions\n",
    "\nSimilar jobs\n",
    "\nMore jobs\n",
    "\nAll jobs\n",
    "\nPrivacy Policy\n",
    "\nCookie",
    "\nCookies",
    "\nTerms",
]


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WS_RE.sub(" ", text)

    # Trim each line and remove noise
    lines = [ln.strip() for ln in text.split("\n")]
    cleaned_lines = []
    for ln in lines:
        if not ln:
            continue
        if ln in {"|", "•", "-", "—"}:
            continue
        if len(ln) < 2:
            continue
        cleaned_lines.append(ln)

    text = "\n".join(cleaned_lines)
    text = _MANY_NL_RE.sub("\n\n", text).strip()
    return text


def _cut_noise_sections(text: str) -> str:
    """
    Cut text at the first occurrence of known noisy sections.
    """
    if not text:
        return text

    # Ensure markers work with surrounding newlines
    t = "\n" + text + "\n"

    cut_at = None
    for m in CUT_MARKERS:
        pos = t.lower().find(m.lower())
        if pos != -1:
            cut_at = pos if cut_at is None else min(cut_at, pos)

    if cut_at is None:
        return text

    # Remove leading newline we added
    trimmed = t[:cut_at].strip()
    return trimmed


def clean_html_to_text(html: str, url: Optional[str] = None) -> str:
    """
    Convert HTML to readable text (best-effort).
    Keeps headings/paragraphs/list items order.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove non-content tags
    for tag in soup(["script", "style", "noscript", "svg", "canvas", "iframe"]):
        tag.decompose()

    # Best-effort remove nav/footer/aside
    for tag in soup.find_all(["nav", "footer", "aside"]):
        tag.decompose()

    # Try to focus on <main> if present
    main = soup.find("main")
    root = main if main else soup.body if soup.body else soup

    # Collect structured text: headings, paragraphs, list items
    parts = []
    for el in root.find_all(["h1", "h2", "h3", "p", "li"]):
        txt = el.get_text(" ", strip=True)
        if not txt:
            continue
        parts.append(txt)

    # Fallback if extraction is empty
    if not parts:
        text = root.get_text("\n", strip=True)
    else:
        text = "\n".join(parts)

    text = _normalize_text(text)
    text = _cut_noise_sections(text)
    return text
