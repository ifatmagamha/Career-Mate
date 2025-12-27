import streamlit as st
from graph.workflow import build_workflow

st.set_page_config(page_title="RecruitIA", layout="wide")
st.title("🤖 RecruitIA - Générateur de candidatures automatisé")

# --- Étape 1 : Informations candidat ---
st.header("1️⃣ Informations candidat")

name = st.text_input("Nom complet")
email = st.text_input("Email")
target_role = st.text_input("Poste visé", "Data Scientist")
skills = st.text_area("Compétences techniques (séparées par une virgule)")
soft_skills = st.text_area("Soft skills (séparées par une virgule)")
experience_level = st.selectbox("Niveau d'expérience", ["Junior", "Mid-Level", "Senior"])
location = st.text_input("Localisation souhaitée", "Paris")

# --- Bouton pour lancer le pipeline ---
if st.button("Lancer le pipeline"):

    if not (name and email and skills):
        st.error("Veuillez remplir au moins le nom, email et les compétences techniques.")
        st.stop()

    # --- Profil candidat ---
    candidate_profile = {
        "name": name,
        "email": email,
        "target_role": target_role,
        "skills": [s.strip() for s in skills.split(",") if s.strip()],
        "soft_skills": [s.strip() for s in soft_skills.split(",") if s.strip()],
        "experience_level": experience_level,
    }

    st.info("🟢 Exécution du pipeline RecruitIA...")
    app = build_workflow()

    initial_state = {
        "query": target_role,
        "location": location,
        "limit": 20,
        "candidate_profile": candidate_profile
    }

    try:
        final_state = app.invoke(initial_state)
    except Exception as e:
        st.error(f"❌ Erreur pendant l'exécution du workflow : {e}")
        st.stop()

    output = final_state.get("final_output", {})
    best_offer = output.get("target_offer")

    if not best_offer:
        st.warning("Aucune offre pertinente trouvée.")
        st.stop()

    # --- Résumé offre ---
    st.success(
        f"✅ Meilleure offre trouvée : "
        f"{best_offer['offer_title']} chez {best_offer['company']}"
    )
    st.write("📊 Score de matching :", best_offer.get("matching_score"))

    # --- Affichage CV ---
    st.header("📄 CV généré")
    cv_md = output.get("cv_markdown")

    if cv_md:
        st.markdown(cv_md, unsafe_allow_html=False)
    else:
        st.warning("CV non généré.")

    # --- Affichage Lettre ---
    st.header("✉️ Lettre de motivation générée")
    letter_md = output.get("cover_letter_markdown")

    if letter_md:
        st.markdown(letter_md, unsafe_allow_html=False)
    else:
        st.warning("Lettre de motivation non générée.")

    # --- Tracking ---
    st.header("📝 Suivi de la candidature")
    st.json(final_state.get("tracking", {}))
