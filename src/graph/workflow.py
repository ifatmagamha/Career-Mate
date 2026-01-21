from __future__ import annotations

from langgraph.graph import StateGraph, END

from graph.state import RecruitAIState
from graph.nodes import (
    build_deps,
    collector_node,
    analyzer_node,
    indexer_node,
    retriever_node,
    matcher_node,
    writer_node,
    tracker_node,
)


def build_graph():
    deps = build_deps()

    g = StateGraph(RecruitAIState)

    # wrap nodes so they receive deps
    g.add_node("collector", lambda s: collector_node(s, deps))
    g.add_node("analyzer", lambda s: analyzer_node(s, deps))

    # RAG nodes
    g.add_node("indexer", lambda s: indexer_node(s, deps))
    g.add_node("retriever", lambda s: retriever_node(s, deps))

    g.add_node("matcher", lambda s: matcher_node(s, deps))
    g.add_node("writer", lambda s: writer_node(s, deps))
    g.add_node("tracker", lambda s: tracker_node(s, deps))

    g.set_entry_point("collector")

    # Pipeline
    g.add_edge("collector", "analyzer")
    g.add_edge("analyzer", "indexer")
    g.add_edge("indexer", "retriever")
    g.add_edge("retriever", "matcher")
    g.add_edge("matcher", "writer")
    g.add_edge("writer", "tracker")
    g.add_edge("tracker", END)

    return g.compile()
