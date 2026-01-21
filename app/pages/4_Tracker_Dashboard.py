# apps/4_Tracker_Dashboard.py
from __future__ import annotations
from src.ui.nav import nav
nav()

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.ui.session import require_login
from src.config.settings import settings

st.set_page_config(page_title="RecruitAI — Tracker", layout="wide")
st.title("📊 RecruitAI — Tracker")

require_login()

p = Path(settings.DATA_DIR) / "tracking.json"
p.parent.mkdir(parents=True, exist_ok=True)
if not p.exists():
    p.write_text("[]", encoding="utf-8")

data = json.loads(p.read_text(encoding="utf-8"))
if not isinstance(data, list):
    data = []

df = pd.DataFrame(data) if data else pd.DataFrame(columns=["title", "company", "score", "status", "url"])

st.subheader("Applications")
st.dataframe(df[["status", "score", "title", "company", "url"]] if not df.empty else df, use_container_width=True)

st.divider()
st.subheader("Update status")

if df.empty:
    st.info("No tracked offers yet. Run Job Search first (it auto-saves matches into tracker).")
    st.stop()

idx = st.selectbox(
    "Pick an entry",
    options=list(range(len(df))),
    format_func=lambda i: f"{df.iloc[i]['status']} — {df.iloc[i]['score']} — {df.iloc[i]['title']}",
)

new_status = st.selectbox("New status", ["saved", "applied", "interview", "rejected"], index=0)

if st.button("Update"):
    now = datetime.utcnow().isoformat() + "Z"
    data[idx]["status"] = new_status
    data[idx]["updated_at"] = now
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    st.success("Updated ✅")
    st.rerun()

st.divider()
st.subheader("Quick stats")
if not df.empty:
    st.write(df["status"].value_counts())
