from __future__ import annotations

from langgraph.graph import StateGraph, END

from src.graph.state import RecruitAIState
from src.graph.nodes import node_collect, node_analyze, node_match, node_write, node_track
from src.graph.router import route_request
from src.agents.rag_agent import rag_node
from src.agents.stats_agent import stats_node

# Simple Chat Node for "general_chat"
from langchain_core.messages import AIMessage
def node_chat(state: RecruitAIState):
    # Fallback chat if no specific agent
    return {"messages": [AIMessage(content="I can help you search for jobs or answer questions about your profile. automated chat is not fully implemented yet.")]}

def build_recruit_graph():
    g = StateGraph(RecruitAIState)

    # Core Nodes
    g.add_node("router", lambda state: {}) # Router is just a pass-through to conditional edge
    g.add_node("collect", node_collect)
    g.add_node("analyze", node_analyze)
    g.add_node("match", node_match)
    g.add_node("write", node_write)
    g.add_node("track", node_track)
    
    # New Agents
    g.add_node("rag", rag_node)
    g.add_node("stats", stats_node)
    g.add_node("chat", node_chat)

    # Entry Point
    g.set_entry_point("router")

    # Conditional Edges from Router
    g.add_conditional_edges(
        "router",
        route_request,
        {
            "job_pipeline": "collect",
            "rag_agent": "rag",
            "stats_agent": "stats",
            "general_chat": "chat"
        }
    )

    # Job Pipeline Flow
    g.add_edge("collect", "analyze")
    g.add_edge("analyze", "match")
    g.add_edge("match", "write")
    g.add_edge("write", "track")
    g.add_edge("track", END)
    
    # Agent Flows
    g.add_edge("rag", END)
    g.add_edge("stats", END)
    g.add_edge("chat", END)

    return g.compile()
