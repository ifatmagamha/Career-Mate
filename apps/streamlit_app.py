import streamlit as st
from pathlib import Path

st.set_page_config(page_title="RecruitAI", layout="wide")

st.title("RecruitAI — Assistant multi-agent pour le recrutement")
st.write("Collector → Analyzer → RAG → Matcher → Writer → Tracker")

st.info("Utilise le menu à gauche pour naviguer entre les pages.")

# quick check: show generated docs if exist
cv_path = Path("data/processed/generated_docs/cv_generated.tex")
lm_path = Path("data/processed/generated_docs/cover_letter_generated.tex")

col1, col2 = st.columns(2)
with col1:
    st.metric("CV généré", "✅" if cv_path.exists() else "❌")
with col2:
    st.metric("Lettre générée", "✅" if lm_path.exists() else "❌")
