# src/graph/build_graph.py
from __future__ import annotations

from langgraph.graph import StateGraph, END

from src.graph.state import RecruitAIState
from src.graph.nodes import node_collect, node_analyze, node_match, node_write, node_track


def build_recruit_graph():
    g = StateGraph(RecruitAIState)

    g.add_node("collect", node_collect)
    g.add_node("analyze", node_analyze)
    g.add_node("match", node_match)
    g.add_node("write", node_write)
    g.add_node("track", node_track)

    g.set_entry_point("collect")
    g.add_edge("collect", "analyze")
    g.add_edge("analyze", "match")
    g.add_edge("match", "write")
    g.add_edge("write", "track")
    g.add_edge("track", END)

    return g.compile()
