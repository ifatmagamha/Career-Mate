# src/agents/tracker.py
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from src.schemas.job_offer import MatchResult


def track_matches(matches: List[MatchResult], tracking_path: str) -> None:
    """
    Append new matches into tracking.json with status='saved' if not already present.
    """
    p = Path(tracking_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            data = []
    else:
        data = []

    existing_urls = {x.get("url") for x in data if isinstance(x, dict)}

    now = datetime.utcnow().isoformat() + "Z"
    for m in matches:
        u = str(m.url)
        if u in existing_urls:
            continue
        data.append(
            {
                "url": u,
                "title": m.title,
                "company": m.company,
                "location": m.location,
                "score": m.score,
                "status": "saved",  # saved/applied/interview/rejected
                "created_at": now,
                "updated_at": now,
            }
        )

    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
