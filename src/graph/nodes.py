# src/graph/nodes.py
from __future__ import annotations

from typing import Optional

from src.config.logging import logger
from src.graph.state import RecruitAIState
from src.schemas.job_offer import OfferAnalyzed

from src.agents.collector import collect_offers
from src.agents.analyzer import analyze_offers

# ⚠️ adapte si ton matcher a un autre nom
from src.agents.matcher import match_offers

# ⚠️ adapte si ton writer a un autre nom
from src.agents.writer import generate_cv_and_letter_pdfs

# tracker (si tu l’as ajouté comme on a fait)
from src.agents.tracker import upsert_application


def _pick_offer(state: RecruitAIState) -> Optional[OfferAnalyzed]:
    """
    Select offer for writer/tracker:
    - if state.selected_offer_url exists => pick that
    - else pick best match by score
    """
    offers = state.get("offers_analyzed") or []
    if not offers:
        return None

    selected = state.get("selected_offer_url")
    if selected:
        for o in offers:
            if str(o.url) == str(selected):
                return o

    matches = state.get("matches") or []
    if matches:
        best = sorted(matches, key=lambda m: m.score, reverse=True)[0]
        best_url = str(best.url)
        for o in offers:
            if str(o.url) == best_url:
                return o

    # fallback: first analyzed
    return offers[0]


def collector_node(state: RecruitAIState) -> RecruitAIState:
    query = state.get("query", "Data Science")
    location = state.get("location", "Paris")
    limit = int(state.get("limit", 10))

    offers_raw = collect_offers(query=query, location=location, limit=limit)
    state["offers_raw"] = offers_raw
    logger.info(f"[graph] collector_node -> {len(offers_raw)} offers_raw")
    return state


def analyzer_node(state: RecruitAIState) -> RecruitAIState:
    offers_raw = state.get("offers_raw") or []
    if not offers_raw:
        state["offers_analyzed"] = []
        logger.warning("[graph] analyzer_node: no offers_raw")
        return state

    offers_analyzed = analyze_offers(offers_raw)
    state["offers_analyzed"] = offers_analyzed
    logger.info(f"[graph] analyzer_node -> {len(offers_analyzed)} offers_analyzed")
    return state


def matcher_node(state: RecruitAIState) -> RecruitAIState:
    candidate = state.get("candidate")
    offers_analyzed = state.get("offers_analyzed") or []

    if candidate is None:
        state["matches"] = []
        logger.warning("[graph] matcher_node: candidate missing")
        return state

    if not offers_analyzed:
        state["matches"] = []
        logger.warning("[graph] matcher_node: no offers_analyzed")
        return state

    matches = match_offers(candidate, offers_analyzed)
    state["matches"] = matches
    logger.info(f"[graph] matcher_node -> {len(matches)} matches")
    return state


def writer_node(state: RecruitAIState) -> RecruitAIState:
    candidate = state.get("candidate")
    if candidate is None:
        logger.warning("[graph] writer_node: candidate missing")
        return state

    offer = _pick_offer(state)
    if offer is None:
        logger.warning("[graph] writer_node: no offer selected")
        return state

    user_id = state.get("user_id", "id_user")

    # ✅ doit retourner des paths pdf (ou dict) selon ton implémentation
    # Exemple attendu: {"cv_pdf": "...", "letter_pdf": "..."}
    generated = generate_cv_and_letter_pdfs(
        user_id=user_id,
        candidate=candidate,
        offer=offer,
    )

    # Normalize
    if isinstance(generated, dict):
        cv_pdf = generated.get("cv_pdf")
        letter_pdf = generated.get("letter_pdf")
    else:
        # si ton writer retourne tuple (cv, letter)
        cv_pdf, letter_pdf = generated

    state["generated"] = {
        "offer_url": str(offer.url),
        "cv_pdf": cv_pdf,
        "letter_pdf": letter_pdf,
    }
    logger.info(f"[graph] writer_node -> cv={cv_pdf} letter={letter_pdf}")
    return state


def tracker_node(state: RecruitAIState) -> RecruitAIState:
    user_id = state.get("user_id", "id_user")

    offer = _pick_offer(state)
    if offer is None:
        logger.warning("[graph] tracker_node: no offer selected")
        return state

    gen = state.get("generated") or {}
    cv_pdf = gen.get("cv_pdf")
    letter_pdf = gen.get("letter_pdf")

    rec = upsert_application(
        user_id=user_id,
        offer=offer,
        cv_pdf=cv_pdf,
        letter_pdf=letter_pdf,
        status="to_apply",
    )
    state["tracking"] = rec.model_dump(mode="json")
    logger.info("[graph] tracker_node -> saved tracking record")
    return state
