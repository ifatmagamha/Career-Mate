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
import time
from src.api.agent_traces import log_agent_trace

def node_collect(state: RecruitAIState) -> RecruitAIState:
    start_time = time.time()
    try:
        offers_raw = collect_offers(
            query=state["query"],
            location=state.get("location", "Paris"), # Default for evaulation
            limit=state.get("limit", 10),
        )
        state["offers_raw"] = offers_raw
        save_json(Path(settings.DATA_DIR) / "job_offers_raw.json", offers_raw)
        
        duration = (time.time() - start_time) * 1000
        log_agent_trace("Collector", f"Query: {state['query']}", f"Found {len(offers_raw)} offers", duration)
        return state
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        log_agent_trace("Collector", state["query"], str(e), duration, status="error")
        raise e

def node_analyze(state: RecruitAIState) -> RecruitAIState:
    start_time = time.time()
    try:
        offers_analyzed = analyze_offers(
            state["offers_raw"],
            llm_max=state.get("llm_max", 2),
        )
        state["offers_analyzed"] = offers_analyzed
        save_json(Path(settings.DATA_DIR) / "job_offers_analyzed.json", offers_analyzed)
        
        duration = (time.time() - start_time) * 1000
        log_agent_trace("Analyzer", f"Input: {len(state['offers_raw'])} raw", f"Analyzed {len(offers_analyzed)} offers", duration)
        return state
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        log_agent_trace("Analyzer", "Batch analysis", str(e), duration, status="error")
        raise e

def node_match(state: RecruitAIState) -> RecruitAIState:
    start_time = time.time()
    try:
        matches = match_offers(
            state["candidate"],
            state["offers_analyzed"],
            top_k=state.get("top_k", 10),
        )
        state["matches"] = matches
        save_json(Path(settings.DATA_DIR) / "matches.json", matches)
        
        duration = (time.time() - start_time) * 1000
        log_agent_trace("Matcher", f"Candidate: {state['candidate'].full_name}", f"Ranked {len(matches)} matches", duration)
        return state
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        log_agent_trace("Matcher", "Matching process", str(e), duration, status="error")
        raise e


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


def node_report_matches(state: RecruitAIState) -> RecruitAIState:
    """Generates a conversational summary of matched jobs."""
    from langchain_core.messages import AIMessage
    
    matches = state.get("matches", [])
    if not matches:
        return {"messages": [AIMessage(content="I couldn't find any job offers matching your request at the moment.")]}
    
    count = len(matches)
    top_matches = matches[:3]
    
    summary = f"I found {count} potential job matches for you! Here are the top picks:\n\n"
    for i, m in enumerate(top_matches, 1):
        summary += f"{i}. **{m.title}** at {m.company} ({m.score}% match)\n"
    
    summary += "\nYou can view all details in the Job Explorer tab."
    
    return {"messages": [AIMessage(content=summary)], "active_node": "job_pipeline"}
