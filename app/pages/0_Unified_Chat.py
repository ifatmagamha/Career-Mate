import streamlit as st
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from langchain_core.messages import HumanMessage, AIMessage
from src.graph.build_graph import build_recruit_graph
from src.ui.nav import nav
import json

# Page Config
st.set_page_config(page_title="RecruitAI - Chat", page_icon="🤖", layout="wide")

# Navigation
nav()

st.title("🤖 RecruitAI Assistant")
st.caption("Ask about jobs, your CV, or market stats.")

# Initialize Graph
if "graph" not in st.session_state:
    st.session_state["graph"] = build_recruit_graph()

# Initialize Chat History
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Display History
for msg in st.session_state["messages"]:
    if isinstance(msg, HumanMessage):
        with st.chat_message("user"):
            st.markdown(msg.content)
    elif isinstance(msg, AIMessage):
        with st.chat_message("assistant"):
            st.markdown(msg.content)

# Input
user_input = st.chat_input("Ex: 'Find Python jobs in Paris' or 'How many remote offers do we have?'")

# Quick Actions (Pills-like interface)
if not user_input:
    cols = st.columns(4)
    with cols[0]:
        if st.button("🔍 Find Python Jobs", use_container_width=True):
            user_input = "Find Python developer jobs in Paris"
    with cols[1]:
        if st.button("📊 Job Stats", use_container_width=True):
            user_input = "How many job offers are in the database?"
    with cols[2]:
        if st.button("📝 Check my CV", use_container_width=True):
            user_input = "Does my CV mention Python knowledge?"
    with cols[3]:
        if st.button("📧 Write Cover Letter", use_container_width=True):
            user_input = "Write a cover letter for a Python Engineer role"

if user_input:
    # 1. Display User Message
    st.session_state["messages"].append(HumanMessage(content=user_input))
    with st.chat_message("user"):
        st.markdown(user_input)

    # 2. Run Graph
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        with st.spinner("Thinking..."):
            try:
                # Prepare inputs
                inputs = {
                    "messages": st.session_state["messages"],
                    "query": user_input # Fallback for some nodes
                }
                
                # Invoke
                config = {"recursion_limit": 10}
                final_state = st.session_state["graph"].invoke(inputs, config=config)
                
                # Get Response
                new_msgs = final_state.get("messages", [])
                if new_msgs:
                    # We might get multiple messages back, usually the last one is the final answer
                    # But the graph returns ALL messages in history usually, so we need to find the new ones.
                    # LangGraph default 'add_messages' appends. 
                    
                    # Simple hack: take the last message if it's AI
                    last_msg = new_msgs[-1]
                    response_text = last_msg.content
                    
                    message_placeholder.markdown(response_text)
                    st.session_state["messages"] = new_msgs
                else:
                    response_text = "I completed the task but have no text response."
                    message_placeholder.markdown(response_text)
                
                # 3. Check for specific side-effects (e.g., Job Cards)
                if final_state.get("offers_analyzed"):
                     from src.ui.components import render_job_card
                     with st.expander(f"🔎 View Analyzed Jobs ({len(final_state['offers_analyzed'])})", expanded=True):
                        # Display as cards
                        for offer in final_state["offers_analyzed"]:
                            # Offer is likely a Pydantic model or dict, normalize to dict
                            offer_dict = offer.model_dump() if hasattr(offer, "model_dump") else offer
                            render_job_card(offer_dict)
                        
            except Exception as e:
                st.error(f"An error occurred: {e}")
