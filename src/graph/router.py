from typing import Literal

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from src.config.settings import settings
from src.graph.state import RecruitAIState
from src.config.logging import logger

# Initialize LLM
llm = ChatGoogleGenerativeAI(
    model=settings.GEMINI_MODEL,
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0
)

# Router Prompt
ROUTER_SYSTEM_PROMPT = """You are the Orchestrator for RecruitAI.
Your job is to route the user's request to the correct agent.

AVAILABLE AGENTS:
1. "job_pipeline": User specifically wants to LAUNCH a new search or scrape operations. (Keywords: find new jobs, scrape linkedin, look for offers).
2. "rag_agent": User asks about THEIR OWN profile, CV, or saved templates. (Keywords: what's on my cv? do I have python skills?).
3. "stats_agent": User asks for STATISTICS, COUNTS, or QUESTIONS about existing job offers in the database. (Keywords: how many jobs?, what is the average salary?, list python jobs, compare remote vs onsite).
4. "general_chat": Simple greetings, or clarifications.

OUTPUT:
Return ONLY one of these strings: "job_pipeline", "rag_agent", "stats_agent", "general_chat".
"""

def route_request(state: RecruitAIState) -> Literal["job_pipeline", "rag_agent", "stats_agent", "general_chat"]:
    """
    Decides the next node based on the last user message.
    """
    messages = state.get("messages", [])
    if not messages:
        return "general_chat"
    
    last_msg = messages[-1]
    if not isinstance(last_msg, HumanMessage):
         # If the last message wasn't human, likely we just finished a tool? 
         # Default to END or chat. for now, let's assume we want to stop or chat.
         return "general_chat"

    logger.info(f"[router] Routing message: {last_msg.content[:50]}...")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", ROUTER_SYSTEM_PROMPT),
        ("human", "{input}")
    ])
    
    chain = prompt | llm
    
    try:
        response = chain.invoke({"input": last_msg.content})
        decision = response.content.strip().lower()
        
        # Normalize
        if "job" in decision or "pipeline" in decision:
            return "job_pipeline"
        elif "rag" in decision or "cv" in decision:
            return "rag_agent"
        elif "stats" in decision or "count" in decision or "average" in decision or "list" in decision:
            return "stats_agent"
        else:
            return "general_chat"
            
    except Exception as e:
        logger.error(f"[router] Error routing: {e}")
        return "general_chat"
