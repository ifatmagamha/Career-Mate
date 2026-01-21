# src/ui/nav.py
from __future__ import annotations
import streamlit as st

def nav():
    st.sidebar.divider()
    st.sidebar.page_link("pages/5_Login.py", label="Login", icon="🔐")
    st.sidebar.page_link("pages/6_Profile.py", label="Profile", icon="👤")
    st.sidebar.page_link("pages/0_Chat_Assistant.py", label="Chat", icon="💬")
    st.sidebar.page_link("pages/1_Job_Search.py", label="Job Search", icon="🔎")
    st.sidebar.page_link("pages/2_Results.py", label="Results", icon="🏁")
    st.sidebar.page_link("pages/3_Generator.py", label="Generator", icon="📝")
    st.sidebar.page_link("pages/4_Tracker_Dashboard.py", label="Tracker", icon="📊")
