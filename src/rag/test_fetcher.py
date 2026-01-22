# src/rag/test_fetcher.py
from __future__ import annotations
from src.rag.fetcher import fetch_url

def main():
    url = "https://careers.descartesunderwriting.com/jobs/6631557-data-scientist-intern"
    res = fetch_url(url)

    print("ok:", res.ok)
    print("status:", res.status_code)
    print("content_type:", res.content_type)
    print("error:", res.error)

    if res.text:
        print("text_len:", len(res.text))
        print("sample:", res.text[:500])

    if res.raw_bytes:
        print("bytes_len:", len(res.raw_bytes))

if __name__ == "__main__":
    main()
