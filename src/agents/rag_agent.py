from langchain_core.messages import AIMessage

from src.config.logging import logger
from src.graph.state import RecruitAIState
from src.llm.port import llm, prompt_version
from src.storage.vector_store import query_store
from src.utils.prompts import load_prompt

RAG_SYSTEM_PROMPT = load_prompt("rag")

def rag_node(state: RecruitAIState) -> dict:
    messages = state.get("messages", [])
    if not messages:
         return {}

    last_msg = messages[-1]
    query = last_msg.content

    logger.info(f"[rag_agent] Searching for: {query}")

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
    system = RAG_SYSTEM_PROMPT.replace("{context}", context_text).replace("{question}", query)
    answer = llm.complete(
        [{"role": "system", "content": system}, {"role": "user", "content": query}],
        role="chat", prompt_version=prompt_version(RAG_SYSTEM_PROMPT),
    )
    logger.info(f"[rag_agent] Answer generated.")

    return {
        "messages": [AIMessage(content=answer)],
        "retrieved_chunks": context_parts,
        "active_node": "rag"
    }

