from __future__ import annotations
from langgraph.graph import StateGraph, END
from langchain_core.messages import AIMessage, HumanMessage

from src.graph.state import RecruitAIState
from src.graph.nodes import node_collect, node_analyze, node_match, node_write, node_track, node_report_matches
from src.graph.router import route_request
from src.agents.rag_agent import rag_node

def node_chat(state: RecruitAIState):
    """Conversational fallback using the LLM."""
    from src.llm.port import llm

    messages = state.get("messages", [])
    if not messages:
        return {"messages": [AIMessage(content="Hello! How can I help you today?")]}
    
    last_query = messages[-1].content
    
    prompt = f"""
    You are RecruitAI, a helpful assistant for job seekers.
    The user said: "{last_query}"
    
    Provide a helpful, friendly, and concise response. 
    Mention that you can help them:
    1. Search and match job offers.
    2. Answer questions about their CV (RAG).
    3. Provide market statistics on job offers.
    
    Keep it brief.
    """
    
    res = llm.complete(prompt, role="chat", temperature=0.4)
    return {"messages": [AIMessage(content=res)], "active_node": "chat"}

def build_recruit_graph():
    g = StateGraph(RecruitAIState)

    # Core Nodes
    g.add_node("router", lambda state: {}) # Router is just a pass-through to conditional edge
    g.add_node("collect", node_collect)
    g.add_node("analyze", node_analyze)
    g.add_node("match", node_match)
    g.add_node("write", node_write)
    g.add_node("track", node_track)
    g.add_node("report_matches", node_report_matches)
    
    # New Agents
    g.add_node("rag", rag_node)
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
            "general_chat": "chat"
        }
    )

    # Job Pipeline Flow (Search & Match)
    g.add_edge("collect", "analyze")
    g.add_edge("analyze", "match")
    g.add_edge("match", "report_matches")
    g.add_edge("report_matches", END) # Stop after reporting for Explorer
    
    # Application Generation Flow (Optional/Separate)
    # g.add_edge("write", "track")
    # g.add_edge("track", END)
    
    # Agent Flows
    g.add_edge("rag", END)
    g.add_edge("chat", END)

    return g.compile()
