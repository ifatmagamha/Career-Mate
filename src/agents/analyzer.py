from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Protocol

from schemas.job import JobOfferRaw, JobOfferParsed


class LLMClient(Protocol):
    def generate(self, *, model: str, prompt: str) -> str:
        ...


ANALYSIS_PROMPT = """Tu es un expert en recrutement.
Analyse l'offre d'emploi suivante et retourne STRICTEMENT un JSON valide.

Champs attendus (utilise [] si inconnu) :
- title (str)
- company (str|null)
- location (str|null)
- contract_type (str|null)
- remote_policy (str|null)  # onsite/hybrid/remote si possible
- seniority (str|null)      # junior/mid/senior
- missions (liste[str])
- requirements (liste[str])
- skills (liste[str])       # compétences techniques
- tools_stack (liste[str])  # outils/stack (si distinct)
- languages (liste[str])    # langues humaines
- education_level (str|null)
- years_experience_min (number|null)
- summary (str|null)
- keywords (liste[str])

Offre:
\"\"\"{job_text}\"\"\"
"""


def _extract_json(text: str) -> dict[str, Any]:
    # récupère le premier objet JSON trouvé
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise ValueError("No JSON found in LLM output")
    return json.loads(m.group())


def _norm_list(xs: Any) -> list[str]:
    if not xs:
        return []
    if isinstance(xs, str):
        return [xs.strip()]
    if isinstance(xs, list):
        out = []
        for x in xs:
            if x is None:
                continue
            out.append(str(x).strip())
        return [x for x in out if x]
    return []


@dataclass
class AnalyzerAgent:
    llm: LLMClient
    model: str = "gemini-2.0-flash"
    sleep_s: float = 0.7

    def analyze_one(self, job: JobOfferRaw) -> JobOfferParsed:
        job_text = f"""Titre: {job.title or ''}
Entreprise: {job.company or ''}
Localisation: {job.location or ''}
Description: {job.raw_text or ''}
URL: {str(job.url) if job.url else ''}
"""
        raw = self.llm.generate(model=self.model, prompt=ANALYSIS_PROMPT.format(job_text=job_text))

        try:
            d = _extract_json(raw)
        except Exception:
            d = {}

        parsed = JobOfferParsed(
            id=job.id,
            source=job.source,
            url=job.url,
            title=(d.get("title") or job.title or "").strip() or "Unknown title",
            company=d.get("company") or job.company,
            location=d.get("location") or job.location,
            contract_type=d.get("contract_type"),
            remote_policy=d.get("remote_policy"),
            seniority=d.get("seniority"),
            missions=_norm_list(d.get("missions")),
            requirements=_norm_list(d.get("requirements")),
            skills=[s.lower() for s in _norm_list(d.get("skills"))],
            tools_stack=[t.lower() for t in _norm_list(d.get("tools_stack"))],
            languages=_norm_list(d.get("languages")),
            education_level=d.get("education_level"),
            years_experience_min=d.get("years_experience_min"),
            keywords=_norm_list(d.get("keywords")),
            summary=d.get("summary"),
        )
        return parsed

    def analyze_many(self, jobs: list[JobOfferRaw]) -> list[JobOfferParsed]:
        out: list[JobOfferParsed] = []
        for i, j in enumerate(jobs, start=1):
            print(f"[Analyzer] {i}/{len(jobs)} {j.title}")
            out.append(self.analyze_one(j))
            time.sleep(self.sleep_s)
        return out
