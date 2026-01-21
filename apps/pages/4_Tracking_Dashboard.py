import streamlit as st
import pandas as pd
import json
from pathlib import Path
import plotly.express as px

st.set_page_config(page_title="Tracking", layout="wide")
st.title("4) Tracking Dashboard")

p = Path("data/tracking/applications.json")
if not p.exists():
    st.warning("Pas de tracking. Lance le pipeline pour créer applications.json")
    st.stop()

rows = json.loads(p.read_text(encoding="utf-8"))
df = pd.DataFrame(rows)

st.subheader("Historique des candidatures")
st.dataframe(df, use_container_width=True)

if "score" in df.columns:
    st.subheader("Distribution des scores")
    fig = px.histogram(df, x="score", nbins=10)
    st.plotly_chart(fig, use_container_width=True)

if "status" in df.columns:
    st.subheader("Répartition des statuts")
    fig2 = px.pie(df, names="status")
    st.plotly_chart(fig2, use_container_width=True)
