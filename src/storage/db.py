# src/storage/db.py
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config.settings import settings

DB_PATH = Path(settings.DATA_DIR) / "career_mate.db"

# One status list for code, API and UI (spec v0.1, D2)
STATUSES = ("saved", "to_apply", "applied", "interview", "offer", "accepted", "rejected", "archived")
ACTORS = ("user", "ai", "automation")

# List fields are stored as JSON text.
_JSON_FIELDS = ("skills", "nice_to_have", "missions", "requirements")

_OFFER_FIELDS = (
    "url", "title", "company", "location", "remote_policy", "contract_type", "seniority",
    "salary", "deadline", "summary", "raw_text", "source", "model", "prompt_version", "match_score",
)

SCHEMA = """
-- What the employer published (re-extractable, never edited by tracking)
CREATE TABLE IF NOT EXISTS offers (
    id             TEXT PRIMARY KEY,
    url            TEXT UNIQUE,
    title          TEXT NOT NULL,
    company        TEXT,
    location       TEXT,
    remote_policy  TEXT,
    contract_type  TEXT,
    seniority      TEXT,
    salary         TEXT,
    deadline       TEXT,
    skills         TEXT DEFAULT '[]',
    nice_to_have   TEXT DEFAULT '[]',
    missions       TEXT DEFAULT '[]',
    requirements   TEXT DEFAULT '[]',
    summary        TEXT,
    raw_text       TEXT,
    source         TEXT,
    model          TEXT,
    prompt_version TEXT,
    match_score    INTEGER,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
-- What I do with it (1:1 with offers)
CREATE TABLE IF NOT EXISTS applications (
    id             TEXT PRIMARY KEY,
    offer_id       TEXT NOT NULL UNIQUE REFERENCES offers(id),
    status         TEXT NOT NULL DEFAULT 'saved',
    next_action    TEXT,
    next_action_at TEXT,
    applied_at     TEXT,
    channel        TEXT,
    contact        TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_id       TEXT REFERENCES offers(id),
    application_id TEXT REFERENCES applications(id),
    actor          TEXT NOT NULL,
    type           TEXT NOT NULL,
    payload        TEXT DEFAULT '{}',
    created_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS llm_calls (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at     TEXT NOT NULL,
    role           TEXT NOT NULL,
    provider       TEXT NOT NULL,
    model          TEXT NOT NULL,
    prompt_version TEXT,
    offer_id       TEXT,
    status         TEXT NOT NULL,
    http_status    INTEGER,
    input_tokens   INTEGER,
    output_tokens  INTEGER,
    latency_ms     INTEGER,
    cost_usd       REAL,
    error          TEXT,
    request        TEXT,
    response       TEXT
);
"""

_VIEW = """
SELECT o.*, a.id AS application_id, a.status, a.next_action, a.next_action_at, a.applied_at
FROM offers o JOIN applications a ON a.offer_id = o.id
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def _row_to_offer(row: sqlite3.Row) -> Dict[str, Any]:
    offer = dict(row)
    for f in _JSON_FIELDS:
        offer[f] = json.loads(offer[f] or "[]")
    return offer


def log_event(conn: sqlite3.Connection, type_: str, *, actor: str, offer_id: Optional[str] = None,
              application_id: Optional[str] = None, payload: Dict[str, Any] | None = None) -> None:
    if actor not in ACTORS:
        raise ValueError(f"Unknown actor: {actor}")
    conn.execute(
        "INSERT INTO events (offer_id, application_id, actor, type, payload, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (offer_id, application_id, actor, type_, json.dumps(payload or {}, ensure_ascii=False), _now()),
    )


def insert_offer(conn: sqlite3.Connection, data: Dict[str, Any], *, status: str = "saved", actor: str = "user") -> Dict[str, Any]:
    """Create the offer and its application in one transaction."""
    if status not in STATUSES:
        raise ValueError(f"Unknown status: {status}")
    now = _now()
    row = {k: data.get(k) for k in _OFFER_FIELDS}
    row.update({f: json.dumps(data.get(f) or [], ensure_ascii=False) for f in _JSON_FIELDS})
    row.update(id=data.get("id") or str(uuid.uuid4()), created_at=now, updated_at=now)
    app_id = str(uuid.uuid4())

    with conn:
        conn.execute(f"INSERT INTO offers ({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})", list(row.values()))
        conn.execute(
            "INSERT INTO applications (id, offer_id, status, applied_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (app_id, row["id"], status, now if status == "applied" else None, now, now),
        )
        log_event(conn, "offer.created", actor=actor, offer_id=row["id"], application_id=app_id,
                  payload={"source": row["source"], "status": status})
    return get_offer(conn, row["id"])


def get_offer(conn: sqlite3.Connection, offer_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(_VIEW + " WHERE o.id = ?", (offer_id,)).fetchone()
    return _row_to_offer(row) if row else None


def get_offer_by_application(conn: sqlite3.Connection, application_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(_VIEW + " WHERE a.id = ?", (application_id,)).fetchone()
    return _row_to_offer(row) if row else None


def find_offer_by_url(conn: sqlite3.Connection, url: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(_VIEW + " WHERE o.url = ?", (url,)).fetchone()
    return _row_to_offer(row) if row else None


def list_offers(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    return [_row_to_offer(r) for r in conn.execute(_VIEW + " ORDER BY o.created_at DESC").fetchall()]


def update_status(conn: sqlite3.Connection, application_id: str, status: str, *, actor: str = "user") -> Optional[Dict[str, Any]]:
    if status not in STATUSES:
        raise ValueError(f"Unknown status: {status}")
    offer = get_offer_by_application(conn, application_id)
    if not offer:
        return None
    if offer["status"] != status:
        now = _now()
        with conn:
            conn.execute(
                "UPDATE applications SET status = ?, updated_at = ?, applied_at = COALESCE(applied_at, ?) WHERE id = ?",
                (status, now, now if status == "applied" else None, application_id),
            )
            log_event(conn, "application.status_changed", actor=actor, offer_id=offer["id"],
                      application_id=application_id, payload={"from": offer["status"], "to": status})
    return get_offer_by_application(conn, application_id)


def log_llm_call(conn: sqlite3.Connection, call: Dict[str, Any]) -> None:
    call = {**call, "created_at": _now()}
    with conn:
        conn.execute(f"INSERT INTO llm_calls ({', '.join(call)}) VALUES ({', '.join('?' for _ in call)})", list(call.values()))


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        c = connect(Path(d) / "t.db")
        o = insert_offer(c, {"url": "https://x/1", "title": "Data Eng", "skills": ["SQL"], "source": "test"}, actor="ai")
        assert o["skills"] == ["SQL"] and o["status"] == "saved" and o["application_id"], o
        assert find_offer_by_url(c, "https://x/1")["id"] == o["id"]

        a = update_status(c, o["application_id"], "applied")
        assert a["status"] == "applied" and a["applied_at"], a
        update_status(c, o["application_id"], "applied")  # no-op: same status, no event
        update_status(c, o["application_id"], "interview")
        assert get_offer(c, o["id"])["applied_at"] == a["applied_at"]  # first applied date kept

        for bad in (lambda: update_status(c, o["application_id"], "interviewing"),
                    lambda: insert_offer(c, {"title": "x"}, status="nope"),
                    lambda: log_event(c, "x", actor="robot")):
            try:
                bad()
                raise AssertionError("expected ValueError")
            except ValueError:
                pass

        rows = [(r["type"], r["actor"]) for r in c.execute("SELECT type, actor FROM events ORDER BY id")]
        assert rows == [("offer.created", "ai"), ("application.status_changed", "user"),
                        ("application.status_changed", "user")], rows

        log_llm_call(c, {"role": "extract", "provider": "p", "model": "m", "status": "ok", "input_tokens": 3})
        assert c.execute("SELECT input_tokens FROM llm_calls").fetchone()[0] == 3
        c.close()
    print("db ok")
