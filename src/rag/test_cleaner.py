# src/rag/test_cleaner.py
from __future__ import annotations

from fetcher import fetch_url
from cleaner import clean_html_to_text

def main():
    url = "https://careers.descartesunderwriting.com/jobs/6631557-data-scientist-intern"
    res = fetch_url(url)

    text = clean_html_to_text(res.text or "", url=url)
    print("clean_len:", len(text))
    print("preview:\n", text[:1200])

if __name__ == "__main__":
    main()
