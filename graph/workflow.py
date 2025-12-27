# graph/workflow.py

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langgraph.graph import StateGraph, END
import os

from agents.collector import CollectorAgent, GoogleJobsCollector
from agents.analyzer import AnalyzerAgent
from agents.matcher import MatcherAgent
from agents.writer import WriterAgent
from agents.tracker import TrackerAgent


def build_workflow():
    """
    Construit le pipeline complet LangGraph :
    Collector -> Analyzer -> Matcher -> Writer -> Tracker
    """

    # --- Créer le graphe ---
    graph = StateGraph(dict)

    # --- Instanciation des agents ---
    collector_agent = CollectorAgent(
        collectors=[
            GoogleJobsCollector(
                api_key=os.getenv("GOOGLE_API_KEY"),
                cse_id=os.getenv("GOOGLE_CSE_ID")
            )
        ]
    )

    analyzer_agent = AnalyzerAgent()
    matcher_agent = MatcherAgent()
    writer_agent = WriterAgent()
    tracker_agent = TrackerAgent()

    # --- Définition des noeuds ---
    graph.add_node("collector", collector_agent.run)
    graph.add_node("analyzer", analyzer_agent.run)
    graph.add_node("matcher", matcher_agent.run)
    graph.add_node("writer", writer_agent.run)
    graph.add_node("tracker", tracker_agent.run)

    # --- Définition des transitions ---
    graph.set_entry_point("collector")
    graph.add_edge("collector", "analyzer")
    graph.add_edge("analyzer", "matcher")
    graph.add_edge("matcher", "writer")
    graph.add_edge("writer", "tracker")
    graph.add_edge("tracker", END)

    # --- Compilation du graphe pour exécution ---
    return graph.compile()
