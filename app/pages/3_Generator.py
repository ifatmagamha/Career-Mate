# apps/3_Generator.py
from __future__ import annotations
from src.ui.nav import nav
nav()

import json
from pathlib import Path
import streamlit as st

from src.ui.session import require_login
from src.storage.user_store import load_profile
from src.schemas.candidate import CandidateProfile
from src.schemas.job_offer import OfferAnalyzed
from src.agents.writer import generate_documents
from src.export.pdf import text_to_pdf
from src.config.settings import settings

st.set_page_config(page_title="RecruitAI — Generator", layout="wide")
st.title("📝 RecruitAI — Generator (CV + Motivation Letter)")

user_id = require_login()
profile = load_profile(user_id)

selected_url = st.session_state.get("selected_offer_url")
if not selected_url:
    st.warning("No offer selected. Go to Results first.")
    st.page_link("pages/2_Results.py", label="➡️ Go to Results", icon="🏁")
    st.stop()

p = Path(settings.DATA_DIR) / "job_offers_analyzed.json"
if not p.exists():
    st.warning("No analyzed offers found. Run Job Search first.")
    st.page_link("pages/1_Job_Search.py", label="➡️ Go to Job Search", icon="🔎")
    st.stop()

offers = json.loads(p.read_text(encoding="utf-8"))
offer = None
for o in offers:
    if o.get("url") == selected_url:
        offer = OfferAnalyzed.model_validate(o)
        break

if offer is None:
    st.error("Selected offer not found in analyzed offers.")
    st.stop()

st.markdown(f"### Selected offer")
st.write(offer.title)
st.write(offer.company)
st.write(str(offer.url))

candidate = CandidateProfile(
    full_name=profile.full_name or "User",
    email=profile.email,
    phone=None,
    location=profile.location,
    cv_text=profile.cv_text,
    target_roles=profile.target_roles,
    target_keywords=profile.target_keywords,
)

gen_btn = st.button("✨ Generate CV + Letter", type="primary")

out_dir = Path(settings.DATA_DIR) / "generated"
cv_txt_path = out_dir / "generated_cv.txt"
lm_txt_path = out_dir / "generated_letter.txt"
cv_pdf_path = out_dir / "generated_cv.pdf"
lm_pdf_path = out_dir / "generated_letter.pdf"

if gen_btn:
    with st.status("Generating with LLM (top1 only)...", expanded=True):
        cv_text, letter_text = generate_documents(candidate, offer)
        out_dir.mkdir(parents=True, exist_ok=True)
        cv_txt_path.write_text(cv_text, encoding="utf-8")
        lm_txt_path.write_text(letter_text, encoding="utf-8")

        text_to_pdf(cv_text, cv_pdf_path, title="Targeted CV (RecruitAI)")
        text_to_pdf(letter_text, lm_pdf_path, title="Motivation Letter (RecruitAI)")
        st.success("✅ Generated + PDF ready")

st.divider()
st.subheader("Downloads")

if cv_pdf_path.exists():
    st.download_button("⬇️ Download CV PDF", data=cv_pdf_path.read_bytes(), file_name="RecruitAI_CV.pdf")
if lm_pdf_path.exists():
    st.download_button("⬇️ Download Letter PDF", data=lm_pdf_path.read_bytes(), file_name="RecruitAI_Letter.pdf")

st.page_link("pages/4_Tracker_Dashboard.py", label="➡️ Go to Tracker", icon="📊")
