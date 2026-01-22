# src/rag/test_chunker.py
from __future__ import annotations

from fetcher import fetch_url
from cleaner import clean_html_to_text
from chunker import chunk_text

def main():
    url = "https://careers.descartesunderwriting.com/jobs/6631557-data-scientist-intern"
    res = fetch_url(url)
    text = clean_html_to_text(res.text or "", url=url)
    chunks = chunk_text(text, url=url, chunk_size=1200, overlap=200)

    print("clean_len:", len(text))
    print("chunks:", len(chunks))
    for c in chunks[:2]:
        print("\n--- chunk", c.index, "id=", c.chunk_id, "len=", len(c.text))
        print(c.text[:500])

if __name__ == "__main__":
    main()
