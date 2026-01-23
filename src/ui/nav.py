from __future__ import annotations
import streamlit as st
def nav():
    st.sidebar.markdown("### 🚀 Career Mate")
    st.sidebar.divider()
    st.sidebar.page_link("pages/5_Login.py", label="Login / Profile", icon="🔐")
    st.sidebar.page_link("pages/6_Profile.py", label="My Persona", icon="👤")
    st.sidebar.page_link("pages/0_Unified_Chat.py", label="AI Assistant", icon="🤖")
    st.sidebar.page_link("pages/2_Results.py", label="Analyzed Jobs", icon="💼")
    st.sidebar.page_link("pages/3_Generator.py", label="Cover Letter AI", icon="✍️")
    st.sidebar.page_link("pages/4_Tracker_Dashboard.py", label="Application Tracker", icon="📊")
