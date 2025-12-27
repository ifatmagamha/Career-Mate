# main.py

from dotenv import load_dotenv
load_dotenv()

from graph.workflow import build_workflow
import os

def main():
    """
    Exécute le pipeline complet :
    Collector -> Analyzer -> Matcher -> Writer -> Tracker
    Génère ensuite les PDFs du CV et de la lettre de motivation
    """

    # --- Build pipeline LangGraph ---
    app = build_workflow()

    # --- Initial State ---
    initial_state = {
        "query": "Data Scientist",
        "location": "Paris",
        "limit": 20,
        "candidate_profile": {
            "name": "Yassine Dridi",
            "email": "yassine.dridi@dauphine.tn",
            "skills": [
                "Python",
                "Machine Learning",
                "Data Analysis",
                "Statistics",
                "SQL",
                "Data Visualization"
            ],
            "soft_skills": [
                "Communication",
                "Problem-solving",
                "Teamwork"
            ],
            "experience_level": "Mid-Level",
        },
    }

# --- Run pipeline ---
    final_state = app.invoke(initial_state)

    # --- Output ---
    output = final_state.get("final_output", {})
    target_offer = output.get("target_offer", {})

    print("✅ Pipeline terminé")
    print(
        "📌 Offre ciblée :",
        target_offer.get("offer_title"),
        "-",
        target_offer.get("company"),
    )
    print("📊 Score matching :", target_offer.get("matching_score"))

    # --- PDFs générés par WriterAgent ---
    print("📄 CV PDF :", output.get("cv_pdf"))
    print("📄 Lettre PDF :", output.get("letter_pdf"))

    # --- Tracking ---
    tracking = final_state.get("tracking", {})
    if tracking:
        print("📝 Suivi application :", tracking)


if __name__ == "__main__":
    main()