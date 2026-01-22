# app/pages/1_Profile.py
import streamlit as st
from src.ui.state import init_session
from src.ui.auth import require_login, logout_button

st.set_page_config(page_title="RecruitAI - Profile", layout="wide")
init_session()
require_login()

st.sidebar.success(f"{st.session_state.user_email}")
logout_button()

st.title("👤 Profile")

full_name = st.text_input("Full name")
location = st.text_input("Location", value="Paris")
github = st.text_input("GitHub URL (optional)")
cv_text = st.text_area("Paste your CV text", height=250)

target_roles = st.text_input("Target roles (comma-separated)", value="Data Scientist Intern")
target_keywords = st.text_input("Target keywords (comma-separated)", value="Python, SQL, Machine Learning")

if st.button("Save profile"):
    st.session_state.profile = {
        "full_name": full_name,
        "location": location,
        "github": github,
        "cv_text": cv_text,
        "target_roles": [x.strip() for x in target_roles.split(",") if x.strip()],
        "target_keywords": [x.strip() for x in target_keywords.split(",") if x.strip()],
    }
    st.success("✅ Profile saved.")
