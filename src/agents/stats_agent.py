import json
import os
import pandas as pd
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage

from src.config.settings import settings
from src.config.logging import logger
from src.graph.state import RecruitAIState

# Initialize LLM
llm = ChatGoogleGenerativeAI(
    model=settings.GEMINI_MODEL,
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0
)

def load_jobs_dataframe() -> pd.DataFrame:
    """Loads the analyzed jobs JSON into a Pandas DataFrame."""
    path = os.path.join(settings.DATA_DIR, "job_offers_analyzed.json")
    if not os.path.exists(path):
        logger.warning(f"[stats_agent] File not found: {path}")
        return pd.DataFrame()
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        df = pd.DataFrame(data)
        logger.info(f"[stats_agent] Loaded DataFrame with {len(df)} rows.")
        return df
    except Exception as e:
        logger.error(f"[stats_agent] Error loading DataFrame: {e}")
        return pd.DataFrame()

def stats_node(state: RecruitAIState) -> dict:
    """
    Pandas/Stats Agent Node:
    1. Loads job data into DataFrame.
    2. Uses LangChain experimental Pandas Agent to answer structured queries.
    """
    import time
    from src.api.agent_traces import log_agent_trace
    start_time = time.time()
    
    messages = state.get("messages", [])
    if not messages:
        return {}
    
    last_msg = messages[-1]
    query = last_msg.content
    
    logger.info(f"[stats_agent] Processing query: {query}")
    
    try:
        df = load_jobs_dataframe()
        if df.empty:
            duration = (time.time() - start_time) * 1000
            log_agent_trace("Stats", query, "No data available", duration)
            return {"messages": [AIMessage(content="I have no job data available to analyze right now.")]}

        # Create the agent
        agent = create_pandas_dataframe_agent(
            llm,
            df,
            verbose=True,
            allow_dangerous_code=True,
            agent_type="tool-calling",
            max_iterations=5,
        )
        
        response = agent.invoke({"input": query})
        output_text = response["output"]
        
        duration = (time.time() - start_time) * 1000
        log_agent_trace("Stats", query, output_text, duration)
        
        logger.info(f"[stats_agent] Result: {output_text}")
        return {"messages": [AIMessage(content=output_text)]}
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        log_agent_trace("Stats", query, str(e), duration, status="error")
        logger.error(f"[stats_agent] Error interacting with DataFrame: {e}")
        return {"messages": [AIMessage(content="I encountered an error trying to analyze the data.")]}
