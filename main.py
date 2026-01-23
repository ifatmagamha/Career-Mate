from __future__ import annotations

import sys
from langchain_core.messages import HumanMessage
from src.graph.build_graph import build_recruit_graph
from src.config.logging import logger

def main():
    print("Initializing RecruitAI Agent...")
    graph = build_recruit_graph()
    
    # Initialize chat history
    messages = []
    
    print("\n--- RecruitAI (Router + RAG + Jobs) ---")
    print("Type 'exit' to quit.")
    print("Try: 'search for python jobs in Paris' or 'what is in my CV?'")
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue
            if user_input.lower() in {"exit", "quit"}:
                break
            
            # Prepare state
            messages.append(HumanMessage(content=user_input))
            inputs = {"messages": messages, "query": user_input} # query fallback for legacy nodes
            
            # Run Graph
            print("Thinking...")
            final_state = graph.invoke(inputs)
            
            # Get output
            new_messages = final_state.get("messages", [])
            if new_messages:
                last_msg = new_messages[-1]
                print(f"AI: {last_msg.content}")
                messages = new_messages # Update history
            else:
                # Fallback if job pipeline ran (it doesn't return messages yet in legacy nodes)
                # We check legacy outputs
                if final_state.get("offers_analyzed"):
                    count = len(final_state["offers_analyzed"])
                    print(f"AI: I found and analyzed {count} offers. (Check dashboard)")
                else:
                    print("AI: [Task Completed]")
                    
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
