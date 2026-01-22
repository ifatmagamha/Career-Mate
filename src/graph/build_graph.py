# src/graph/build_graph.py
from __future__ import annotations

from langgraph.graph import StateGraph, END

from src.graph.state import RecruitAIState
from src.graph.nodes import (
    collector_node,
    analyzer_node,
    matcher_node,
    writer_node,
    tracker_node,
)


def build_recruit_graph():
    g = StateGraph(RecruitAIState)

    g.add_node("collector", collector_node)
    g.add_node("analyzer", analyzer_node)
    g.add_node("matcher", matcher_node)
    g.add_node("writer", writer_node)
    g.add_node("tracker", tracker_node)

    # MVP linear flow
    g.set_entry_point("collector")
    g.add_edge("collector", "analyzer")
    g.add_edge("analyzer", "matcher")
    g.add_edge("matcher", "writer")
    g.add_edge("writer", "tracker")
    g.add_edge("tracker", END)

    return g.compile()
