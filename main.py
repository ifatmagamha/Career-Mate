# main.py

from dotenv import load_dotenv
load_dotenv()

from graph.workflow import build_workflow
from services.latex_compiler import compile_latex
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

    # --- Access output ---
    output = final_state["final_output"]
    target_offer = output["target_offer"]

    print("✅ Pipeline terminé")
    print("📌 Offre ciblée :", target_offer["offer_title"], "-", target_offer["company"])
    print("📊 Score matching :", target_offer.get("matching_score"))

    # --- Compile PDFs via service ---
    cv_pdf = compile_latex(output["cv_latex"], "cv")
    letter_pdf = compile_latex(output["cover_letter_latex"], "cover_letter")

    print("📄 PDFs générés :", cv_pdf, letter_pdf)

    # --- Tracking résumé ---
    tracking = final_state.get("tracking", {})
    print("📝 Suivi application :", tracking)


if __name__ == "__main__":
    main()
