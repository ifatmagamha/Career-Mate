import streamlit as st
import pandas as pd
from graph.workflow import build_workflow
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="RecruitAI", layout="wide")

st.title("🤖 RecruitAI – Génération intelligente de CV & Lettre")

# ======================================================
# SIDEBAR — PROFIL CANDIDAT (SOURCE DE VÉRITÉ)
# ======================================================
st.sidebar.header("👤 Informations personnelles")

full_name = st.sidebar.text_input("Nom complet *")
email = st.sidebar.text_input("Email")
phone = st.sidebar.text_input("Téléphone")
location = st.sidebar.text_input("Ville / Pays")

st.sidebar.header("🎓 Formation")

education_level = st.sidebar.selectbox(
    "Niveau d'étude *",
    ["Licence", "Master 1", "Master 2", "Doctorat"]
)

field_of_study = st.sidebar.text_input("Domaine d'étude *")
university = st.sidebar.text_input("Université / École")

st.sidebar.header("🛠️ Compétences")

skills = st.sidebar.multiselect(
    "Compétences techniques *",
    ["Python", "ML", "NLP", "SQL", "Deep Learning", "Data Analysis"]
)

soft_skills = st.sidebar.multiselect(
    "Soft skills",
    ["Communication", "Travail en équipe", "Autonomie", "Adaptabilité"]
)

languages = st.sidebar.multiselect(
    "Langues",
    ["Français", "Anglais", "Espagnol", "Arabe"]
)

st.sidebar.header("💼 Expérience & projets")

experience = st.sidebar.text_area("Expérience professionnelle")
projects = st.sidebar.text_area("Projets académiques / personnels")

# ======================================================
# RECHERCHE OFFRE
# ======================================================
st.subheader("🔍 Offre ciblée")

job_query = st.text_input("Poste recherché *", "Data Scientist stage")
job_location = st.text_input("Localisation *", "Paris")
limit = st.slider("Nombre d'offres analysées", 5, 30, 10)

# ======================================================
# VALIDATION DES DONNÉES
# ======================================================
required_fields_filled = all([
    full_name,
    education_level,
    field_of_study,
    skills,
    job_query,
    job_location
])

# ======================================================
# LANCEMENT PIPELINE
# ======================================================
if st.button("🚀 Générer CV & Lettre"):
    if not required_fields_filled:
        st.error("❌ Merci de remplir tous les champs obligatoires (*)")
    else:
        with st.spinner("Génération des documents en cours..."):
            workflow = build_workflow()

            candidate_profile = {
                "identity": {
                    "full_name": full_name,
                    "email": email,
                    "phone": phone,
                    "location": location
                },
                "education": {
                    "level": education_level,
                    "field": field_of_study,
                    "university": university
                },
                "skills": skills,
                "soft_skills": soft_skills,
                "languages": languages,
                "experience": experience,
                "projects": projects
            }

            state = workflow.invoke({
                "query": job_query,
                "location": job_location,
                "limit": limit,
                "candidate_profile": candidate_profile
            })

        st.success("Documents générés avec succès ✅")

        # ======================================================
        # MATCHING
        # ======================================================
        st.subheader("📊 Résultats de matching")
        if state.get("matched_offers"):
            st.dataframe(pd.DataFrame(state["matched_offers"]))
        else:
            st.warning("Aucune offre matchée.")

        # ======================================================
        # DOCUMENTS
        # ======================================================
        st.subheader("📄 Documents générés")

        final_output = state.get("final_output", {})
        if final_output:
            col1, col2 = st.columns(2)

            with col1:
                with open(final_output["cv_pdf"], "rb") as f:
                    st.download_button("📥 Télécharger le CV", f, "cv.pdf")

            with col2:
                with open(final_output["letter_pdf"], "rb") as f:
                    st.download_button("📥 Télécharger la lettre", f, "lettre_motivation.pdf")

        # ======================================================
        # TRACKING
        # ======================================================
        st.subheader("🗂️ Suivi")
        if "tracking" in state:
            st.json(state["tracking"])

