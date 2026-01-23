import streamlit as st
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ui.nav import nav

st.set_page_config(page_title="Career Mate", layout="wide")
nav()

col1, col2 = st.columns([1, 4])
with col1:
    st.image("https://cdn-icons-png.flaticon.com/512/4712/4712009.png", width=100) # Placeholder logo
with col2:
    st.title("Career Mate")
    st.markdown("### Your AI Copilot for Job Hunting")

st.write("---")
st.success("👋 Welcome! Use the sidebar to navigate your AI tools.")

