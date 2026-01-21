import streamlit as st
import pandas as pd

from graph.workflow import build_graph
from schemas.candidate import CandidateProfile

st.set_page_config(page_title="Collecte & Analyse", layout="wide")
st.title("1) Collecte & Analyse")

with st.sidebar:
    st.header("Paramètres recherche")
    query = st.text_input("Query", "stage data scientist")
    location = st.text_input("Location", "Paris")
    limit = st.slider("Nombre d'offres", 5, 30, 10)
    rag_k = st.slider("Top-k (RAG)", 3, 20, 10)

    st.header("Candidat (minimal)")
    skills_txt = st.text_area("Skills (séparés par virgule)", "python, pandas, sql, machine learning, nlp, langchain")

run = st.button("🚀 Lancer le pipeline (jusqu’au tracking)", use_container_width=True)

if run:
    candidate = CandidateProfile(
        id="cand_ui",
        full_name="UI Candidate",
        location=location,
        skills=[s.strip() for s in skills_txt.split(",") if s.strip()],
    )

    graph = build_graph()
    state = {
        "candidate": candidate,
        "query": query,
        "location": location,
        "limit": limit,
        "rag_k": rag_k,
    }

    with st.spinner("Exécution du pipeline..."):
        result = graph.invoke(state)

    st.session_state["last_result"] = result
    st.success("Pipeline terminé ✅")

result = st.session_state.get("last_result")
if not result:
    st.warning("Clique sur 'Lancer le pipeline' pour générer des résultats.")
    st.stop()

# OFFERS RAW
st.subheader("Offres collectées (raw)")
offers_raw = result.get("offers_raw", [])
df_raw = pd.DataFrame([{
    "id": o.id,
    "title": o.title,
    "company": o.company,
    "location": o.location,
    "source": o.source,
    "url": str(o.url) if o.url else None,
} for o in offers_raw])
st.dataframe(df_raw, use_container_width=True)

# OFFERS PARSED
st.subheader("Offres analysées (parsed)")
offers_parsed = result.get("offers_parsed", [])
df_parsed = pd.DataFrame([{
    "id": o.id,
    "title": o.title,
    "company": o.company,
    "location": o.location,
    "skills": ", ".join(o.skills[:15]),
    "missions_n": len(o.missions),
    "requirements_n": len(o.requirements),
} for o in offers_parsed])
st.dataframe(df_parsed, use_container_width=True)

# RAG info
st.subheader("RAG")
st.write("Top IDs récupérés:", result.get("rag_top_offer_ids", [])[:10])
st.write("Indexed:", result.get("rag_indexed_count"))
