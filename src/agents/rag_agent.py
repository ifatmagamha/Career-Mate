from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from src.config.settings import settings
from src.config.logging import logger
from src.graph.state import RecruitAIState
from src.storage.vector_store import query_store

# Initialize LLM
llm = ChatGoogleGenerativeAI(
    model=settings.GEMINI_MODEL,
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0.3
)

RAG_SYSTEM_PROMPT = """You are a helpful assistant for a job candidate.
You have access to their personal documents (CV, templates, etc.).

CONTEXT:
{context}

QUESTION:
{question}

INSTRUCTIONS:
- Answer the question based ONLY on the provided context.
- If the answer is not in the context, say "I don't have that information in your documents."
- Be concise and professional.
"""

def rag_node(state: RecruitAIState) -> dict:
    """
    RAG Agent Node:
    1. Retrieve relevant docs based on last user message.
    2. Generate answer.
    """
    messages = state.get("messages", [])
    if not messages:
         return {}
    
    last_msg = messages[-1]
    query = last_msg.content
    
    logger.info(f"[rag_agent] Searching for: {query}")
    
    # 1. Retrieve
    docs = query_store(query, k=3)
    context_text = "\n\n".join([d.page_content for d in docs])
    
    if not context_text:
        context_text = "No relevant documents found."

    # 2. Generate
    prompt = ChatPromptTemplate.from_template(RAG_SYSTEM_PROMPT)
    chain = prompt | llm
    
    response = chain.invoke({"context": context_text, "question": query})
    logger.info(f"[rag_agent] Answer generated.")
    
    return {"messages": [response]}
