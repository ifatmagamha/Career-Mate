from __future__ import annotations

from dataclasses import dataclass

from graph.state import RecruitAIState

from agents.collector import CollectorAgent, GoogleJobsCollector
from agents.analyzer import AnalyzerAgent
from agents.matcher import MatcherAgent
from agents.writer import WriterAgent
from agents.tracker import TrackerAgent

from config.settings import settings
from llm.gemini_client import GeminiClient

# RAG (memory - no chromadb)
from rag.embeddings import EmbeddingModel
from rag.memory_store import MemoryVectorStore
from rag.indexer import OfferIndexer
from rag.retriever import OfferRetriever

# Offer quality: filter + fetch
from services.url_filters import is_probably_listing_page
from services.web_fetcher import WebFetcher


@dataclass
class GraphDeps:
    # Agents
    collector: CollectorAgent
    analyzer: AnalyzerAgent
    matcher: MatcherAgent
    writer: WriterAgent
    tracker: TrackerAgent

    # Fetcher
    fetcher: WebFetcher

    # RAG
    store: MemoryVectorStore
    embedder: EmbeddingModel
    indexer: OfferIndexer
    retriever: OfferRetriever


def build_deps() -> GraphDeps:
    settings.validate()

    # LLM
    llm = GeminiClient(api_key=settings.gemini_api_key)

    # Collector
    collector = CollectorAgent(
        collectors=[
            GoogleJobsCollector(
                api_key=settings.google_api_key,
                cse_id=settings.google_cse_id,
            )
        ]
    )

    # Core agents
    analyzer = AnalyzerAgent(llm=llm)
    matcher = MatcherAgent()
    writer = WriterAgent(llm=llm)
    tracker = TrackerAgent(path=settings.tracking_path)

    # Fetcher (HTML -> text)
    fetcher = WebFetcher()

    # RAG components (in-memory + persisted .pkl)
    store = MemoryVectorStore(path="data/vectorstore/offers_index.pkl")
    embedder = EmbeddingModel(model_name="all-MiniLM-L6-v2")
    indexer = OfferIndexer(store=store, embedder=embedder)
    retriever = OfferRetriever(store=store, embedder=embedder)

    return GraphDeps(
        collector=collector,
        analyzer=analyzer,
        matcher=matcher,
        writer=writer,
        tracker=tracker,
        fetcher=fetcher,
        store=store,
        embedder=embedder,
        indexer=indexer,
        retriever=retriever,
    )


def _push_error(state: RecruitAIState, msg: str) -> RecruitAIState:
    errs = state.get("errors", [])
    errs.append(msg)
    state["errors"] = errs
    return state


def collector_node(state: RecruitAIState, deps: GraphDeps) -> RecruitAIState:
    try:
        query = state.get("query", "data science internship")
        location = state.get("location", "France")
        limit = int(state.get("limit", 20))

        offers = deps.collector.run(query=query, location=location, limit=limit)
        state["offers_raw"] = offers
        return state
    except Exception as e:
        return _push_error(state, f"[collector_node] {e}")


def fetch_node(state: RecruitAIState, deps: GraphDeps) -> RecruitAIState:
    """
    Filter listing/search pages and fetch real job-page text into raw_text.
    Goal: improve Analyzer extraction (company/requirements/missions).
    """
    try:
        offers = state.get("offers_raw", [])
        if not offers:
            return _push_error(state, "[fetch_node] No offers_raw found")

        filtered_out = 0
        fetched = 0
        kept = []

        for o in offers:
            url = str(getattr(o, "url", "") or "")

            # Drop listing pages (search/results)
            if url and is_probably_listing_page(url):
                filtered_out += 1
                continue

            # Fetch page content and overwrite raw_text if good
            if url:
                txt = deps.fetcher.fetch_text(url)
                if txt and len(txt) > 300:
                    # assumes o is mutable
                    o.raw_text = txt
                    fetched += 1

            kept.append(o)

        state["offers_raw"] = kept
        state["filtered_count"] = filtered_out
        state["fetched_count"] = fetched
        return state
    except Exception as e:
        return _push_error(state, f"[fetch_node] {e}")


def analyzer_node(state: RecruitAIState, deps: GraphDeps) -> RecruitAIState:
    try:
        raws = state.get("offers_raw", [])
        if not raws:
            return _push_error(state, "[analyzer_node] No offers_raw found")

        parsed = deps.analyzer.analyze_many(raws)
        state["offers_parsed"] = parsed
        return state
    except Exception as e:
        return _push_error(state, f"[analyzer_node] {e}")


# -------- RAG NODES (MEMORY) --------

def indexer_node(state: RecruitAIState, deps: GraphDeps) -> RecruitAIState:
    try:
        offers = state.get("offers_parsed", [])
        if not offers:
            return _push_error(state, "[indexer_node] No offers_parsed found")

        n = deps.indexer.index_offers(offers)
        state["rag_indexed_count"] = n
        return state
    except Exception as e:
        return _push_error(state, f"[indexer_node] {e}")


def retriever_node(state: RecruitAIState, deps: GraphDeps) -> RecruitAIState:
    try:
        cand = state.get("candidate", None)
        if cand is None:
            return _push_error(state, "[retriever_node] Missing candidate in state")

        k = int(state.get("rag_k", 10))
        res = deps.retriever.retrieve(cand, k=k)

        state["rag_query_result"] = res
        top_ids = (res.get("ids") or [[]])[0]
        state["rag_top_offer_ids"] = top_ids
        return state
    except Exception as e:
        return _push_error(state, f"[retriever_node] {e}")


# -------- MATCHING / WRITING / TRACKING --------

def matcher_node(state: RecruitAIState, deps: GraphDeps) -> RecruitAIState:
    try:
        cand = state.get("candidate", None)
        offers = state.get("offers_parsed", [])
        if cand is None:
            return _push_error(state, "[matcher_node] Missing candidate in state")
        if not offers:
            return _push_error(state, "[matcher_node] No offers_parsed found")

        top_ids = set(state.get("rag_top_offer_ids", []) or [])
        if top_ids:
            offers = [o for o in offers if o.id in top_ids]

        if not offers:
            return _push_error(state, "[matcher_node] Offers list empty after RAG filtering")

        matches = deps.matcher.rank(offers, cand)
        state["matches"] = matches

        if matches and not state.get("selected_job_id"):
            state["selected_job_id"] = matches[0].job_id

        return state
    except Exception as e:
        return _push_error(state, f"[matcher_node] {e}")


def writer_node(state: RecruitAIState, deps: GraphDeps) -> RecruitAIState:
    try:
        cand = state.get("candidate", None)
        offers = state.get("offers_parsed", [])
        matches = state.get("matches", [])
        selected_job_id = state.get("selected_job_id")

        if cand is None:
            return _push_error(state, "[writer_node] Missing candidate in state")
        if not offers or not matches:
            return _push_error(state, "[writer_node] Need offers_parsed and matches before writing")
        if not selected_job_id:
            return _push_error(state, "[writer_node] Missing selected_job_id")

        offer_by_id = {o.id: o for o in offers}
        match_by_job = {m.job_id: m for m in matches}

        offer = offer_by_id.get(selected_job_id)
        match = match_by_job.get(selected_job_id)
        if not offer or not match:
            return _push_error(state, "[writer_node] Selected job not found in offers/matches")

        cv_tex = deps.writer.generate_cv_latex(candidate=cand, offer=offer, match=match)
        letter_tex = deps.writer.generate_letter_latex(candidate=cand, offer=offer, match=match)

        out_dir = "data/processed/generated_docs"
        cv_path, letter_path = deps.writer.save_outputs(out_dir=out_dir, cv_tex=cv_tex, letter_tex=letter_tex)

        state["generated_cv_path"] = cv_path
        state["generated_letter_path"] = letter_path
        return state
    except Exception as e:
        return _push_error(state, f"[writer_node] {e}")


def tracker_node(state: RecruitAIState, deps: GraphDeps) -> RecruitAIState:
    try:
        cand = state.get("candidate", None)
        matches = state.get("matches", [])
        selected_job_id = state.get("selected_job_id")

        if cand is None:
            return _push_error(state, "[tracker_node] Missing candidate in state")
        if not matches:
            return _push_error(state, "[tracker_node] Missing matches")
        if not selected_job_id:
            return _push_error(state, "[tracker_node] Missing selected_job_id")

        match_by_job = {m.job_id: m for m in matches}
        m = match_by_job[selected_job_id]

        row = deps.tracker.add_application(
            job_id=selected_job_id,
            candidate_id=cand.id,
            score=m.score,
            cv_path=state.get("generated_cv_path"),
            letter_path=state.get("generated_letter_path"),
        )
        state["last_application_row"] = row
        return state
    except Exception as e:
        return _push_error(state, f"[tracker_node] {e}")
