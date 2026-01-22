# apps/0_Chat_Assistant.py
from __future__ import annotations
from src.ui.nav import nav
nav()

import json
import streamlit as st

from src.ui.session import require_login
from src.storage.user_store import load_profile
from src.llm.gemini_client import llm, extract_json_dict

st.set_page_config(page_title="RecruitAI — Chat Assistant", layout="wide")
st.title("💬 RecruitAI — Chat Assistant")

user_id = require_login()
profile = load_profile(user_id)

st.caption("This chat helps you define a *search plan* (query, roles, keywords, location).")

if "chat_messages" not in st.session_state:
    st.session_state["chat_messages"] = []
if "search_plan" not in st.session_state:
    st.session_state["search_plan"] = None

# Display chat
for m in st.session_state["chat_messages"]:
    with st.chat_message(m["role"]):
        st.write(m["content"])

user_msg = st.chat_input("Describe what internship you want (role, city, constraints)...")

if user_msg:
    st.session_state["chat_messages"].append({"role": "user", "content": user_msg})
    with st.chat_message("user"):
        st.write(user_msg)

    # LLM produces JSON search plan
    system = """
You are a recruiting assistant.
Task: turn the user's intent into a structured search plan JSON.

Return ONLY JSON with keys:
query (string), location (string), target_roles (array of strings), target_keywords (array of strings),
constraints (object: remote_ok boolean, language string 'fr'|'en').

Rules:
- Do not invent personal info. Use profile fields if needed.
- Keep keywords short (1-3 words).
- If missing, use defaults: location=profile.location, language=profile.language, remote_ok=profile.remote_ok.
"""

    prompt = f"""{system}

PROFILE:
location: {profile.location}
language: {profile.language}
remote_ok: {profile.remote_ok}
target_roles: {profile.target_roles}
target_keywords: {profile.target_keywords}

USER MESSAGE:
{user_msg}
"""

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            text = llm.generate_text(prompt, temperature=0.2, max_output_tokens=500)
            data = extract_json_dict(text)

            # Fallback defaults
            data.setdefault("location", profile.location)
            data.setdefault("target_roles", profile.target_roles or [])
            data.setdefault("target_keywords", profile.target_keywords or [])
            data.setdefault("constraints", {})
            data["constraints"].setdefault("remote_ok", profile.remote_ok)
            data["constraints"].setdefault("language", profile.language)

            st.session_state["search_plan"] = data
            st.write("✅ Search plan ready (JSON):")
            st.code(json.dumps(data, ensure_ascii=False, indent=2), language="json")

            st.session_state["chat_messages"].append(
                {"role": "assistant", "content": "I prepared a search plan. Go to Job Search to run it."}
            )

st.divider()
st.subheader("Current Search Plan")
if st.session_state["search_plan"]:
    st.code(json.dumps(st.session_state["search_plan"], ensure_ascii=False, indent=2), language="json")
    st.page_link("pages/1_Job_Search.py", label="➡️ Go to Job Search", icon="🔎")
else:
    st.info("Chat with the assistant to generate a search plan.")
