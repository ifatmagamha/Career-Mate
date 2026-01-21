from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from schemas.tracking import ApplicationEvent, ApplicationStatus


@dataclass
class TrackerAgent:
    path: str = "data/tracking/applications.json"

    def __post_init__(self):
        p = Path(self.path)
        p.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict[str, Any]]:
        p = Path(self.path)
        if not p.exists():
            return []
        return json.loads(p.read_text(encoding="utf-8"))

    def _save(self, rows: list[dict[str, Any]]) -> None:
        Path(self.path).write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    def add_application(
        self,
        *,
        job_id: str,
        candidate_id: str,
        score: float,
        cv_path: str | None = None,
        letter_path: str | None = None,
    ) -> dict[str, Any]:
        rows = self._load()
        app_id = (max([r.get("application_id", 0) for r in rows]) + 1) if rows else 1

        now = datetime.utcnow().isoformat()
        row = {
            "application_id": app_id,
            "job_id": job_id,
            "candidate_id": candidate_id,
            "score": score,
            "status": ApplicationStatus.APPLIED.value,
            "created_at": now,
            "last_update": now,
            "documents": {"cv": cv_path, "cover_letter": letter_path},
            "history": [{"date": now, "event": "Application created"}],
        }
        rows.append(row)
        self._save(rows)
        return row

    def update_status(self, *, application_id: int, new_status: ApplicationStatus, note: str | None = None) -> dict[str, Any]:
        rows = self._load()
        now = datetime.utcnow().isoformat()

        for r in rows:
            if r.get("application_id") == application_id:
                r["status"] = new_status.value
                r["last_update"] = now
                ev = f"Status changed to {new_status.value}"
                if note:
                    ev += f" | {note}"
                r["history"].append({"date": now, "event": ev})
                self._save(rows)
                return r

        raise ValueError("Application not found")

    def list_applications(self) -> list[dict[str, Any]]:
        return self._load()
