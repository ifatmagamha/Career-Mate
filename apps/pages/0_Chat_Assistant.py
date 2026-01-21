import json
import re
import streamlit as st
import pandas as pd
from pathlib import Path

from llm.gemini_client import GeminiClient
from graph.workflow import build_graph
from schemas.candidate import CandidateProfile

st.set_page_config(page_title="RecruitAI Chat", layout="wide")
st.title("💬 RecruitAI — Chat Assistant")
st.caption("Parle avec l’assistant, il collecte les offres, analyse, match, génère CV/LM et alimente le dashboard.")

# ---------- Helpers ----------
INTENT_PROMPT = """Tu es un assistant recrutement.
À partir du message utilisateur, retourne STRICTEMENT un JSON valide avec ces champs:

- query: string (ex: "stage data scientist", "junior data analyst", etc.)
- location: string (ex: "Paris", "France", "Remote")
- limit: number (5 à 30)
- rag_k: number (3 à 20)
- skills: liste[string] (skills candidates si l'utilisateur en donne, sinon [])

Message utilisateur:
\"\"\"{msg}\"\"\"

Retour JSON seulement, sans texte autour.
"""

def extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise ValueError("No JSON found in LLM output")
    return json.loads(m.group())

def run_pipeline(intent: dict) -> dict:
    # Candidate minimal (tu pourras remplacer par CV parser plus tard)
    skills = intent.get("skills") or st.session_state.get("default_skills", [])
    candidate = CandidateProfile(
        id="cand_chat",
        full_name=st.session_state.get("default_name", "Chat User"),
        location=intent.get("location", "France"),
        skills=skills,
    )

    state = {
        "candidate": candidate,
        "query": intent.get("query", "stage data scientist"),
        "location": intent.get("location", "France"),
        "limit": int(intent.get("limit", 10)),
        "rag_k": int(intent.get("rag_k", 10)),
    }

    graph = build_graph()
    result = graph.invoke(state)
    return result

def render_dashboard(result: dict):
    st.divider()
    st.subheader("📊 Dashboard")

    if result.get("errors"):
        st.error("Erreurs:\n" + "\n".join(result["errors"]))
        return

    # Summary
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Offres collectées", len(result.get("offers_raw", [])))
    c2.metric("Offres analysées", len(result.get("offers_parsed", [])))
    c3.metric("Matches", len(result.get("matches", [])))
    c4.metric("RAG indexées", result.get("rag_indexed_count", 0))

    # Matches table
    offers = {o.id: o for o in result.get("offers_parsed", [])}
    matches = result.get("matches", [])

    df = pd.DataFrame([{
        "job_id": m.job_id,
        "score": m.score,
        "title": offers.get(m.job_id).title if offers.get(m.job_id) else "",
        "company": offers.get(m.job_id).company if offers.get(m.job_id) else "",
        "matched_skills": ", ".join(m.matched_skills[:8]),
        "missing_skills": ", ".join(m.missing_skills[:8]),
    } for m in matches]).sort_values("score", ascending=False)

    st.markdown("### 🔝 Top matching")
    st.dataframe(df, use_container_width=True)

    # Offer detail
    st.markdown("### 🔎 Détail offre")
    if not df.empty:
        selected_job_id = st.selectbox("Choisir une offre", df["job_id"].tolist(), index=0)
        m = next(x for x in matches if x.job_id == selected_job_id)
        o = offers.get(selected_job_id)

        colA, colB = st.columns([2, 1])
        with colA:
            st.markdown(f"#### {o.title if o else selected_job_id}")
            st.write("Entreprise:", o.company if o else None)
            st.write("Localisation:", o.location if o else None)
            st.write("Score:", m.score)
            st.write("Reasons:", m.reasons)
            st.markdown("**Missions**")
            st.write((o.missions or [])[:12] if o else [])
            st.markdown("**Requirements**")
            st.write((o.requirements or [])[:12] if o else [])
        with colB:
            st.markdown("**Matched skills**")
            st.write(m.matched_skills)
            st.markdown("**Missing skills**")
            st.write(m.missing_skills)
            st.markdown("**Recommendations**")
            st.write(m.recommendations)

    # Docs preview + download
    st.markdown("### 🧾 Documents générés")
    cv_path = Path("data/processed/generated_docs/cv_generated.tex")
    lm_path = Path("data/processed/generated_docs/cover_letter_generated.tex")

    d1, d2 = st.columns(2)
    with d1:
        st.subheader("CV (LaTeX)")
        if cv_path.exists():
            st.code(cv_path.read_text(encoding="utf-8")[:3500], language="latex")
            st.download_button("Télécharger CV .tex", cv_path.read_bytes(), file_name="cv_generated.tex")
        else:
            st.info("Aucun CV généré.")
    with d2:
        st.subheader("Lettre (LaTeX)")
        if lm_path.exists():
            st.code(lm_path.read_text(encoding="utf-8")[:3500], language="latex")
            st.download_button("Télécharger lettre .tex", lm_path.read_bytes(), file_name="cover_letter_generated.tex")
        else:
            st.info("Aucune lettre générée.")

    # Tracking
    st.markdown("### 🗂️ Tracking")
    last_row = result.get("last_application_row")
    if last_row:
        st.json(last_row)
    else:
        st.info("Pas de tracking trouvé dans le dernier run.")


# ---------- Sidebar defaults ----------
with st.sidebar:
    st.header("Profil candidat (par défaut)")
    st.session_state["default_name"] = st.text_input("Nom", st.session_state.get("default_name", "Chat User"))
    st.session_state["default_skills"] = [s.strip() for s in st.text_area(
        "Skills (séparés par virgule)",
        ",".join(st.session_state.get("default_skills", ["python", "pandas", "sql", "ml"])),
    ).split(",") if s.strip()]

    st.header("LLM")
    model = st.selectbox("Gemini model", ["gemini-2.0-flash", "gemini-2.5-pro"], index=0)
    st.session_state["intent_model"] = model


# ---------- Chat UI ----------
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "assistant", "content": "Salut 👋 Dis-moi quel poste tu cherches (ex: 'stage data scientist à Paris, 10 offres')."}
    ]

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

user_msg = st.chat_input("Ex: Je cherche un stage data science à Paris, 15 offres. Mes skills: python, sql, pandas")
if user_msg:
    st.session_state["messages"].append({"role": "user", "content": user_msg})
    with st.chat_message("user"):
        st.write(user_msg)

    # 1) Intent parsing
    with st.chat_message("assistant"):
        with st.spinner("Je comprends ta demande..."):
            llm = GeminiClient()
            raw = llm.generate(model=st.session_state["intent_model"], prompt=INTENT_PROMPT.format(msg=user_msg))
            try:
                intent = extract_json(raw)
            except Exception:
                intent = {"query": "stage data scientist", "location": "Paris", "limit": 10, "rag_k": 10, "skills": []}

        st.write("✅ Voilà ce que j’ai compris :")
        st.json(intent)

        # 2) Run pipeline
        with st.spinner("Je lance la pipeline (collecte → analyse → RAG → matching → docs → tracking)..."):
            result = run_pipeline(intent)

        st.session_state["last_result"] = result
        if result.get("errors"):
            st.error("Pipeline terminée avec erreurs.")
        else:
            st.success("Pipeline terminée ✅ Dashboard mis à jour.")
        st.session_state["messages"].append({"role": "assistant", "content": "Pipeline terminée ✅ Tu peux voir le dashboard juste en dessous."})

# Dashboard (always show if exists)
result = st.session_state.get("last_result")
if result:
    render_dashboard(result)
