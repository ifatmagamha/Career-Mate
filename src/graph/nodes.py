# src/graph/nodes.py
from __future__ import annotations

from pathlib import Path

from src.agents.collector import collect_offers
from src.agents.analyzer import analyze_offers
from src.agents.matcher import match_offers
from src.agents.writer import generate_documents  # on crée juste après
from src.agents.tracker import track_matches       # on crée juste après
from src.config.settings import settings
from src.graph.state import RecruitAIState
from src.storage.io import save_json


def node_collect(state: RecruitAIState) -> RecruitAIState:
    offers_raw = collect_offers(
        query=state["query"],
        location=state["location"],
        limit=state.get("limit", 10),
    )
    state["offers_raw"] = offers_raw
    save_json(Path(settings.DATA_DIR) / "job_offers_raw.json", offers_raw)
    return state


def node_analyze(state: RecruitAIState) -> RecruitAIState:
    offers_analyzed = analyze_offers(
        state["offers_raw"],
        llm_max=state.get("llm_max", 2),
    )
    state["offers_analyzed"] = offers_analyzed
    save_json(Path(settings.DATA_DIR) / "job_offers_analyzed.json", offers_analyzed)
    return state


def node_match(state: RecruitAIState) -> RecruitAIState:
    matches = match_offers(
        state["candidate"],
        state["offers_analyzed"],
        top_k=state.get("top_k", 10),
    )
    state["matches"] = matches
    save_json(Path(settings.DATA_DIR) / "matches.json", matches)
    return state


def node_write(state: RecruitAIState) -> RecruitAIState:
    # generate only for top1 to avoid quota
    matches = state.get("matches", [])
    if not matches:
        state["generated_cv"] = None
        state["generated_letter"] = None
        return state

    top = matches[0]
    # find analyzed offer corresponding to top url
    offer = next((o for o in state["offers_analyzed"] if str(o.url) == str(top.url)), None)
    if offer is None:
        state["generated_cv"] = None
        state["generated_letter"] = None
        return state

    cv_text, letter_text = generate_documents(state["candidate"], offer)
    state["generated_cv"] = cv_text
    state["generated_letter"] = letter_text

    out_dir = Path(settings.DATA_DIR) / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "generated_cv.txt").write_text(cv_text or "", encoding="utf-8")
    (out_dir / "generated_letter.txt").write_text(letter_text or "", encoding="utf-8")
    return state


def node_track(state: RecruitAIState) -> RecruitAIState:
    tracking_path = state.get("tracking_path") or str(Path(settings.DATA_DIR) / "tracking.json")
    track_matches(state.get("matches", []), tracking_path)
    state["tracking_path"] = tracking_path
    return state
