# src/ui/auth.py
from __future__ import annotations
import streamlit as st

SESSION_KEYS = {
    "is_auth": False,
    "user_id": None,
    "user_email": None,
}

def init_session() -> None:
    for k, v in SESSION_KEYS.items():
        if k not in st.session_state:
            st.session_state[k] = v

def login(user_id: str, email: str) -> None:
    st.session_state["is_auth"] = True
    st.session_state["user_id"] = user_id
    st.session_state["user_email"] = email

def logout() -> None:
    st.session_state["is_auth"] = False
    st.session_state["user_id"] = None
    st.session_state["user_email"] = None

def require_auth(redirect_page: str = "pages/0_Login.py") -> None:
    init_session()
    if not st.session_state["is_auth"]:
        st.warning("🔐 Vous devez être connecté pour accéder à cette page.")
        st.switch_page(redirect_page)
