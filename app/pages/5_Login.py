# apps/5_Login.py
from __future__ import annotations

import streamlit as st

from src.storage.user_store import create_user, authenticate, get_profile_by_email

st.set_page_config(page_title="RecruitAI — Login", layout="centered")

st.title("RecruitAI — Login")

if "user_id" not in st.session_state:
    st.session_state["user_id"] = None
if "profile" not in st.session_state:
    st.session_state["profile"] = None

tab_login, tab_signup = st.tabs(["Login", "Sign up"])

with tab_login:
    st.subheader("Login")
    email = st.text_input("Email", key="login_email")
    password = st.text_input("Password", type="password", key="login_password")

    if st.button("Login", type="primary"):
        try:
            user_id, profile = authenticate(email, password)
            st.session_state["user_id"] = user_id
            st.session_state["profile"] = profile.model_dump(mode="json")
            st.success("✅ Logged in")
            st.page_link("pages/6_Profile.py", label="➡️ Go to Profile", icon="👤")
        except Exception as e:
            st.error(str(e))

    if st.session_state["user_id"]:
        st.info(f"Logged in as: {st.session_state['profile']['email']}")
        if st.button("Logout"):
            st.session_state["user_id"] = None
            st.session_state["profile"] = None
            st.success("Logged out.")

with tab_signup:
    st.subheader("Create account")
    email_su = st.text_input("Email", key="su_email")
    password_su = st.text_input("Password", type="password", key="su_password")
    password_su2 = st.text_input("Confirm password", type="password", key="su_password2")

    if st.button("Create account"):
        try:
            if password_su != password_su2:
                raise ValueError("Passwords do not match")
            if get_profile_by_email(email_su):
                raise ValueError("Email already registered")

            profile = create_user(email_su, password_su)
            st.success("✅ Account created. You can login now.")
        except Exception as e:
            st.error(str(e))
