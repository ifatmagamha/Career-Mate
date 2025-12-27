# agents/analyzer.py

import os
import json
import re
import time
from typing import Dict, Any, List

from google import genai

import os
from dotenv import load_dotenv

load_dotenv()  # charge les variables du fichier .env

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")

if GEMINI_API_KEY is None:
    raise EnvironmentError("GEMINI_API_KEY manquante")

ANALYSIS_PROMPT = """
Tu es un expert en recrutement.

Analyse l'offre d'emploi suivante.
Même si certaines informations ne sont pas explicitement mentionnées,
déduis-les raisonnablement à partir du contexte du poste.

Retourne STRICTEMENT un JSON valide avec les champs :

- title
- company
- skills
- soft_skills
- missions
- experience_level
- contract_type
- seniority

Offre :
\"\"\"
{job_text}
\"\"\"
"""


class AnalyzerAgent:
    def __init__(self, model: str = "gemini-2.0-flash", sleep_time: float = 1.0):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY manquante")

        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.sleep_time = sleep_time

    def _analyze_offer(self, job: Dict[str, Any]) -> Dict[str, Any]:
        job_text = f"""
Titre: {job.get('title', '')}
Entreprise: {job.get('company', '')}
Description: {job.get('description', '')}
"""

        response = self.client.models.generate_content(
            model=self.model,
            contents=ANALYSIS_PROMPT.format(job_text=job_text)
        )

        try:
            json_text = re.search(r"\{.*\}", response.text, re.S).group()
            analysis = json.loads(json_text)
        except Exception:
            analysis = {
                "title": job.get("title"),
                "company": job.get("company"),
                "skills": [],
                "soft_skills": [],
                "missions": [],
                "experience_level": "Unknown",
                "contract_type": "Unknown",
                "seniority": "Unknown",
            }

        analysis["source_url"] = job.get("url")
        return analysis

    def run(self, state: dict) -> dict:
        """
        LangGraph node
        Expected state:
        {
            "raw_offers": list
        }
        """

        analyzed_offers: List[Dict[str, Any]] = []

        for job in state.get("raw_offers", []):
            analyzed_offers.append(self._analyze_offer(job))
            time.sleep(self.sleep_time)

        state["analyzed_offers"] = analyzed_offers
        return state
