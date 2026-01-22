# src/rag/test_retriever.py
from __future__ import annotations

from fetcher import fetch_url
from cleaner import clean_html_to_text
from chunker import chunk_text
from retriever import retrieve_tfidf, build_offer_query


def main():
    url = "https://careers.descartesunderwriting.com/jobs/6631557-data-scientist-intern"

    print(">>> Fetching URL")
    res = fetch_url(url)
    print("fetch ok:", res.ok, "status:", res.status_code)

    if not res.ok or not res.text:
        print("❌ Fetch failed")
        return

    print("\n>>> Cleaning HTML")
    clean_text = clean_html_to_text(res.text, url=url)
    print("clean_len:", len(clean_text))

    print("\n>>> Chunking text")
    chunks = chunk_text(clean_text, url=url)
    print("chunks:", len(chunks))

    if not chunks:
        print("❌ No chunks produced")
        return

    queries = {
        "requirements": build_offer_query(
            offer_title="Data Scientist Intern",
            offer_company="Descartes Underwriting",
            focus="requirements",
        ),
        "missions": build_offer_query(
            offer_title="Data Scientist Intern",
            offer_company="Descartes Underwriting",
            focus="missions",
        ),
        "skills": build_offer_query(
            offer_title="Data Scientist Intern",
            offer_company="Descartes Underwriting",
            focus="skills",
        ),
    }

    for focus, query in queries.items():
        print("\n" + "=" * 60)
        print(f"FOCUS: {focus.upper()}")
        print("QUERY:", query)

        results = retrieve_tfidf(
            query=query,
            chunks=chunks,
            top_k=3,
            language="en",
        )

        for r in results:
            print(f"\n--- score={r.score:.3f} | chunk={r.chunk.index} | id={r.chunk.chunk_id}")
            print(r.chunk.text[:500])


if __name__ == "__main__":
    main()
