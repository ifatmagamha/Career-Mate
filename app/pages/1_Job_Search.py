# apps/1_Job_Search.py
from __future__ import annotations
import streamlit as st
from src.ui.nav import nav
from src.ui.session import require_login
import json
from pathlib import Path

from src.ui.session import require_login
from src.storage.user_store import load_profile
from src.graph.build_graph import build_recruit_graph
from src.schemas.candidate import CandidateProfile
from src.config.settings import settings

st.set_page_config(page_title="RecruitAI — Job Search", layout="wide")
st.title("🔎 RecruitAI — Job Search")

user_id = require_login()
profile = load_profile(user_id)

search_plan = st.session_state.get("search_plan") or {}

with st.sidebar:
    st.header("Search settings")

    query = st.text_input("Query", value=search_plan.get("query", "Data Science"))
    location = st.text_input("Location", value=search_plan.get("location", profile.location))
    limit = st.slider("Offers to collect", 5, 20, int(search_plan.get("limit", 10)))
    llm_max = st.slider("LLM calls (Analyzer)", 0, 5, int(search_plan.get("llm_max", 2)))
    top_k = st.slider("Top K", 5, 20, int(search_plan.get("top_k", 10)))

    st.subheader("Candidate (from profile)")
    st.write(profile.full_name or profile.email)
    st.write(profile.location)
    run_btn = st.button("🚀 Run pipeline", type="primary")

# Build CandidateProfile from UserProfile
# --- CV validation before building CandidateProfile ---
if not profile.cv_text or len(profile.cv_text.strip()) < 50:
    st.error("❌ Your CV is missing or too short (minimum 50 characters).")
    st.info("👉 Please go to Profile and paste your CV before running the search.")
    st.page_link("pages/02_Profile.py", label="➡️ Go to Profile", icon="👤")
    st.stop()

# Safe to build CandidateProfile
candidate = CandidateProfile(
    full_name=profile.full_name or "User",
    email=profile.email,
    phone=None,
    location=profile.location,
    cv_text=profile.cv_text,
    target_roles=search_plan.get("target_roles") or profile.target_roles,
    target_keywords=search_plan.get("target_keywords") or profile.target_keywords,
)


if run_btn:
    graph = build_recruit_graph()

    state = {
        "query": query,
        "location": location,
        "limit": limit,
        "llm_max": llm_max,
        "top_k": top_k,
        "candidate": candidate,
        "tracking_path": str(Path(settings.DATA_DIR) / "tracking.json"),
    }

    with st.status("Running LangGraph pipeline...", expanded=True):
        out = graph.invoke(state)
        st.write(f"✅ Collected: {len(out.get('offers_raw', []))}")
        st.write(f"✅ Analyzed: {len(out.get('offers_analyzed', []))}")
        st.write(f"✅ Matches: {len(out.get('matches', []))}")

    st.success("Done ✅")
    st.page_link("apps/2_Results.py", label="➡️ View Results", icon="🏁")

st.divider()
st.subheader("Last run outputs")
data_dir = Path(settings.DATA_DIR)
for fname in ["job_offers_raw.json", "job_offers_analyzed.json", "matches.json", "tracking.json"]:
    p = data_dir / fname
    st.write(f"- {fname}: {'✅' if p.exists() else '❌'}")
