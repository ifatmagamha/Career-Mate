import streamlit as st
from src.ui.auth import init_session, login, logout

st.set_page_config(page_title="RecruitAI - Login", layout="wide")
init_session()

st.title("🔐 Login")

if st.session_state["is_auth"]:
    st.success(f"Connecté: {st.session_state['user_email']} (id={st.session_state['user_id']})")
    if st.button("Logout"):
        logout()
        st.rerun()
    st.stop()

with st.form("login_form"):
    email = st.text_input("Email", placeholder="you@email.com")
    user_id = st.text_input("User ID", placeholder="ex: id_user")
    submitted = st.form_submit_button("Se connecter")

if submitted:
    if not email or not user_id:
        st.error("Email et User ID sont obligatoires.")
    else:
        # MVP: pas de password (tu peux l'ajouter après)
        login(user_id=user_id.strip(), email=email.strip())
        st.success("✅ Login OK")
        st.switch_page("pages/1_Profile.py")
