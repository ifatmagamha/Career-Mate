# src/ui/session.py
from __future__ import annotations

import streamlit as st

def require_login():
    user_id = st.session_state.get("user_id")
    if not user_id:
        st.warning("Please login first.")
        st.page_link("apps/5_Login.py", label="➡️ Go to Login", icon="🔐")
        st.stop()
    return user_id
