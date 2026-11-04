from typing import Literal

from src.llm.port import llm, prompt_version
from src.utils.prompts import load_prompt
from src.graph.state import RecruitAIState
from src.config.logging import logger

# Router Prompt
ROUTER_SYSTEM_PROMPT = load_prompt("router")

def route_request(state: RecruitAIState) -> Literal["job_pipeline", "rag_agent", "general_chat"]:
    messages = state.get("messages", [])
    if not messages:
        return "general_chat"
    
    last_msg = messages[-1]
    query = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

    logger.info(f"[router] Routing message: {query[:50]}...")
    
    try:
        final_prompt = ROUTER_SYSTEM_PROMPT.replace("{query}", query)
        response = llm.complete(final_prompt, role="route", prompt_version=prompt_version(ROUTER_SYSTEM_PROMPT))
        content = response.strip().lower()
        
        # Refined Decision Logic
        if any(w in content for w in ["search", "find", "look for", "offers", "jobs", "pipeline"]):
             decision = "job_pipeline"
        elif any(w in content for w in ["cv", "resume", "profile", "my experience", "my skills", "rag"]):
             decision = "rag_agent"
        else:
             decision = "general_chat"

        # If LLM explicitly said rag_agent, respect that more than general_chat
        if "rag" in content or "profile" in content or "cv" in content:
            decision = "rag_agent"
             
        logger.info(f"[router] Decision: {decision} (raw: {content[:20]})")
        return decision
        
    except Exception as e:
        logger.error(f"[router] Error routing: {e}")
        return "general_chat"
