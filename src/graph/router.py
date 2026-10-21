from typing import Literal

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from src.config.settings import settings
from src.utils.prompts import load_prompt
from src.graph.state import RecruitAIState
from src.config.logging import logger

# Initialize LLM
llm = ChatGoogleGenerativeAI(
    model=settings.GEMINI_MODEL,
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0
)

# Router Prompt
ROUTER_SYSTEM_PROMPT = load_prompt("router")

def route_request(state: RecruitAIState) -> Literal["job_pipeline", "rag_agent", "stats_agent", "general_chat"]:
    import time
    from src.api.agent_traces import log_agent_trace
    start_time = time.time()
    
    messages = state.get("messages", [])
    if not messages:
        return "general_chat"
    
    last_msg = messages[-1]
    query = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

    logger.info(f"[router] Routing message: {query[:50]}...")
    
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("human", ROUTER_SYSTEM_PROMPT)
        ])
        
        # Format
        final_prompt = prompt.format(query=query)
        
        # Direct generation
        response = llm.invoke(final_prompt)
        content = response.text.strip().lower()
        
        # Refined Decision Logic
        if any(w in content for w in ["search", "find", "look for", "offers", "jobs", "pipeline"]):
             decision = "job_pipeline"
        elif any(w in content for w in ["cv", "resume", "profile", "my experience", "my skills", "rag"]):
             decision = "rag_agent"
        elif any(w in content for w in ["how many", "count", "average", "stats", "salary", "market", "distribution", "distribution", "percentage"]):
             decision = "stats_agent"
        else:
             decision = "general_chat"
             
        # Priority override based on ORIGINAL query
        if any(w in query.lower() for w in ["how many", "count", "average", "median", "percentage", "distribution"]):
            decision = "stats_agent"
        
        # If LLM explicitly said rag_agent, respect that more than general_chat
        if "rag" in content or "profile" in content or "cv" in content:
            decision = "rag_agent"
             
        duration = (time.time() - start_time) * 1000
        log_agent_trace("Router", query, f"Routed to {decision}", duration)
        
        logger.info(f"[router] Decision: {decision} (raw: {content[:20]})")
        return decision
        
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        log_agent_trace("Router", query, str(e), duration, status="error")
        logger.error(f"[router] Error routing: {e}")
        return "general_chat"
