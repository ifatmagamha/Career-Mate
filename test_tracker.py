# test_tracker.py
from src.agents.tracker import upsert_application, list_applications, add_note
from src.schemas.job_offer import OfferAnalyzed


def main():
    offer = OfferAnalyzed(
        url="https://example.com/job/1",
        title="Data Scientist Intern",
        company="ACME",
        location="Paris",
        contract_type="internship",
        seniority="intern",
        skills=["Python"],
        missions=[],
        requirements=[],
        keywords=[],
        summary="Internship."
    )

    rec = upsert_application(
        user_id="id_user",
        offer=offer,
        cv_pdf="data/generated/id_user_cv.pdf",
        letter_pdf="data/generated/id_user_lettre.pdf",
        status="to_apply",
    )
    print("created/updated:", rec.model_dump(mode="json"))

    add_note("id_user", str(offer.url), "Applied via company portal.")
    apps = list_applications("id_user")
    print("apps:", [a.model_dump(mode="json") for a in apps])


if __name__ == "__main__":
    main()
