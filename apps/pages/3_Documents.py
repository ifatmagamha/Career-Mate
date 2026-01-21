import streamlit as st
from pathlib import Path

st.set_page_config(page_title="Documents", layout="wide")
st.title("3) Documents générés")

cv_path = Path("data/processed/generated_docs/cv_generated.tex")
lm_path = Path("data/processed/generated_docs/cover_letter_generated.tex")

col1, col2 = st.columns(2)
with col1:
    st.subheader("CV (LaTeX)")
    if cv_path.exists():
        st.code(cv_path.read_text(encoding="utf-8")[:5000], language="latex")
        st.download_button("Télécharger CV .tex", cv_path.read_bytes(), file_name="cv_generated.tex")
    else:
        st.warning("CV non trouvé. Lance le pipeline.")

with col2:
    st.subheader("Lettre (LaTeX)")
    if lm_path.exists():
        st.code(lm_path.read_text(encoding="utf-8")[:5000], language="latex")
        st.download_button("Télécharger lettre .tex", lm_path.read_bytes(), file_name="cover_letter_generated.tex")
    else:
        st.warning("Lettre non trouvée. Lance le pipeline.")
