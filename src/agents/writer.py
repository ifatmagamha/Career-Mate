# src/agents/writer.py
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from src.config.logging import logger
from src.schemas.candidate import CandidateProfile
from src.schemas.job_offer import OfferAnalyzed


# -----------------------------
# Helpers (text formatting)
# -----------------------------
def _safe(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_sentences(text: str, max_items: int = 6) -> List[str]:
    text = _normalize_whitespace(text)
    if not text:
        return []
    # Split on ".", "•", "-" lines
    parts: List[str] = []
    for chunk in re.split(r"[\n•]+", text):
        chunk = chunk.strip(" -\t")
        if not chunk:
            continue
        # Further split on "."
        for s in chunk.split("."):
            s = s.strip()
            if len(s) < 8:
                continue
            parts.append(s)
    # Dedup while keeping order
    seen = set()
    out = []
    for p in parts:
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
        if len(out) >= max_items:
            break
    return out


def _dedup_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for it in items:
        t = (it or "").strip()
        if not t:
            continue
        k = t.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(t)
    return out


def _top_skills(candidate: CandidateProfile, offer: OfferAnalyzed, max_skills: int = 12) -> List[str]:
    cand_kw = [str(x).strip() for x in (getattr(candidate, "target_keywords", None) or [])]
    offer_sk = [str(x).strip() for x in (offer.skills or [])]

    cand_kw = [x for x in cand_kw if x]
    offer_sk = [x for x in offer_sk if x]

    # Prioritize intersection, then candidate keywords, then offer skills
    inter = []
    cand_set = {x.lower() for x in cand_kw}
    for s in offer_sk:
        if s.lower() in cand_set:
            inter.append(s)

    merged = _dedup_keep_order(inter + cand_kw + offer_sk)
    return merged[:max_skills]


# -----------------------------
# Minimal PDF layout engine
# -----------------------------
@dataclass
class PDFStyle:
    page_w: float = A4[0]
    page_h: float = A4[1]
    margin_l: float = 1.7 * cm
    margin_r: float = 1.7 * cm
    margin_t: float = 1.6 * cm
    margin_b: float = 1.6 * cm

    font: str = "Helvetica"
    font_bold: str = "Helvetica-Bold"

    title_size: int = 16
    h2_size: int = 11
    text_size: int = 10
    small_size: int = 9

    line_gap: float = 3.0  # extra spacing per line


def _wrap_lines(text: str, max_width: float, font_name: str, font_size: int) -> List[str]:
    # Greedy wrap by words
    words = (text or "").split()
    if not words:
        return []
    lines: List[str] = []
    cur: List[str] = []
    for w in words:
        test = (" ".join(cur + [w])).strip()
        if stringWidth(test, font_name, font_size) <= max_width:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines


def _draw_paragraph(c: canvas.Canvas, x: float, y: float, text: str, style: PDFStyle, font_name: str, font_size: int) -> float:
    max_w = style.page_w - style.margin_l - style.margin_r
    lines = _wrap_lines(text, max_w, font_name, font_size)
    c.setFont(font_name, font_size)
    for ln in lines:
        c.drawString(x, y, ln)
        y -= (font_size + style.line_gap)
    return y


def _draw_bullets(c: canvas.Canvas, x: float, y: float, bullets: List[str], style: PDFStyle, font_size: int = 10) -> float:
    max_w = style.page_w - style.margin_l - style.margin_r
    bullet_indent = 12
    c.setFont(style.font, font_size)
    for b in bullets:
        b = b.strip()
        if not b:
            continue
        wrapped = _wrap_lines(b, max_w - bullet_indent, style.font, font_size)
        if not wrapped:
            continue
        # bullet dot
        c.drawString(x, y, "•")
        c.drawString(x + bullet_indent, y, wrapped[0])
        y -= (font_size + style.line_gap)
        for ln in wrapped[1:]:
            c.drawString(x + bullet_indent, y, ln)
            y -= (font_size + style.line_gap)
    return y


def _section_title(c: canvas.Canvas, x: float, y: float, title: str, style: PDFStyle) -> float:
    c.setFont(style.font_bold, style.h2_size)
    c.drawString(x, y, title.upper())
    y -= (style.h2_size + style.line_gap)
    # thin separator
    c.setLineWidth(0.6)
    c.line(x, y, style.page_w - style.margin_r, y)
    y -= 8
    return y


# -----------------------------
# Public API
# -----------------------------
def generate_cv_pdf(
    candidate: CandidateProfile,
    offer: OfferAnalyzed,
    out_path: str,
) -> str:
    """
    Generate a clean 1-page CV (best-effort) and save to out_path.
    Returns out_path.
    """
    style = PDFStyle()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    c = canvas.Canvas(out_path, pagesize=A4)
    x = style.margin_l
    y = style.page_h - style.margin_t

    # Header
    name = _safe(getattr(candidate, "full_name", None), "Candidat")
    email = _safe(getattr(candidate, "email", None), "")
    phone = _safe(getattr(candidate, "phone", None), "")
    location = _safe(getattr(candidate, "location", None), "")
    github = _safe(getattr(candidate, "github_url", None), "")
    linkedin = _safe(getattr(candidate, "linkedin_url", None), "")

    c.setFont(style.font_bold, style.title_size)
    c.drawString(x, y, name)
    y -= (style.title_size + 6)

    c.setFont(style.font, style.small_size)
    header_line = " | ".join([p for p in [email, phone, location] if p])
    if header_line:
        c.drawString(x, y, header_line)
        y -= (style.small_size + 6)

    links = " | ".join([p for p in [github, linkedin] if p])
    if links:
        c.drawString(x, y, links)
        y -= (style.small_size + 10)

    # Title aligned to offer
    target_title = _safe(offer.title, "Stage")
    company = _safe(offer.company, "")
    c.setFont(style.font_bold, 12)
    c.drawString(x, y, f"CV — Candidature {target_title}" + (f" ({company})" if company else ""))
    y -= (12 + 12)

    # Summary (from cv_text + offer summary)
    y = _section_title(c, x, y, "Profil", style)
    cv_text = _safe(getattr(candidate, "cv_text", None), "")
    summary_bits = _split_sentences(cv_text, max_items=3)
    offer_sum = _safe(getattr(offer, "summary", None), "")
    if offer_sum and offer_sum.lower() not in (cv_text.lower() if cv_text else ""):
        summary_bits.append(offer_sum)
    summary_bits = _dedup_keep_order(summary_bits)[:4]
    if not summary_bits:
        summary_bits = ["Étudiant(e) motivé(e) avec une forte appétence Data / ML et une capacité à livrer des projets concrets."]

    y = _draw_bullets(c, x, y, summary_bits, style, font_size=style.text_size)
    y -= 6

    # Skills
    y = _section_title(c, x, y, "Compétences", style)
    skills = _top_skills(candidate, offer, max_skills=14)
    if not skills:
        skills = ["Python", "SQL", "pandas", "scikit-learn", "Machine Learning"]
    # Print as 2 lines-ish
    c.setFont(style.font, style.text_size)
    skills_line = " • ".join(skills)
    y = _draw_paragraph(c, x, y, skills_line, style, style.font, style.text_size)
    y -= 6

    # Projects / Experience (best-effort from cv_text)
    y = _section_title(c, x, y, "Projets & Expérience", style)
    proj = _split_sentences(cv_text, max_items=6)
    # Boost with offer missions keywords
    missions = offer.missions or []
    if missions:
        # Add 1-2 mission-inspired lines if not present
        for m in missions[:2]:
            mm = _safe(m, "")
            if mm and all(mm.lower() not in p.lower() for p in proj):
                proj.append(mm)
    proj = _dedup_keep_order(proj)[:6]
    if not proj:
        proj = ["Projet ML: classification/prédiction avec features + évaluation.", "Dashboard Streamlit: visualisation & reporting."]

    y = _draw_bullets(c, x, y, proj, style, font_size=style.text_size)
    y -= 6

    # Education (fallback)
    y = _section_title(c, x, y, "Formation", style)
    edu = _safe(getattr(candidate, "education", None), "")
    if edu:
        y = _draw_paragraph(c, x, y, edu, style, style.font, style.text_size)
    else:
        y = _draw_bullets(
            c,
            x,
            y,
            ["Master/Ingénieur (en cours) — Data / IA (à compléter)", "Cours clés: ML, Stats, Data Engineering (à compléter)"],
            style,
            font_size=style.text_size,
        )
    y -= 6

    # Footer
    c.setFont(style.font, style.small_size)
    c.drawString(x, style.margin_b * 0.65, f"Généré par RecruitAI — {datetime.now().strftime('%Y-%m-%d')}")
    c.showPage()
    c.save()

    logger.info(f"[writer] saved CV -> {out_path}")
    return out_path


def generate_letter_pdf(
    candidate: CandidateProfile,
    offer: OfferAnalyzed,
    out_path: str,
) -> str:
    """
    Generate a clean cover letter (1 page) and save to out_path.
    Returns out_path.
    """
    style = PDFStyle()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    c = canvas.Canvas(out_path, pagesize=A4)
    x = style.margin_l
    y = style.page_h - style.margin_t

    # Sender block
    name = _safe(getattr(candidate, "full_name", None), "Candidat")
    email = _safe(getattr(candidate, "email", None), "")
    phone = _safe(getattr(candidate, "phone", None), "")
    location = _safe(getattr(candidate, "location", None), "")

    c.setFont(style.font_bold, 12)
    c.drawString(x, y, name)
    y -= 16
    c.setFont(style.font, style.text_size)
    for line in [email, phone, location]:
        if line:
            c.drawString(x, y, line)
            y -= 13
    y -= 8

    # Recipient / subject
    company = _safe(offer.company, "l'entreprise")
    role = _safe(offer.title, "Stage")
    city = _safe(offer.location, "")
    c.setFont(style.font_bold, 12)
    c.drawString(x, y, f"Objet : Candidature — {role}")
    y -= 18

    c.setFont(style.font, style.text_size)
    y = _draw_paragraph(c, x, y, "Madame, Monsieur,", style, style.font, style.text_size)
    y -= 6

    # Build letter content
    skills = _top_skills(candidate, offer, max_skills=8)
    skills_txt = ", ".join(skills[:5]) if skills else "Python, SQL, Machine Learning"

    missions = offer.missions or []
    reqs = offer.requirements or []
    # Pick 2 lines max
    mission_txt = ""
    if missions:
        mission_txt = missions[0]
    elif offer.summary:
        mission_txt = offer.summary

    motivation = (
        f"Je vous soumets ma candidature pour le poste de {role} chez {company}"
        + (f" à {city}" if city else "")
        + ". "
        "Mon profil et mes projets en data correspondent bien aux attentes d’un stage orienté analyse et modélisation."
    )

    paragraph_2 = (
        f"J’ai développé des bases solides en {skills_txt}. "
        "J’ai déjà réalisé des projets appliqués (modèles ML, préparation de données, visualisation) "
        "et je suis à l’aise pour itérer rapidement et documenter des résultats."
    )

    paragraph_3 = (
        "Je suis particulièrement motivé(e) par cette opportunité car elle me permettra de contribuer concrètement "
        "à des sujets data en environnement professionnel"
        + (f", notamment autour de : {mission_txt}." if mission_txt else ".")
    )

    # If requirements exist, mention alignment
    if reqs:
        paragraph_3 += " Je pense correspondre aux prérequis clés, et je suis prêt(e) à monter en compétence rapidement."

    closing = (
        "Je serais ravi(e) d’échanger avec vous lors d’un entretien afin de détailler ma motivation "
        "et la valeur que je peux apporter à votre équipe.\n\n"
        "Cordialement,"
    )

    for p in [motivation, paragraph_2, paragraph_3, closing]:
        y = _draw_paragraph(c, x, y, p, style, style.font, style.text_size)
        y -= 10

    c.setFont(style.font_bold, style.text_size)
    c.drawString(x, y, name)

    c.showPage()
    c.save()

    logger.info(f"[writer] saved letter -> {out_path}")
    return out_path


def generate_cv_and_letter_pdfs(
    user_id: str,
    candidate: CandidateProfile,
    offer: OfferAnalyzed,
    out_dir: str = "data/generated",
) -> Dict[str, str]:
    """
    Main entry for the Writer agent.
    Creates and saves:
      - {out_dir}/{user_id}_cv.pdf
      - {out_dir}/{user_id}_lettre.pdf

    Returns:
      {"cv_pdf": "...", "letter_pdf": "..."}
    """
    os.makedirs(out_dir, exist_ok=True)

    uid = (user_id or "user").strip()
    uid = re.sub(r"[^a-zA-Z0-9_\-]+", "_", uid)

    cv_path = os.path.join(out_dir, f"{uid}_cv.pdf")
    letter_path = os.path.join(out_dir, f"{uid}_lettre.pdf")

    generate_cv_pdf(candidate, offer, cv_path)
    generate_letter_pdf(candidate, offer, letter_path)

    return {"cv_pdf": cv_path, "letter_pdf": letter_path}
