# apps/2_Results.py
from __future__ import annotations
from src.ui.nav import nav
nav()

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.ui.session import require_login
from src.config.settings import settings

st.set_page_config(page_title="RecruitAI — Results", layout="wide")
st.title("🏁 RecruitAI — Results")

require_login()

p = Path(settings.DATA_DIR) / "matches.json"
if not p.exists():
    st.warning("No matches.json found. Run Job Search first.")
    st.page_link("pages/1_Job_Search.py", label="➡️ Go to Job Search", icon="🔎")
    st.stop()

matches = json.loads(p.read_text(encoding="utf-8"))
if not matches:
    st.warning("matches.json is empty.")
    st.stop()

df = pd.DataFrame(matches).sort_values("score", ascending=False)

with st.sidebar:
    st.header("Filters")
    min_score = st.slider("Min score", 0, 100, 30)
    df2 = df[df["score"] >= min_score].copy()

st.subheader(f"Matches (>= {min_score})")
st.dataframe(df2[["score", "title", "company", "location", "url"]], use_container_width=True, hide_index=True)

st.subheader("Select an offer")
options = list(range(len(df2)))
if not options:
    st.info("No offer after filtering.")
    st.stop()

idx = st.selectbox(
    "Pick a ranked offer",
    options=options,
    format_func=lambda i: f"{df2.iloc[i]['score']} — {df2.iloc[i]['title']}",
)

selected = df2.iloc[idx].to_dict()
st.session_state["selected_offer_url"] = selected["url"]

st.markdown(f"### {selected['title']}")
st.write(f"**Score:** {selected['score']}/100")
st.write(f"**Company:** {selected.get('company')}")
st.write(f"**Location:** {selected.get('location')}")
st.write(f"**URL:** {selected.get('url')}")

c1, c2 = st.columns(2)
with c1:
    st.markdown("**Strong points**")
    st.write(selected.get("strong_points", []))
    st.markdown("**Reasons**")
    st.write(selected.get("reasons", []))
with c2:
    st.markdown("**Missing skills**")
    st.write(selected.get("missing_skills", []))

st.page_link("pages/3_Generator.py", label="➡️ Generate CV + Letter (PDF)", icon="📝")
