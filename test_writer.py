# test_writer.py
from src.agents.writer import generate_cv_and_letter_pdfs
from src.schemas.candidate import CandidateProfile
from src.schemas.job_offer import OfferAnalyzed


def main():
    candidate = CandidateProfile(
        full_name="John Doe",
        email="john@test.com",
        phone="0600000000",
        location="Paris",
        cv_text=(
            "Data Science student. Skills: Python, SQL, pandas, scikit-learn. "
            "Built ML classification project and Streamlit dashboard. "
            "Worked on data cleaning, feature engineering and model evaluation."
        ) * 2,
        target_roles=["Data Scientist Intern"],
        target_keywords=["Python", "Machine Learning", "SQL", "pandas", "scikit-learn"],
        # si ton schema supporte ces champs:
        # github_url="https://github.com/johndoe",
        # linkedin_url="https://linkedin.com/in/johndoe",
    )

    offer = OfferAnalyzed(
        url="https://example.com/job/1",
        title="Data Scientist Intern",
        company="ACME",
        location="Paris",
        contract_type="internship",
        seniority="intern",
        skills=["Python", "SQL", "Machine Learning", "pandas"],
        missions=["Build ML models", "Analyze datasets", "Communicate results"],
        requirements=["Python", "Basics ML", "Good communication"],
        keywords=["python", "ml", "sql"],
        summary="Internship in a data science team."
    )

    files = generate_cv_and_letter_pdfs(
        user_id="id_user",
        candidate=candidate,
        offer=offer,
        out_dir="data/generated",
    )
    print("✅ PDFs saved:", files)


if __name__ == "__main__":
    main()
