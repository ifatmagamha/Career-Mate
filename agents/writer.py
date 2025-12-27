import os
import json
from typing import Dict, Any
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from google import genai


OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

CV_PROMPT = """
Tu es un moteur de génération de documents.

RÈGLE ABSOLUE :
- NE PAS écrire d'introduction
- NE PAS expliquer ce que tu fais
- NE PAS commenter
- NE PAS parler à la première personne

Tu dois produire UNIQUEMENT le contenu du CV final.

FORMAT STRICT :
- Markdown
- Commence DIRECTEMENT par le nom du candidat
- Titres avec ###
- Listes avec -

SI TU ÉCRIS UNE PHRASE D'INTRODUCTION, LA RÉPONSE EST FAUSSE.

Profil candidat :
{candidate}

Offre ciblée :
{offer}
"""



LETTER_PROMPT = """
Tu es un moteur de génération de documents.

RÈGLE ABSOLUE :
- AUCUNE introduction
- AUCUNE explication
- AUCUN commentaire

Tu dois produire UNIQUEMENT la lettre finale.

FORMAT STRICT :
- Markdown
- Commence DIRECTEMENT par "Madame, Monsieur,"

SI TU AJOUTES DU TEXTE AVANT, LA RÉPONSE EST FAUSSE.

Profil candidat :
{candidate}

Offre ciblée :
{offer}
"""


class WriterAgent:
    def __init__(self, model: str = "gemini-2.5-pro"):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY manquante")

        self.client = genai.Client(api_key=api_key)
        self.model = model

    def _generate_text(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        return response.text.strip()

    def _write_pdf(self, filename: str, content: str):
        path = os.path.join(OUTPUT_DIR, filename)

        styles = getSampleStyleSheet()
        doc = SimpleDocTemplate(path, pagesize=A4)

        elements = []
        for line in content.split("\n"):
            elements.append(Paragraph(line, styles["Normal"]))
            elements.append(Spacer(1, 10))

        doc.build(elements)
        return path

    def run(self, state: dict) -> dict:
        matched_offers = state.get("matched_offers")
        candidate = state.get("candidate_profile")

        if not matched_offers or not candidate:
            raise ValueError("Données manquantes")

        best_offer = matched_offers[0]

        cv_text = self._generate_text(
            CV_PROMPT.format(
                candidate=json.dumps(candidate, indent=2),
                offer=json.dumps(best_offer, indent=2),
            )
        )

        letter_text = self._generate_text(
            LETTER_PROMPT.format(
                candidate=json.dumps(candidate, indent=2),
                offer=json.dumps(best_offer, indent=2),
            )
        )

        cv_path = self._write_pdf("cv.pdf", cv_text)
        letter_path = self._write_pdf("lettre_motivation.pdf", letter_text)

        state["final_output"] = {
            "cv_pdf": cv_path,
            "letter_pdf": letter_path,
            "target_offer": best_offer,
        }

        return state
