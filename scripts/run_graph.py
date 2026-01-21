from __future__ import annotations
from graph.workflow import build_graph
from schemas.candidate import CandidateProfile

def main():
    graph = build_graph()

    # Exemple candidat minimal
    candidate = CandidateProfile(
        id="cand_001",
        full_name="Test Candidate",
        location="France",
        skills=["python", "pandas", "sql", "machine learning", "nlp", "langchain"],
    )

    state = {
        "candidate": candidate,
        "query": "stage data scientist",
        "location": "Paris",
        "limit": 10,
    }

    result = graph.invoke(state)

    print("\n=== DONE ===")
    print("Errors:", result.get("errors"))
    print("Offers raw:", len(result.get("offers_raw", [])))
    print("Offers parsed:", len(result.get("offers_parsed", [])))
    print("Matches:", len(result.get("matches", [])))
    print("Selected:", result.get("selected_job_id"))
    print("CV path:", result.get("generated_cv_path"))
    print("Letter path:", result.get("generated_letter_path"))
    print("Tracked row:", result.get("last_application_row"))


if __name__ == "__main__":
    main()
