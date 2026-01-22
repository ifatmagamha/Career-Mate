# apps/6_Profile.py
from __future__ import annotations
from src.ui.nav import nav
nav()

import streamlit as st

from src.schemas.user import UserProfile
from src.storage.user_store import load_profile, save_profile

st.set_page_config(page_title="RecruitAI — Profile", layout="wide")
st.title("RecruitAI — My Profile")

# Require login
user_id = st.session_state.get("user_id")
if not user_id:
    st.warning("Please login first.")
    st.page_link("pages/5_Login.py", label="➡️ Go to Login", icon="🔐")
    st.stop()

# Load profile fresh
profile = load_profile(user_id)

st.caption(f"User ID: {profile.user_id} • Email: {profile.email}")

colA, colB = st.columns([1, 1])

with colA:
    st.subheader("Identity")
    profile.full_name = st.text_input("Full name", value=profile.full_name)
    profile.location = st.text_input("Location", value=profile.location)
    profile.language = st.selectbox("Language", options=["fr", "en"], index=0 if profile.language == "fr" else 1)

    st.subheader("Links")
    github = st.text_input("GitHub URL", value=str(profile.github_url) if profile.github_url else "")
    linkedin = st.text_input("LinkedIn URL", value=str(profile.linkedin_url) if profile.linkedin_url else "")
    portfolio = st.text_input("Portfolio URL", value=str(profile.portfolio_url) if profile.portfolio_url else "")

    # Validate URLs via Pydantic by setting them into model later
    profile.github_url = github or None
    profile.linkedin_url = linkedin or None
    profile.portfolio_url = portfolio or None

with colB:
    st.subheader("Targets")
    roles = st.text_input("Target roles (comma-separated)", value=", ".join(profile.target_roles))
    keywords = st.text_input("Target keywords (comma-separated)", value=", ".join(profile.target_keywords))
    pref_locs = st.text_input("Preferred locations (comma-separated)", value=", ".join(profile.preferred_locations))
    profile.remote_ok = st.checkbox("Remote OK", value=profile.remote_ok)

    def split_csv(s: str):
        return [x.strip() for x in (s or "").split(",") if x.strip()]

    profile.target_roles = split_csv(roles)
    profile.target_keywords = split_csv(keywords)
    profile.preferred_locations = split_csv(pref_locs)

st.subheader("CV text")
profile.cv_text = st.text_area("Paste your CV text here", value=profile.cv_text, height=240)

c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    if st.button("💾 Save profile", type="primary"):
        try:
            # re-validate the whole model (URLs etc.)
            validated = UserProfile.model_validate(profile.model_dump(mode="json"))
            save_profile(validated)
            st.success("Saved ✅")
        except Exception as e:
            st.error(str(e))

with c2:
    st.page_link("pages/0_Chat_Assistant.py", label="➡️ Chat Assistant", icon="💬")
with c3:
    st.page_link("pages/1_Job_Search.py", label="➡️ Job Search", icon="🔎")
