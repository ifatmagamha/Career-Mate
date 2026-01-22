# src/ui/nav.py
from __future__ import annotations
import streamlit as st

def nav():
    st.sidebar.title("RecruitAI")
    st.sidebar.divider()

    # paths are relative to the entrypoint folder: app/
    st.sidebar.page_link("Home.py", label="Home", icon="🏠")

    st.sidebar.page_link("pages/0_Login.py", label="Login", icon="🔐")
    st.sidebar.page_link("pages/1_Profile.py", label="Profile", icon="👤")
    st.sidebar.page_link("pages/2_Chat_Assistant.py", label="Chat", icon="💬")
    st.sidebar.page_link("pages/3_Job_Search.py", label="Job Search", icon="🔎")
    st.sidebar.page_link("pages/4_Results.py", label="Results", icon="🏁")
    st.sidebar.page_link("pages/5_Generator.py", label="Generator", icon="📝")
    st.sidebar.page_link("pages/6_Tracker.py", label="Tracker", icon="📊")
