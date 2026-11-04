from __future__ import annotations

import json
import re
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
LAYOUTS = ("grid", "table", "board")

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
    folder_id      TEXT REFERENCES folders(id),
    notes          TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

-- My own directories (an offer sits in at most one; none = unfiled)
CREATE TABLE IF NOT EXISTS folders (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TEXT NOT NULL
);

-- People to reach for an application (third-party personal data: stays in this local file)
CREATE TABLE IF NOT EXISTS contacts (
    id             TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    role           TEXT,
    linkedin_url   TEXT,
    notes          TEXT,
    reached_out    INTEGER NOT NULL DEFAULT 0,
    reached_at     TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

-- Saved views: a named filter + sort + layout
CREATE TABLE IF NOT EXISTS views (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE COLLATE NOCASE,
    filters    TEXT NOT NULL DEFAULT '{}',
    layout     TEXT NOT NULL DEFAULT 'grid',
    created_at TEXT NOT NULL
);

-- Full-text index over offers (BM25 ranking), kept in sync by triggers
CREATE VIRTUAL TABLE IF NOT EXISTS offers_fts USING fts5(
    title, company, location, summary, skills, nice_to_have, raw_text,
    content='offers', content_rowid='rowid', tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS offers_fts_ai AFTER INSERT ON offers BEGIN
    INSERT INTO offers_fts(rowid, title, company, location, summary, skills, nice_to_have, raw_text)
    VALUES (new.rowid, new.title, new.company, new.location, new.summary, new.skills, new.nice_to_have, new.raw_text);
END;

CREATE TRIGGER IF NOT EXISTS offers_fts_ad AFTER DELETE ON offers BEGIN
    INSERT INTO offers_fts(offers_fts, rowid, title, company, location, summary, skills, nice_to_have, raw_text)
    VALUES ('delete', old.rowid, old.title, old.company, old.location, old.summary, old.skills, old.nice_to_have, old.raw_text);
END;

CREATE TRIGGER IF NOT EXISTS offers_fts_au AFTER UPDATE ON offers BEGIN
    INSERT INTO offers_fts(offers_fts, rowid, title, company, location, summary, skills, nice_to_have, raw_text)
    VALUES ('delete', old.rowid, old.title, old.company, old.location, old.summary, old.skills, old.nice_to_have, old.raw_text);
    INSERT INTO offers_fts(rowid, title, company, location, summary, skills, nice_to_have, raw_text)
    VALUES (new.rowid, new.title, new.company, new.location, new.summary, new.skills, new.nice_to_have, new.raw_text);
END;

-- Dense vectors for semantic search (derived data: rebuilt when the text or the embedding model changes)
CREATE TABLE IF NOT EXISTS offer_embeddings (
    offer_id   TEXT PRIMARY KEY REFERENCES offers(id) ON DELETE CASCADE,
    model      TEXT NOT NULL,
    text_hash  TEXT NOT NULL,
    dim        INTEGER NOT NULL,
    vector     BLOB NOT NULL,
    updated_at TEXT NOT NULL
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
SELECT o.*, a.id AS application_id, a.status, a.next_action, a.next_action_at, a.applied_at,
       a.folder_id, a.notes,
       (SELECT COUNT(*) FROM contacts c WHERE c.application_id = a.id) AS contacts_count
FROM offers o JOIN applications a ON a.offer_id = o.id
"""

_CONTACT_FIELDS = ("name", "role", "linkedin_url", "notes")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    # Databases created before folders/notes existed: add the columns in place
    for column, decl in (("folder_id", "TEXT REFERENCES folders(id)"), ("notes", "TEXT")):
        if column not in {r["name"] for r in conn.execute("PRAGMA table_info(applications)")}:
            conn.execute(f"ALTER TABLE applications ADD COLUMN {column} {decl}")
    # Schema v2: the full-text index appeared; index offers that existed before it
    if conn.execute("PRAGMA user_version").fetchone()[0] < 2:
        with conn:
            conn.execute("INSERT INTO offers_fts(offers_fts) VALUES ('rebuild')")
            conn.execute("PRAGMA user_version = 2")
    return conn


# Common spellings -> one canonical name, so filters and counts group the same skill together.
# ponytail: small hand-made alias list; grow it from the facet list when duplicates show up.
SKILL_ALIASES = {
    "postgres": "PostgreSQL", "postgresql": "PostgreSQL", "js": "JavaScript", "javascript": "JavaScript",
    "ts": "TypeScript", "typescript": "TypeScript", "python": "Python", "py": "Python", "sql": "SQL",
    "k8s": "Kubernetes", "kubernetes": "Kubernetes", "gcp": "Google Cloud", "google cloud platform": "Google Cloud",
    "aws": "AWS", "amazon web services": "AWS", "ml": "Machine Learning", "machine learning": "Machine Learning",
    "power bi": "Power BI", "powerbi": "Power BI", "airflow": "Apache Airflow", "apache airflow": "Apache Airflow",
    "spark": "Apache Spark", "apache spark": "Apache Spark", "kafka": "Apache Kafka", "apache kafka": "Apache Kafka",
    "dbt": "dbt", "excel": "Excel", "microsoft excel": "Excel", "git": "Git", "docker": "Docker",
}


def normalize_skills(skills: Any) -> List[str]:
    """Trim, map known aliases, drop case-insensitive duplicates, keep order."""
    out: List[str] = []
    seen = set()
    for s in skills or []:
        s = " ".join(str(s).split())
        if not s:
            continue
        s = SKILL_ALIASES.get(s.casefold(), s)
        if s.casefold() not in seen:
            seen.add(s.casefold())
            out.append(s)
    return out


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
    data = {**data, "skills": normalize_skills(data.get("skills")), "nice_to_have": normalize_skills(data.get("nice_to_have"))}
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


# Fields you can correct on an offer card (provenance fields like model/source stay as captured)
EDITABLE_OFFER_FIELDS = ("url", "title", "company", "location", "remote_policy", "contract_type", "seniority",
                         "salary", "deadline", "summary", "raw_text") + _JSON_FIELDS


def update_offer(conn: sqlite3.Connection, offer_id: str, changes: Dict[str, Any], *, actor: str = "user") -> Optional[Dict[str, Any]]:
    """Apply edits to the posting fields; the event records which fields changed (your edits win over AI values)."""
    offer = get_offer(conn, offer_id)
    if not offer:
        return None
    changes = {k: v for k, v in changes.items() if k in EDITABLE_OFFER_FIELDS}
    for f in ("skills", "nice_to_have"):
        if f in changes:
            changes[f] = normalize_skills(changes[f])
    changed = [k for k, v in changes.items() if offer.get(k) != v]
    if not changed:
        return offer
    values = {k: json.dumps(changes[k] or [], ensure_ascii=False) if k in _JSON_FIELDS else changes[k] for k in changed}
    values["updated_at"] = _now()
    with conn:
        conn.execute(f"UPDATE offers SET {', '.join(f'{k} = ?' for k in values)} WHERE id = ?", [*values.values(), offer_id])
        log_event(conn, "offer.edited", actor=actor, offer_id=offer_id, application_id=offer["application_id"],
                  payload={"fields": changed})
    return get_offer(conn, offer_id)


def _enum_values(name: str) -> tuple:
    from typing import get_args
    from src.schemas import job_offer
    return tuple(v for v in get_args(getattr(job_offer, name)) if v != "unknown")


# Filterable fields with a fixed list of values: one entry = SQL filter, API value list and the
# natural-language interpreter's schema all at once. Add a field here to make it filterable everywhere.
ENUM_FILTERS = {
    "status": ("a.status", STATUSES),
    "contract_type": ("o.contract_type", _enum_values("SheetContract")),
    "remote_policy": ("o.remote_policy", _enum_values("SheetRemote")),
}

SORTS = {
    "recent": "o.created_at DESC",
    "deadline": "o.deadline IS NULL, o.deadline ASC",
    "title": "o.title COLLATE NOCASE",
    "company": "o.company IS NULL, o.company COLLATE NOCASE",
    "updated": "MAX(o.updated_at, a.updated_at) DESC",
    "relevance": "bm25(offers_fts)",  # only with a search query
}


def _fts_query(q: str) -> str:
    """User text -> safe FTS5 query: every word must match, as a prefix ('pyth' finds 'python')."""
    words = re.findall(r"\w+", q, flags=re.UNICODE)
    return " ".join(f'"{w}"*' for w in words)


def query_offers(conn: sqlite3.Connection, f: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    """Search + filters + sort over offers. Lists are OR within a filter, AND across filters."""
    f = f or {}
    joins, where, params = "", [], []
    fts = _fts_query(f.get("q") or "")
    if fts:
        joins = "JOIN offers_fts ON offers_fts.rowid = o.rowid"
        where.append("offers_fts MATCH ?")
        params.append(fts)
    for key, (column, _) in ENUM_FILTERS.items():
        values = [v for v in (f.get(key) or []) if v]
        if values:
            where.append(f"{column} IN ({', '.join('?' for _ in values)})")
            params += values
    folder = f.get("folder")
    if folder == "unfiled":
        where.append("a.folder_id IS NULL")
    elif folder:
        where.append("a.folder_id = ?")
        params.append(folder)
    if f.get("deadline_before"):
        where.append("o.deadline IS NOT NULL AND o.deadline <= ?")
        params.append(f["deadline_before"])
    sort = f.get("sort") or ("relevance" if fts else "recent")
    if sort not in SORTS or (sort == "relevance" and not fts):
        sort = "recent"
    sql = _VIEW.replace("FROM offers o JOIN", f"FROM offers o {joins} JOIN") \
        + (" WHERE " + " AND ".join(where) if where else "") + f" ORDER BY {SORTS[sort]}"
    return [_row_to_offer(r) for r in conn.execute(sql, params).fetchall()]


def offer_facets(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Totals for the sidebar and the skills present in your offers (for the skill filter)."""
    total, unfiled = conn.execute(
        "SELECT COUNT(*), SUM(folder_id IS NULL) FROM applications").fetchone()
    skills = conn.execute(
        "SELECT value AS name, COUNT(*) AS count FROM offers o, json_each(o.skills) "
        "GROUP BY value COLLATE NOCASE ORDER BY count DESC, name COLLATE NOCASE").fetchall()
    return {"total": total, "unfiled": unfiled or 0, "skills": [dict(s) for s in skills]}


def list_views(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute("SELECT * FROM views ORDER BY name COLLATE NOCASE").fetchall()
    return [{**dict(r), "filters": json.loads(r["filters"])} for r in rows]


def save_view(conn: sqlite3.Connection, name: str, filters: Dict[str, Any], layout: str, view_id: Optional[str] = None) -> Dict[str, Any]:
    """Create (no id) or update a view. Raises sqlite3.IntegrityError on a duplicate name."""
    if not name.strip():
        raise ValueError("View name is empty")
    if layout not in LAYOUTS:
        raise ValueError(f"Unknown layout: {layout}")
    row = {"id": view_id or str(uuid.uuid4()), "name": name.strip(), "filters": json.dumps(filters, ensure_ascii=False),
           "layout": layout, "created_at": _now()}
    with conn:
        if view_id:
            cur = conn.execute("UPDATE views SET name = ?, filters = ?, layout = ? WHERE id = ?",
                               (row["name"], row["filters"], layout, view_id))
            if not cur.rowcount:
                raise KeyError(view_id)
        else:
            conn.execute("INSERT INTO views (id, name, filters, layout, created_at) VALUES (?, ?, ?, ?, ?)", tuple(row.values()))
    r = conn.execute("SELECT * FROM views WHERE id = ?", (row["id"],)).fetchone()
    return {**dict(r), "filters": json.loads(r["filters"])}


def delete_view(conn: sqlite3.Connection, view_id: str) -> bool:
    with conn:
        return conn.execute("DELETE FROM views WHERE id = ?", (view_id,)).rowcount > 0


def set_folder(conn: sqlite3.Connection, application_id: str, folder_id: Optional[str], *, actor: str = "user") -> Optional[Dict[str, Any]]:
    """Move an application into a folder (None = unfiled)."""
    offer = get_offer_by_application(conn, application_id)
    if not offer:
        return None
    if folder_id and not conn.execute("SELECT 1 FROM folders WHERE id = ?", (folder_id,)).fetchone():
        raise ValueError(f"Unknown folder: {folder_id}")
    if offer["folder_id"] != folder_id:
        with conn:
            conn.execute("UPDATE applications SET folder_id = ?, updated_at = ? WHERE id = ?", (folder_id, _now(), application_id))
            log_event(conn, "application.moved", actor=actor, offer_id=offer["id"], application_id=application_id,
                      payload={"from": offer["folder_id"], "to": folder_id})
    return get_offer_by_application(conn, application_id)


def set_notes(conn: sqlite3.Connection, application_id: str, notes: str) -> Optional[Dict[str, Any]]:
    with conn:
        cur = conn.execute("UPDATE applications SET notes = ?, updated_at = ? WHERE id = ?", (notes, _now(), application_id))
    return get_offer_by_application(conn, application_id) if cur.rowcount else None


def list_folders(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT f.id, f.name, f.created_at, COUNT(a.id) AS count FROM folders f "
        "LEFT JOIN applications a ON a.folder_id = f.id GROUP BY f.id ORDER BY f.name COLLATE NOCASE"
    ).fetchall()
    return [dict(r) for r in rows]


def create_folder(conn: sqlite3.Connection, name: str) -> Dict[str, Any]:
    """Raises sqlite3.IntegrityError if the name exists (case-insensitive)."""
    folder = {"id": str(uuid.uuid4()), "name": name.strip(), "created_at": _now()}
    if not folder["name"]:
        raise ValueError("Folder name is empty")
    with conn:
        conn.execute("INSERT INTO folders (id, name, created_at) VALUES (?, ?, ?)", tuple(folder.values()))
    return {**folder, "count": 0}


def rename_folder(conn: sqlite3.Connection, folder_id: str, name: str) -> bool:
    if not name.strip():
        raise ValueError("Folder name is empty")
    with conn:
        return conn.execute("UPDATE folders SET name = ? WHERE id = ?", (name.strip(), folder_id)).rowcount > 0


def delete_folder(conn: sqlite3.Connection, folder_id: str) -> bool:
    """Its offers become unfiled; nothing else is deleted."""
    with conn:
        conn.execute("UPDATE applications SET folder_id = NULL WHERE folder_id = ?", (folder_id,))
        return conn.execute("DELETE FROM folders WHERE id = ?", (folder_id,)).rowcount > 0


def _contact(row: sqlite3.Row) -> Dict[str, Any]:
    return {**dict(row), "reached_out": bool(row["reached_out"])}


def list_contacts(conn: sqlite3.Connection, application_id: str) -> List[Dict[str, Any]]:
    rows = conn.execute("SELECT * FROM contacts WHERE application_id = ? ORDER BY created_at", (application_id,)).fetchall()
    return [_contact(r) for r in rows]


def add_contact(conn: sqlite3.Connection, application_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    offer = get_offer_by_application(conn, application_id)
    if not offer:
        return None
    now = _now()
    row = {k: data.get(k) for k in _CONTACT_FIELDS}
    row.update(id=str(uuid.uuid4()), application_id=application_id, reached_out=int(bool(data.get("reached_out"))),
               reached_at=now if data.get("reached_out") else None, created_at=now, updated_at=now)
    with conn:
        conn.execute(f"INSERT INTO contacts ({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})", list(row.values()))
        log_event(conn, "contact.added", actor="user", offer_id=offer["id"], application_id=application_id,
                  payload={"contact_id": row["id"], "role": row["role"]})
    return _contact(conn.execute("SELECT * FROM contacts WHERE id = ?", (row["id"],)).fetchone())


def update_contact(conn: sqlite3.Connection, contact_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    current = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
    if not current:
        return None
    changes = {k: data[k] for k in _CONTACT_FIELDS if k in data}
    if "reached_out" in data and bool(data["reached_out"]) != bool(current["reached_out"]):
        changes["reached_out"] = int(bool(data["reached_out"]))
        changes["reached_at"] = _now() if data["reached_out"] else None
    if not changes:
        return _contact(current)
    changes["updated_at"] = _now()
    with conn:
        conn.execute(f"UPDATE contacts SET {', '.join(f'{k} = ?' for k in changes)} WHERE id = ?", [*changes.values(), contact_id])
        if "reached_out" in changes:
            log_event(conn, "contact.reached_out" if changes["reached_out"] else "contact.unmarked", actor="user",
                      application_id=current["application_id"], payload={"contact_id": contact_id})
    return _contact(conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone())


def delete_contact(conn: sqlite3.Connection, contact_id: str) -> bool:
    with conn:
        return conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,)).rowcount > 0


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

        # folders: create, unique name, move, delete -> unfiled
        app_id = o["application_id"]
        f = create_folder(c, " Data roles ")
        assert f["name"] == "Data roles"
        try:
            create_folder(c, "data ROLES")
            raise AssertionError("expected IntegrityError")
        except sqlite3.IntegrityError:
            pass
        assert set_folder(c, app_id, f["id"])["folder_id"] == f["id"]
        assert list_folders(c)[0]["count"] == 1
        try:
            set_folder(c, app_id, "nope")
            raise AssertionError("expected ValueError")
        except ValueError:
            pass
        assert rename_folder(c, f["id"], "Data")
        assert delete_folder(c, f["id"]) and get_offer(c, o["id"])["folder_id"] is None

        # notes + contacts
        assert set_notes(c, app_id, "Ask about remote")["notes"] == "Ask about remote"
        k = add_contact(c, app_id, {"name": "Sam", "role": "Recruiter", "linkedin_url": "https://linkedin.com/in/sam"})
        assert k["reached_out"] is False and get_offer(c, o["id"])["contacts_count"] == 1
        k2 = update_contact(c, k["id"], {"reached_out": True})
        assert k2["reached_out"] and k2["reached_at"]
        assert update_contact(c, k["id"], {"reached_out": False})["reached_at"] is None
        types = [r["type"] for r in c.execute("SELECT type FROM events ORDER BY id")]
        assert types[-4:] == ["application.moved", "contact.added", "contact.reached_out", "contact.unmarked"], types
        assert delete_contact(c, k["id"]) and list_contacts(c, app_id) == []
        c.close()

        # --- edits, normalization, search, filters, views ---
        s = connect(Path(d) / "search.db")
        a1 = insert_offer(s, {"title": "Data Engineer", "company": "Doctolib", "location": "Paris",
                              "skills": ["python", "Postgres", "Python", " dbt "], "contract_type": "permanent",
                              "remote_policy": "hybrid", "deadline": "2026-12-01", "raw_text": "Pipelines de données en temps réel"})
        assert a1["skills"] == ["Python", "PostgreSQL", "dbt"], a1["skills"]
        a2 = insert_offer(s, {"title": "ML Intern", "company": "Alan", "location": "Lyon", "skills": ["PyTorch"],
                              "nice_to_have": ["SQL"], "contract_type": "internship", "deadline": "2026-11-20"})
        insert_offer(s, {"title": "Sales Exec", "company": "Qonto", "skills": ["CRM"]}, status="applied")

        assert [o["title"] for o in query_offers(s, {"q": "pyth"})] == ["Data Engineer"]       # prefix match on skills
        assert [o["title"] for o in query_offers(s, {"q": "donnees"})] == ["Data Engineer"]    # accents ignored
        assert query_offers(s, {"q": 'C++ "OR'}) == []                                         # odd input is safe
        assert [o["title"] for o in query_offers(s, {"status": ["applied"]})] == ["Sales Exec"]
        assert [o["title"] for o in query_offers(s, {"sort": "deadline"})][:2] == ["ML Intern", "Data Engineer"]
        assert [o["title"] for o in query_offers(s, {"deadline_before": "2026-11-30"})] == ["ML Intern"]
        fo = create_folder(s, "Data")
        set_folder(s, a1["application_id"], fo["id"])
        assert [o["title"] for o in query_offers(s, {"folder": fo["id"]})] == ["Data Engineer"]
        assert len(query_offers(s, {"folder": "unfiled"})) == 2

        e = update_offer(s, a2["id"], {"title": "ML Engineer Intern", "skills": ["pytorch", "k8s"], "model": "hack"})
        assert e["title"] == "ML Engineer Intern" and e["skills"] == ["pytorch", "Kubernetes"] and e["model"] is None
        assert [o["title"] for o in query_offers(s, {"q": "engineer intern"})] == ["ML Engineer Intern"]  # index follows edits
        ev = s.execute("SELECT payload FROM events WHERE type = 'offer.edited'").fetchone()["payload"]
        assert json.loads(ev)["fields"] == ["title", "skills"], ev
        assert update_offer(s, a2["id"], {"title": "ML Engineer Intern"})["title"] == "ML Engineer Intern"  # no-op

        facets = offer_facets(s)
        assert facets["total"] == 3 and facets["unfiled"] == 2 and {"name": "Python", "count": 1} in facets["skills"]

        v = save_view(s, "Paris data", {"q": "data", "status": ["saved"]}, "table")
        assert list_views(s)[0]["filters"] == {"q": "data", "status": ["saved"]}
        assert save_view(s, "Paris data 2", {}, "board", view_id=v["id"])["layout"] == "board"
        for bad in (lambda: save_view(s, "x", {}, "kanban"), lambda: save_view(s, " ", {}, "grid")):
            try:
                bad()
                raise AssertionError("expected ValueError")
            except ValueError:
                pass
        assert delete_view(s, v["id"]) and list_views(s) == []
        s.close()

        # a database created before folders/notes existed is migrated in place
        old = sqlite3.connect(Path(d) / "old.db")
        old.executescript("CREATE TABLE applications (id TEXT PRIMARY KEY, offer_id TEXT NOT NULL UNIQUE, "
                          "status TEXT NOT NULL DEFAULT 'saved', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);")
        old.close()
        m = connect(Path(d) / "old.db")
        assert {"folder_id", "notes"} <= {r["name"] for r in m.execute("PRAGMA table_info(applications)")}
        m.close()
    print("db ok")
