from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from src.config.settings import settings
from src.config.logging import logger
from src.graph.state import RecruitAIState
from src.storage.vector_store import query_store
from src.utils.prompts import load_prompt

# Initialize LLM
llm = ChatGoogleGenerativeAI(
    model=settings.GEMINI_MODEL,
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0.3
)

RAG_SYSTEM_PROMPT = load_prompt("rag")

def rag_node(state: RecruitAIState) -> dict:
    import time
    from src.api.agent_traces import log_agent_trace
    start_time = time.time()
    
    messages = state.get("messages", [])
    if not messages:
         return {}
    
    last_msg = messages[-1]
    query = last_msg.content
    
    logger.info(f"[rag_agent] Searching for: {query}")
    
    try:
        # 1. Retrieve from Vector Store
        docs = query_store(query, k=3)
        context_parts = [d.page_content for d in docs]
        
        # 2. Add Candidate Profile info if available in state
        candidate = state.get("candidate")
        if candidate:
            candidate_info = f"CURRENT PROFILE DATA:\nName: {candidate.full_name}\nEmail: {candidate.email}\nSkills: {', '.join(candidate.skills)}\nSummary: {candidate.summary}"
            context_parts.append(candidate_info)
            
        context_text = "\n\n".join(context_parts)
        
        if not context_text:
            context_text = "No relevant documents or profile data found."

        # 2. Generate
        prompt = ChatPromptTemplate.from_messages([
            ("system", RAG_SYSTEM_PROMPT),
            ("human", "{question}")
        ])
        chain = prompt | llm
        
        response = chain.invoke({"context": context_text, "question": query})
        logger.info(f"[rag_agent] Answer generated.")
        
        duration = (time.time() - start_time) * 1000
        log_agent_trace("RAG", query, response.text, duration)
        
        return {
            "messages": [response],
            "retrieved_chunks": context_parts,
            "active_node": "rag"
        }
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        log_agent_trace("RAG", query, str(e), duration, status="error")
        raise e
