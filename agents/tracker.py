# agents/tracker.py

import json
import os
from datetime import datetime
from typing import Dict, Any, List


TRACKING_PATH = "data/tracking/applications.json"


def _load_applications() -> List[Dict[str, Any]]:
    if not os.path.exists(TRACKING_PATH):
        return []
    with open(TRACKING_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_applications(apps: List[Dict[str, Any]]):
    os.makedirs(os.path.dirname(TRACKING_PATH), exist_ok=True)
    with open(TRACKING_PATH, "w", encoding="utf-8") as f:
        json.dump(apps, f, indent=2, ensure_ascii=False)


class TrackerAgent:
    """
    LangGraph terminal node
    Responsible for persistence & tracking
    """

    def run(self, state: dict) -> dict:
        """
        Expected state:
        {
            "final_output": {
                "target_offer": dict,
                "cv_latex": str,
                "cover_letter_latex": str
            }
        }
        """

        final_output = state.get("final_output")
        if not final_output:
            raise ValueError("final_output manquant dans le state")

        offer = final_output["target_offer"]

        applications = _load_applications()

        application = {
            "application_id": len(applications) + 1,
            "offer_title": offer.get("offer_title"),
            "company": offer.get("company"),
            "matching_score": offer.get("matching_score"),
            "source_url": offer.get("source_url"),
            "status": "Generated",
            "created_at": datetime.now().isoformat(),
            "last_update": datetime.now().isoformat(),
            "history": [
                {
                    "date": datetime.now().isoformat(),
                    "event": "Documents generated",
                }
            ],
        }

        applications.append(application)
        _save_applications(applications)

        state["tracking"] = application
        return state
