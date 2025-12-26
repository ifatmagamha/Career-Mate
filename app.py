import streamlit as st
from graph.workflow import build_workflow
from services.latex_compiler import compile_latex

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
    else:
        # Créer le profil candidat
        candidate_profile = {
            "name": name,
            "email": email,
            "target_role": target_role,
            "skills": [s.strip() for s in skills.split(",")],
            "soft_skills": [s.strip() for s in soft_skills.split(",")],
            "experience_level": experience_level,
        }

        # --- Exécution du workflow ---
        st.info("🟢 Exécution du pipeline...")
        app = build_workflow()

        # On passe uniquement les infos nécessaires
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
        best_offer = output.get("target_offer", {})

        if not best_offer:
            st.warning("Aucune offre trouvée pour votre profil.")
            st.stop()

        st.success(f"✅ Meilleure offre trouvée : {best_offer['offer_title']} chez {best_offer['company']}")
        st.write("Score de matching :", best_offer.get("matching_score"))

        # --- Génération des PDFs ---
        st.info("📄 Génération du CV et de la lettre de motivation...")

        try:
            cv_pdf = compile_latex(output.get("cv_latex", ""), "cv")
            letter_pdf = compile_latex(output.get("cover_letter_latex", ""), "cover_letter")
        except Exception as e:
            st.error(f"❌ Erreur lors de la génération des PDFs : {e}")
            st.stop()

        # --- Boutons de téléchargement ---
        with open(cv_pdf, "rb") as f:
            st.download_button(
                "Télécharger CV",
                f.read(),
                file_name="cv.pdf"
            )

        with open(letter_pdf, "rb") as f:
            st.download_button(
                "Télécharger Lettre de motivation",
                f.read(),
                file_name="cover_letter.pdf"
            )

        # --- Affichage du suivi de candidature ---
        st.write("📝 Suivi de l'application :")
        st.json(final_state.get("tracking", {}))
