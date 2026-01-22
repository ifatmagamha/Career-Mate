from __future__ import annotations

from src.graph.build_graph import build_recruit_graph
from src.schemas.candidate import CandidateProfile

def main():
    graph = build_recruit_graph()

    candidate = CandidateProfile(
        full_name="Demo Candidate",
        email=None,
        phone=None,
        location="Paris",
        cv_text="Data Science student. Skills: Python, SQL, Pandas, scikit-learn, ML, Docker.",
        target_roles=["Data Scientist"],
        target_keywords=["Python", "SQL", "Machine Learning", "NLP"],
    )

    state = {
        "query": "Data Science",
        "location": "Paris",
        "limit": 10,
        "llm_max": 2,
        "top_k": 10,
        "candidate": candidate,
        "tracking_path": "data/tracking.json",
    }

    out = graph.invoke(state)
    print("DONE. Top match:", out["matches"][0].title if out.get("matches") else "None")


if __name__ == "__main__":
    main()
