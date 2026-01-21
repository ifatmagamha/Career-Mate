# app/Home.py
import streamlit as st
from src.ui.nav import nav

st.set_page_config(page_title="RecruitAI", layout="wide")
nav()

st.title("RecruitAI")
st.write("Use the left menu to navigate.")
st.page_link("pages/5_Login.py", label="➡️ Start (Login)", icon="🔐")
