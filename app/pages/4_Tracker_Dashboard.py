from __future__ import annotations
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

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

st.subheader("Applications (Kanban Board)")

# Kanban Board
from src.ui.components import render_kanban_column

if df.empty:
    st.info("No tracked offers yet. Run Job Search first (it auto-saves matches into tracker).")
    st.stop()

# Group by status
status_cols = st.columns(4)
statuses = ["saved", "applied", "interview", "rejected"]
colors = ["#6366f1", "#f59e0b", "#10b981", "#ef4444"] # Indigo, Amber, Emerald, Red

for i, status in enumerate(statuses):
    with status_cols[i]:
        # Filter jobs for this status
        jobs_in_status = df[df["status"] == status].to_dict('records')
        render_kanban_column(status.upper(), jobs_in_status, status, colors[i])

st.divider()

# Quick Update Form (Legacy simplified, could be better integrated)
st.caption("Admin (Quick Status Update)")
idx = st.selectbox(
    "Pick an entry to move",
    options=list(range(len(df))),
    format_func=lambda i: f"{df.iloc[i]['status']} — {df.iloc[i]['title']}",
)
new_status = st.selectbox("New status", statuses, index=0)
if st.button("Move"):
    now = datetime.utcnow().isoformat() + "Z"
    data[idx]["status"] = new_status
    data[idx]["updated_at"] = now
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    st.success("Moved ✅")
    st.rerun()
