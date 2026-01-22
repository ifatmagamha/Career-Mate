# smoke_graph.py
from __future__ import annotations

from src.graph.build_graph import build_recruit_graph
from src.schemas.candidate import CandidateProfile


def main():
    graph = build_recruit_graph()

    candidate = CandidateProfile(
        full_name="John Doe",
        email="john@test.com",
        phone=None,
        location="Paris",
        cv_text=("Data Science student. Skills: Python, SQL, pandas, scikit-learn. "
                 "Built ML classification project and Streamlit dashboard. ") * 3,
        target_roles=["Data Scientist Intern"],
        target_keywords=["Python", "Machine Learning", "SQL"]
    )

    state = {
        "user_id": "id_user",
        "query": "Data Science",
        "location": "Paris",
        "limit": 5,
        "candidate": candidate,
        # optionnel: forcer une offre
        # "selected_offer_url": "https://...."
    }

    out = graph.invoke(state)

    print("\n✅ GRAPH DONE")
    print("keys:", list(out.keys()))
    print("offers_raw:", len(out.get("offers_raw") or []))
    print("offers_analyzed:", len(out.get("offers_analyzed") or []))
    print("matches:", len(out.get("matches") or []))
    print("generated:", out.get("generated"))
    print("tracking:", out.get("tracking"))


if __name__ == "__main__":
    main()
