"""PostgreSQL storage. Every function takes the logged-in user's id and only ever touches that user's rows."""
from __future__ import annotations

import atexit
import re
import threading
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src.config.settings import settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
IntegrityError = psycopg.IntegrityError  # duplicate names etc.; the API turns it into 409

# One status list for code, API and UI (spec v0.1, D2)
STATUSES = ("saved", "to_apply", "applied", "interview", "offer", "accepted", "rejected", "archived")
ACTORS = ("user", "ai", "automation")
LAYOUTS = ("grid", "table", "board")

_JSON_FIELDS = ("skills", "nice_to_have", "missions", "requirements")
_OFFER_FIELDS = (
    "url", "title", "company", "location", "remote_policy", "contract_type", "seniority",
    "salary", "deadline", "summary", "raw_text", "source", "model", "prompt_version", "match_score",
)
_CONTACT_FIELDS = ("name", "role", "linkedin_url", "notes")

_VIEW = """
SELECT o.id, o.url, o.title, o.company, o.location, o.remote_policy, o.contract_type, o.seniority, o.salary,
       o.deadline, o.skills, o.nice_to_have, o.missions, o.requirements, o.summary, o.raw_text, o.source,
       o.model, o.prompt_version, o.match_score, o.created_at, o.updated_at,
       a.id AS application_id, a.status, a.next_action, a.next_action_at, a.applied_at, a.folder_id, a.notes,
       (SELECT count(*) FROM contacts c WHERE c.application_id = a.id) AS contacts_count
FROM offers o JOIN applications a ON a.offer_id = o.id
"""


# --- connections -------------------------------------------------------------------------------------

def _plain(v: Any) -> Any:
    """DB values -> JSON-friendly values (the API and the UI work with strings)."""
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def _row_factory(cursor):
    make = dict_row(cursor)
    return lambda values: {k: _plain(v) for k, v in make(values).items()}


def _set_search_path(conn: psycopg.Connection, schema: str) -> None:
    conn.execute(sql.SQL("SET search_path TO {}, public, extensions").format(sql.Identifier(schema)))
    conn.commit()


def connect(url: str | None = None, schema: str | None = None) -> psycopg.Connection:
    """One standalone connection (CLI, scripts, self-checks). The API uses the pool instead."""
    url = url or settings.DATABASE_URL
    if not url:
        raise RuntimeError("DATABASE_URL is not set (see .env.example)")
    # prepare_threshold=None: no server-side prepared statements, so connection poolers work
    conn = psycopg.connect(url, row_factory=_row_factory, prepare_threshold=None)
    _set_search_path(conn, schema or settings.DB_SCHEMA)
    return conn


_pool = None
_pool_lock = threading.Lock()  # the first requests arrive together, in different threads: create one pool only


def pool():
    global _pool
    with _pool_lock:
        if _pool is None:
            from psycopg_pool import ConnectionPool
            if not settings.DATABASE_URL:
                raise RuntimeError("DATABASE_URL is not set (see .env.example)")
            _pool = ConnectionPool(
                settings.DATABASE_URL, min_size=1, max_size=5, open=True,
                kwargs={"row_factory": _row_factory, "prepare_threshold": None},
                configure=lambda c: _set_search_path(c, settings.DB_SCHEMA),
            )
            atexit.register(close_pool)  # CLI/scripts: close before Python shuts its threads down
    return _pool


def close_pool() -> None:
    """On shutdown: close connections cleanly (the container stops gracefully)."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    """Borrow a pooled connection for one request; committed on success, rolled back on error."""
    with pool().connection() as conn:
        yield conn


def migrate(conn: psycopg.Connection, schema: str | None = None) -> List[str]:
    """Apply the SQL files in migrations/ that this schema has not run yet, in name order."""
    schema = schema or settings.DB_SCHEMA
    applied_now = []
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (schema,))  # two containers starting at once
        conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
        conn.execute(sql.SQL("SET LOCAL search_path TO {}, public, extensions").format(sql.Identifier(schema)))
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
                     "(name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
        done = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations")}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name not in done:
                conn.execute(path.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
                applied_now.append(path.name)
    _set_search_path(conn, schema)
    return applied_now


@contextmanager
def temp_schema(url: str | None = None) -> Iterator[psycopg.Connection]:
    """A throwaway, migrated schema for tests and measurements; dropped afterwards."""
    schema = f"test_{uuid.uuid4().hex[:12]}"
    conn = connect(url, schema)
    try:
        migrate(conn, schema)
        yield conn
    finally:
        conn.rollback()
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        conn.commit()
        conn.close()


def _id(value: Any) -> Optional[str]:
    """A well-formed uuid string, or None (so a bad id from a URL is 'not found', not a DB error)."""
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError):
        return None


def _date(value: Any) -> Optional[str]:
    v = str(value or "").strip()[:10]
    return v if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) else None


# --- offers & applications -----------------------------------------------------------------------------

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


def log_event(conn, user_id: str, type_: str, *, actor: str, offer_id: Optional[str] = None,
              application_id: Optional[str] = None, payload: Dict[str, Any] | None = None) -> None:
    if actor not in ACTORS:
        raise ValueError(f"Unknown actor: {actor}")
    conn.execute(
        "INSERT INTO events (user_id, offer_id, application_id, actor, type, payload) VALUES (%s, %s, %s, %s, %s, %s)",
        (user_id, offer_id, application_id, actor, type_, Jsonb(payload or {})),
    )


def insert_offer(conn, user_id: str, data: Dict[str, Any], *, status: str = "saved", actor: str = "user") -> Dict[str, Any]:
    """Create the offer and its application in one transaction."""
    if status not in STATUSES:
        raise ValueError(f"Unknown status: {status}")
    data = {**data, "skills": normalize_skills(data.get("skills")), "nice_to_have": normalize_skills(data.get("nice_to_have"))}
    row = {k: data.get(k) for k in _OFFER_FIELDS}
    row["deadline"] = _date(row["deadline"])
    row.update({f: Jsonb(data.get(f) or []) for f in _JSON_FIELDS})
    row.update(id=_id(data.get("id")) or str(uuid.uuid4()), user_id=user_id)
    if data.get("created_at"):  # imports keep their original dates
        row.update(created_at=data["created_at"], updated_at=data.get("updated_at") or data["created_at"])

    with conn.transaction():
        conn.execute(sql.SQL("INSERT INTO offers ({}) VALUES ({})").format(
            sql.SQL(", ").join(map(sql.Identifier, row)), sql.SQL(", ").join(sql.Placeholder() * len(row))),
            list(row.values()))
        app_id = conn.execute(
            "INSERT INTO applications (user_id, offer_id, status, applied_at) "
            "VALUES (%s, %s, %s, CASE WHEN %s THEN now() END) RETURNING id",
            (user_id, row["id"], status, status == "applied"),
        ).fetchone()["id"]
        log_event(conn, user_id, "offer.created", actor=actor, offer_id=row["id"], application_id=app_id,
                  payload={"source": row["source"], "status": status})
    return get_offer(conn, user_id, row["id"])


def _one(conn, where: str, params: tuple) -> Optional[Dict[str, Any]]:
    return conn.execute(_VIEW + " WHERE o.user_id = %s AND " + where, params).fetchone()


def get_offer(conn, user_id: str, offer_id: str) -> Optional[Dict[str, Any]]:
    oid = _id(offer_id)
    return _one(conn, "o.id = %s", (user_id, oid)) if oid else None


def get_offer_by_application(conn, user_id: str, application_id: str) -> Optional[Dict[str, Any]]:
    aid = _id(application_id)
    return _one(conn, "a.id = %s", (user_id, aid)) if aid else None


def find_offer_by_url(conn, user_id: str, url: str) -> Optional[Dict[str, Any]]:
    return _one(conn, "o.url = %s", (user_id, url))


def list_offers(conn, user_id: str) -> List[Dict[str, Any]]:
    return conn.execute(_VIEW + " WHERE o.user_id = %s ORDER BY o.created_at DESC", (user_id,)).fetchall()


def update_status(conn, user_id: str, application_id: str, status: str, *, actor: str = "user") -> Optional[Dict[str, Any]]:
    if status not in STATUSES:
        raise ValueError(f"Unknown status: {status}")
    offer = get_offer_by_application(conn, user_id, application_id)
    if not offer:
        return None
    if offer["status"] != status:
        with conn.transaction():
            conn.execute(
                "UPDATE applications SET status = %s, updated_at = now(), "
                "applied_at = COALESCE(applied_at, CASE WHEN %s THEN now() END) WHERE id = %s AND user_id = %s",
                (status, status == "applied", offer["application_id"], user_id),
            )
            log_event(conn, user_id, "application.status_changed", actor=actor, offer_id=offer["id"],
                      application_id=offer["application_id"], payload={"from": offer["status"], "to": status})
    return get_offer_by_application(conn, user_id, application_id)


# Fields you can correct on an offer card (provenance fields like model/source stay as captured)
EDITABLE_OFFER_FIELDS = ("url", "title", "company", "location", "remote_policy", "contract_type", "seniority",
                         "salary", "deadline", "summary", "raw_text") + _JSON_FIELDS


def update_offer(conn, user_id: str, offer_id: str, changes: Dict[str, Any], *, actor: str = "user") -> Optional[Dict[str, Any]]:
    """Apply edits to the posting fields; the event records which fields changed (your edits win over AI values)."""
    offer = get_offer(conn, user_id, offer_id)
    if not offer:
        return None
    changes = {k: v for k, v in changes.items() if k in EDITABLE_OFFER_FIELDS}
    for f in ("skills", "nice_to_have"):
        if f in changes:
            changes[f] = normalize_skills(changes[f])
    if "deadline" in changes:
        changes["deadline"] = _date(changes["deadline"])
    changed = [k for k, v in changes.items() if offer.get(k) != v]
    if not changed:
        return offer
    values = {k: Jsonb(changes[k] or []) if k in _JSON_FIELDS else changes[k] for k in changed}
    with conn.transaction():
        conn.execute(sql.SQL("UPDATE offers SET {}, updated_at = now() WHERE id = %s AND user_id = %s").format(
            sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(k)) for k in values)),
            [*values.values(), offer["id"], user_id])
        log_event(conn, user_id, "offer.edited", actor=actor, offer_id=offer["id"],
                  application_id=offer["application_id"], payload={"fields": changed})
    return get_offer(conn, user_id, offer_id)


# --- search, filters, sort -------------------------------------------------------------------------------

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
    "deadline": "o.deadline ASC NULLS LAST",
    "title": "lower(o.title)",
    "company": "lower(o.company) NULLS LAST",
    "updated": "GREATEST(o.updated_at, a.updated_at) DESC",
    "relevance": "ts_rank_cd(o.search, to_tsquery('simple', f_unaccent(%(q)s))) DESC",  # only with a search query
}


def _fts_query(q: str) -> str:
    """User text -> safe tsquery text: every word must match, as a prefix ('pyth' finds 'python')."""
    words = re.findall(r"[^\W_]+", q, flags=re.UNICODE)
    return " & ".join(f"{w}:*" for w in words)


def query_offers(conn, user_id: str, f: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    """Search + filters + sort over one user's offers. Lists are OR within a filter, AND across filters."""
    f = f or {}
    where, params = ["o.user_id = %(uid)s"], {"uid": user_id}
    fts = _fts_query(f.get("q") or "")
    if fts:
        where.append("o.search @@ to_tsquery('simple', f_unaccent(%(q)s))")
        params["q"] = fts
    for key, (column, _) in ENUM_FILTERS.items():
        values = [v for v in (f.get(key) or []) if v]
        if values:
            where.append(f"{column} = ANY(%({key})s)")
            params[key] = values
    folder = f.get("folder")
    if folder == "unfiled":
        where.append("a.folder_id IS NULL")
    elif folder:
        where.append("a.folder_id = %(folder)s")
        params["folder"] = _id(folder)
    if f.get("deadline_before"):
        where.append("o.deadline <= %(deadline_before)s")
        params["deadline_before"] = _date(f["deadline_before"])
    sort = f.get("sort") or ("relevance" if fts else "recent")
    if sort not in SORTS or (sort == "relevance" and not fts):
        sort = "recent"
    return conn.execute(_VIEW + " WHERE " + " AND ".join(where) + f" ORDER BY {SORTS[sort]}, o.id", params).fetchall()


def offer_facets(conn, user_id: str) -> Dict[str, Any]:
    """Totals for the sidebar."""
    return conn.execute(
        "SELECT count(*) AS total, count(*) FILTER (WHERE folder_id IS NULL) AS unfiled "
        "FROM applications WHERE user_id = %s", (user_id,)).fetchone()


# --- views, folders, notes -------------------------------------------------------------------------------

def list_views(conn, user_id: str) -> List[Dict[str, Any]]:
    return conn.execute("SELECT * FROM views WHERE user_id = %s ORDER BY lower(name)", (user_id,)).fetchall()


def save_view(conn, user_id: str, name: str, filters: Dict[str, Any], layout: str, view_id: Optional[str] = None) -> Dict[str, Any]:
    """Create (no id) or update a view. Raises IntegrityError on a duplicate name, KeyError on an unknown id."""
    if not name.strip():
        raise ValueError("View name is empty")
    if layout not in LAYOUTS:
        raise ValueError(f"Unknown layout: {layout}")
    with conn.transaction():
        if view_id:
            row = conn.execute("UPDATE views SET name = %s, filters = %s, layout = %s WHERE id = %s AND user_id = %s "
                               "RETURNING *", (name.strip(), Jsonb(filters), layout, _id(view_id), user_id)).fetchone()
            if not row:
                raise KeyError(view_id)
            return row
        return conn.execute("INSERT INTO views (user_id, name, filters, layout) VALUES (%s, %s, %s, %s) RETURNING *",
                            (user_id, name.strip(), Jsonb(filters), layout)).fetchone()


def delete_view(conn, user_id: str, view_id: str) -> bool:
    with conn.transaction():
        return conn.execute("DELETE FROM views WHERE id = %s AND user_id = %s", (_id(view_id), user_id)).rowcount > 0


def set_folder(conn, user_id: str, application_id: str, folder_id: Optional[str], *, actor: str = "user") -> Optional[Dict[str, Any]]:
    """Move an application into one of the user's folders (None = unfiled)."""
    offer = get_offer_by_application(conn, user_id, application_id)
    if not offer:
        return None
    if folder_id and not conn.execute("SELECT 1 FROM folders WHERE id = %s AND user_id = %s",
                                      (_id(folder_id), user_id)).fetchone():
        raise ValueError(f"Unknown folder: {folder_id}")
    if offer["folder_id"] != folder_id:
        with conn.transaction():
            conn.execute("UPDATE applications SET folder_id = %s, updated_at = now() WHERE id = %s AND user_id = %s",
                         (folder_id, offer["application_id"], user_id))
            log_event(conn, user_id, "application.moved", actor=actor, offer_id=offer["id"],
                      application_id=offer["application_id"], payload={"from": offer["folder_id"], "to": folder_id})
    return get_offer_by_application(conn, user_id, application_id)


def set_notes(conn, user_id: str, application_id: str, notes: str) -> Optional[Dict[str, Any]]:
    with conn.transaction():
        n = conn.execute("UPDATE applications SET notes = %s, updated_at = now() WHERE id = %s AND user_id = %s",
                         (notes, _id(application_id), user_id)).rowcount
    return get_offer_by_application(conn, user_id, application_id) if n else None


def list_folders(conn, user_id: str) -> List[Dict[str, Any]]:
    return conn.execute(
        "SELECT f.id, f.name, f.created_at, count(a.id) AS count FROM folders f "
        "LEFT JOIN applications a ON a.folder_id = f.id WHERE f.user_id = %s "
        "GROUP BY f.id ORDER BY lower(f.name)", (user_id,)).fetchall()


def create_folder(conn, user_id: str, name: str) -> Dict[str, Any]:
    """Raises IntegrityError if the user already has that name (case-insensitive)."""
    if not name.strip():
        raise ValueError("Folder name is empty")
    with conn.transaction():
        row = conn.execute("INSERT INTO folders (user_id, name) VALUES (%s, %s) RETURNING id, name, created_at",
                           (user_id, name.strip())).fetchone()
    return {**row, "count": 0}


def rename_folder(conn, user_id: str, folder_id: str, name: str) -> bool:
    if not name.strip():
        raise ValueError("Folder name is empty")
    with conn.transaction():
        return conn.execute("UPDATE folders SET name = %s WHERE id = %s AND user_id = %s",
                            (name.strip(), _id(folder_id), user_id)).rowcount > 0


def delete_folder(conn, user_id: str, folder_id: str) -> bool:
    """Its offers become unfiled (ON DELETE SET NULL); nothing else is deleted."""
    with conn.transaction():
        return conn.execute("DELETE FROM folders WHERE id = %s AND user_id = %s", (_id(folder_id), user_id)).rowcount > 0


# --- contacts -------------------------------------------------------------------------------------------

def list_contacts(conn, user_id: str, application_id: str) -> List[Dict[str, Any]]:
    return conn.execute("SELECT * FROM contacts WHERE application_id = %s AND user_id = %s ORDER BY created_at",
                        (_id(application_id), user_id)).fetchall()


def add_contact(conn, user_id: str, application_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    offer = get_offer_by_application(conn, user_id, application_id)
    if not offer:
        return None
    reached = bool(data.get("reached_out"))
    with conn.transaction():
        row = conn.execute(
            "INSERT INTO contacts (user_id, application_id, name, role, linkedin_url, notes, reached_out, reached_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, CASE WHEN %s THEN now() END) RETURNING *",
            (user_id, offer["application_id"], *(data.get(k) for k in _CONTACT_FIELDS), reached, reached)).fetchone()
        log_event(conn, user_id, "contact.added", actor="user", offer_id=offer["id"],
                  application_id=offer["application_id"], payload={"contact_id": row["id"], "role": row["role"]})
    return row


def update_contact(conn, user_id: str, contact_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    cid = _id(contact_id)
    current = conn.execute("SELECT * FROM contacts WHERE id = %s AND user_id = %s", (cid, user_id)).fetchone() if cid else None
    if not current:
        return None
    changes = {k: data[k] for k in _CONTACT_FIELDS if k in data}
    if "reached_out" in data and bool(data["reached_out"]) != current["reached_out"]:
        changes["reached_out"] = bool(data["reached_out"])
        changes["reached_at"] = datetime.now(timezone.utc) if changes["reached_out"] else None
    if not changes:
        return current
    with conn.transaction():
        row = conn.execute(sql.SQL(
            "UPDATE contacts SET {}, updated_at = now() WHERE id = %s AND user_id = %s RETURNING *").format(
            sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(k)) for k in changes)),
            [*changes.values(), cid, user_id]).fetchone()
        if "reached_out" in changes:
            log_event(conn, user_id, "contact.reached_out" if changes["reached_out"] else "contact.unmarked",
                      actor="user", application_id=current["application_id"], payload={"contact_id": cid})
    return row


def delete_contact(conn, user_id: str, contact_id: str) -> bool:
    with conn.transaction():
        return conn.execute("DELETE FROM contacts WHERE id = %s AND user_id = %s", (_id(contact_id), user_id)).rowcount > 0


# --- profile (parsed CV + the file itself) -----------------------------------------------------------------

def get_profile(conn, user_id: str) -> Optional[Dict[str, Any]]:
    return conn.execute("SELECT profile, source_file, cv_mime, updated_at FROM profiles WHERE user_id = %s",
                        (user_id,)).fetchone()


def get_cv_file(conn, user_id: str) -> Optional[Dict[str, Any]]:
    return conn.execute("SELECT source_file, cv_file, cv_mime FROM profiles WHERE user_id = %s AND cv_file IS NOT NULL",
                        (user_id,)).fetchone()


def save_profile(conn, user_id: str, profile: Dict[str, Any], *, source_file: Optional[str] = None,
                 cv_file: Optional[bytes] = None, cv_mime: Optional[str] = None) -> None:
    """Upsert. Without a new file, the stored CV file is kept."""
    with conn.transaction():
        conn.execute(
            "INSERT INTO profiles (user_id, profile, source_file, cv_file, cv_mime) VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (user_id) DO UPDATE SET profile = EXCLUDED.profile, updated_at = now(), "
            "source_file = COALESCE(EXCLUDED.source_file, profiles.source_file), "
            "cv_file = COALESCE(EXCLUDED.cv_file, profiles.cv_file), cv_mime = COALESCE(EXCLUDED.cv_mime, profiles.cv_mime)",
            (user_id, Jsonb(profile), source_file, cv_file, cv_mime))


MAX_INSTRUCTIONS_CHARS = 2000


def get_instructions(conn, user_id: str) -> str:
    """The user's personal instructions for generated documents ('' if never set)."""
    row = conn.execute("SELECT instructions FROM preferences WHERE user_id = %s", (user_id,)).fetchone()
    return row["instructions"] if row else ""


def save_instructions(conn, user_id: str, instructions: str) -> str:
    instructions = (instructions or "").strip()
    if len(instructions) > MAX_INSTRUCTIONS_CHARS:
        raise ValueError(f"Instructions are limited to {MAX_INSTRUCTIONS_CHARS} characters")
    with conn.transaction():
        conn.execute(
            "INSERT INTO preferences (user_id, instructions) VALUES (%s, %s) "
            "ON CONFLICT (user_id) DO UPDATE SET instructions = EXCLUDED.instructions, updated_at = now()",
            (user_id, instructions))
    return instructions


DOC_TYPES = ("cover-letter", "cold-email", "interview")


def add_document(conn, user_id: str, offer_id: str, doc_type: str, content: str, *, parent_id: Optional[str] = None,
                 feedback: Optional[str] = None, settings: Dict[str, Any] | None = None, model: Optional[str] = None,
                 prompt_version: Optional[str] = None, actor: str = "ai") -> Optional[Dict[str, Any]]:
    """Save a new version of the offer's document of this type. None if the offer is not the user's."""
    if doc_type not in DOC_TYPES:
        raise ValueError(f"Unknown document type: {doc_type}")
    if not (content or "").strip():
        raise ValueError("Document is empty")
    offer = get_offer(conn, user_id, offer_id)
    if not offer:
        return None
    with conn.transaction():
        # the lock serializes two saves of the same document, so versions stay 1, 2, 3...
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"{offer['id']}:{doc_type}",))
        row = conn.execute(
            "INSERT INTO documents (user_id, offer_id, doc_type, version, parent_id, content, feedback, settings, "
            "model, prompt_version) VALUES (%s, %s, %s, (SELECT coalesce(max(version), 0) + 1 FROM documents "
            "WHERE offer_id = %s AND doc_type = %s), %s, %s, %s, %s, %s, %s) RETURNING *",
            (user_id, offer["id"], doc_type, offer["id"], doc_type, _id(parent_id), content.strip(), feedback,
             Jsonb(settings or {}), model, prompt_version)).fetchone()
        log_event(conn, user_id, "document.created", actor=actor, offer_id=offer["id"],
                  application_id=offer["application_id"],
                  payload={"document_id": row["id"], "doc_type": doc_type, "version": row["version"]})
    return row


def get_document(conn, user_id: str, document_id: str) -> Optional[Dict[str, Any]]:
    did = _id(document_id)
    return conn.execute("SELECT * FROM documents WHERE id = %s AND user_id = %s", (did, user_id)).fetchone() if did else None


def list_documents(conn, user_id: str, offer_id: str, doc_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """All versions for an offer, newest first (optionally one document type)."""
    sql_ = "SELECT * FROM documents WHERE user_id = %s AND offer_id = %s"
    params: list = [user_id, _id(offer_id)]
    if doc_type:
        sql_ += " AND doc_type = %s"
        params.append(doc_type)
    return conn.execute(sql_ + " ORDER BY doc_type, version DESC", params).fetchall()


def log_llm_call(conn, call: Dict[str, Any]) -> None:
    with conn.transaction():
        conn.execute(sql.SQL("INSERT INTO llm_calls ({}) VALUES ({})").format(
            sql.SQL(", ").join(map(sql.Identifier, call)), sql.SQL(", ").join(sql.Placeholder() * len(call))),
            list(call.values()))


if __name__ == "__main__":
    # Needs a reachable Postgres (DATABASE_URL); works in a throwaway schema that is dropped afterwards.
    U, V = str(uuid.uuid4()), str(uuid.uuid4())  # two users

    def raises(exc, fn):
        try:
            fn()
        except exc:
            return True
        raise AssertionError(f"expected {exc.__name__}")

    with temp_schema() as c:
        assert migrate(c, c.execute("SELECT current_schema() AS s").fetchone()["s"]) == []  # idempotent

        o = insert_offer(c, U, {"url": "https://x/1", "title": "Data Eng", "skills": ["SQL"], "source": "test"}, actor="ai")
        assert o["skills"] == ["SQL"] and o["status"] == "saved" and o["application_id"], o
        assert find_offer_by_url(c, U, "https://x/1")["id"] == o["id"]

        a = update_status(c, U, o["application_id"], "applied")
        assert a["status"] == "applied" and a["applied_at"], a
        update_status(c, U, o["application_id"], "applied")  # no-op: same status, no event
        update_status(c, U, o["application_id"], "interview")
        assert get_offer(c, U, o["id"])["applied_at"] == a["applied_at"]  # first applied date kept
        assert get_offer(c, U, "not-a-uuid") is None

        raises(ValueError, lambda: update_status(c, U, o["application_id"], "interviewing"))
        raises(ValueError, lambda: insert_offer(c, U, {"title": "x"}, status="nope"))
        raises(ValueError, lambda: log_event(c, U, "x", actor="robot"))

        rows = [(r["type"], r["actor"]) for r in c.execute("SELECT type, actor FROM events ORDER BY id")]
        assert rows == [("offer.created", "ai"), ("application.status_changed", "user"),
                        ("application.status_changed", "user")], rows

        log_llm_call(c, {"user_id": U, "role": "extract", "provider": "p", "model": "m", "status": "ok", "input_tokens": 3})
        assert c.execute("SELECT input_tokens FROM llm_calls").fetchone()["input_tokens"] == 3

        # folders: create, unique name, move, delete -> unfiled
        app_id = o["application_id"]
        f = create_folder(c, U, " Data roles ")
        assert f["name"] == "Data roles"
        raises(IntegrityError, lambda: create_folder(c, U, "data ROLES"))
        assert set_folder(c, U, app_id, f["id"])["folder_id"] == f["id"]
        assert list_folders(c, U)[0]["count"] == 1
        raises(ValueError, lambda: set_folder(c, U, app_id, str(uuid.uuid4())))
        assert rename_folder(c, U, f["id"], "Data")
        assert delete_folder(c, U, f["id"]) and get_offer(c, U, o["id"])["folder_id"] is None

        # notes + contacts
        assert set_notes(c, U, app_id, "Ask about remote")["notes"] == "Ask about remote"
        k = add_contact(c, U, app_id, {"name": "Sam", "role": "Recruiter", "linkedin_url": "https://linkedin.com/in/sam"})
        assert k["reached_out"] is False and get_offer(c, U, o["id"])["contacts_count"] == 1
        k2 = update_contact(c, U, k["id"], {"reached_out": True})
        assert k2["reached_out"] and k2["reached_at"]
        assert update_contact(c, U, k["id"], {"reached_out": False})["reached_at"] is None
        types = [r["type"] for r in c.execute("SELECT type FROM events ORDER BY id")]
        assert types[-4:] == ["application.moved", "contact.added", "contact.reached_out", "contact.unmarked"], types
        assert delete_contact(c, U, k["id"]) and list_contacts(c, U, app_id) == []

        # --- isolation: user V sees and changes nothing of user U ---
        assert get_offer(c, V, o["id"]) is None and find_offer_by_url(c, V, "https://x/1") is None
        assert list_offers(c, V) == [] and query_offers(c, V) == [] and offer_facets(c, V)["total"] == 0
        assert update_status(c, V, app_id, "rejected") is None and set_notes(c, V, app_id, "x") is None
        assert update_offer(c, V, o["id"], {"title": "hijack"}) is None and add_contact(c, V, app_id, {"name": "x"}) is None
        fu = create_folder(c, U, "Mine")
        assert not rename_folder(c, V, fu["id"], "x") and not delete_folder(c, V, fu["id"]) and list_folders(c, V) == []
        create_folder(c, V, "Mine")  # same name is fine for another user
        vo = insert_offer(c, V, {"url": "https://x/1", "title": "Same URL, other user"})  # url unique per user only
        raises(ValueError, lambda: set_folder(c, V, vo["application_id"], fu["id"]))  # not V's folder
        assert get_offer(c, U, o["id"])["status"] == "interview"

        # profile
        save_profile(c, U, {"full_name": "A"}, source_file="cv.pdf", cv_file=b"%PDF", cv_mime="application/pdf")
        save_profile(c, U, {"full_name": "B"})  # file kept
        assert get_profile(c, U)["profile"] == {"full_name": "B"} and get_cv_file(c, U)["cv_file"] == b"%PDF"
        assert get_profile(c, V) is None

        # personal instructions: per user, upsert, trimmed, bounded
        assert get_instructions(c, U) == ""
        save_instructions(c, U, "  Sign as Ada. No buzzwords.  ")
        save_instructions(c, U, "Sign as Ada.")
        assert get_instructions(c, U) == "Sign as Ada." and get_instructions(c, V) == ""
        raises(ValueError, lambda: save_instructions(c, U, "x" * (MAX_INSTRUCTIONS_CHARS + 1)))

        # documents: versions per offer and type, revisions point at their parent, user-scoped
        d1 = add_document(c, U, o["id"], "cover-letter", "Draft 1", settings={"tone": "formal"}, model="m")
        d2 = add_document(c, U, o["id"], "cover-letter", "Draft 2", parent_id=d1["id"], feedback="shorter")
        e1 = add_document(c, U, o["id"], "cold-email", "Email 1")
        assert (d1["version"], d2["version"], e1["version"]) == (1, 2, 1)
        assert d2["parent_id"] == d1["id"] and d1["settings"] == {"tone": "formal"}
        assert [d["version"] for d in list_documents(c, U, o["id"], "cover-letter")] == [2, 1]
        assert len(list_documents(c, U, o["id"])) == 3
        raises(ValueError, lambda: add_document(c, U, o["id"], "poem", "x"))
        raises(ValueError, lambda: add_document(c, U, o["id"], "cold-email", "  "))
        assert add_document(c, V, o["id"], "cover-letter", "hijack") is None          # not V's offer
        assert get_document(c, V, d1["id"]) is None and list_documents(c, V, o["id"]) == []
        assert get_document(c, U, d1["id"])["content"] == "Draft 1"
        assert c.execute("SELECT count(*) n FROM events WHERE type = 'document.created'").fetchone()["n"] == 3

    # --- edits, normalization, search, filters, views ---
    with temp_schema() as s:
        a1 = insert_offer(s, U, {"title": "Data Engineer", "company": "Doctolib", "location": "Paris",
                                 "skills": ["python", "Postgres", "Python", " dbt "], "contract_type": "permanent",
                                 "remote_policy": "hybrid", "deadline": "2026-12-01", "raw_text": "Pipelines de données en temps réel"})
        assert a1["skills"] == ["Python", "PostgreSQL", "dbt"] and a1["deadline"] == "2026-12-01", a1
        a2 = insert_offer(s, U, {"title": "ML Intern", "company": "Alan", "location": "Lyon", "skills": ["PyTorch"],
                                 "nice_to_have": ["SQL"], "contract_type": "internship", "deadline": "2026-11-20"})
        insert_offer(s, U, {"title": "Sales Exec", "company": "Qonto", "skills": ["CRM"], "deadline": "soon"}, status="applied")

        assert [o["title"] for o in query_offers(s, U, {"q": "pyth"})] == ["Data Engineer"]       # prefix match on skills
        assert [o["title"] for o in query_offers(s, U, {"q": "donnees"})] == ["Data Engineer"]    # accents ignored
        assert [o["title"] for o in query_offers(s, U, {"q": "DONNÉES"})] == ["Data Engineer"]
        assert query_offers(s, U, {"q": 'C++ "OR & | ! :*'}) == []                                # odd input is safe
        assert len(query_offers(s, U, {"q": "&|!"})) == 3                                         # no words = no search
        assert [o["title"] for o in query_offers(s, U, {"status": ["applied"]})] == ["Sales Exec"]
        assert [o["title"] for o in query_offers(s, U, {"sort": "deadline"})] == ["ML Intern", "Data Engineer", "Sales Exec"]
        assert [o["title"] for o in query_offers(s, U, {"deadline_before": "2026-11-30"})] == ["ML Intern"]
        assert [o["title"] for o in query_offers(s, U, {"q": "intern doctolib"})] == []           # AND across words
        fo = create_folder(s, U, "Data")
        set_folder(s, U, a1["application_id"], fo["id"])
        assert [o["title"] for o in query_offers(s, U, {"folder": fo["id"]})] == ["Data Engineer"]
        assert len(query_offers(s, U, {"folder": "unfiled"})) == 2
        assert query_offers(s, U, {"folder": "garbage"}) == []

        e = update_offer(s, U, a2["id"], {"title": "ML Engineer Intern", "skills": ["pytorch", "k8s"], "model": "hack"})
        assert e["title"] == "ML Engineer Intern" and e["skills"] == ["pytorch", "Kubernetes"] and e["model"] is None
        assert [o["title"] for o in query_offers(s, U, {"q": "engineer intern"})] == ["ML Engineer Intern"]  # index follows edits
        # title (weight A) outranks raw text (weight D)
        insert_offer(s, U, {"title": "Analyst", "raw_text": "you will work with a data engineer"})
        ranked = [o["title"] for o in query_offers(s, U, {"q": "engineer"})]
        assert len(ranked) == 3 and ranked[-1] == "Analyst", ranked
        ev = s.execute("SELECT payload FROM events WHERE type = 'offer.edited'").fetchone()["payload"]
        assert ev["fields"] == ["title", "skills"], ev
        assert update_offer(s, U, a2["id"], {"title": "ML Engineer Intern"})["title"] == "ML Engineer Intern"  # no-op

        facets = offer_facets(s, U)
        assert facets == {"total": 4, "unfiled": 3}, facets

        v = save_view(s, U, "Paris data", {"q": "data", "status": ["saved"]}, "table")
        assert list_views(s, U)[0]["filters"] == {"q": "data", "status": ["saved"]}
        assert save_view(s, U, "Paris data 2", {}, "board", view_id=v["id"])["layout"] == "board"
        raises(KeyError, lambda: save_view(s, V, "x", {}, "grid", view_id=v["id"]))  # other user's view
        raises(ValueError, lambda: save_view(s, U, "x", {}, "kanban"))
        raises(ValueError, lambda: save_view(s, U, " ", {}, "grid"))
        assert not delete_view(s, V, v["id"])
        assert delete_view(s, U, v["id"]) and list_views(s, U) == []

    # concurrent first requests share one pool
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(8) as ex:
        assert len({id(p) for p in ex.map(lambda _: pool(), range(8))}) == 1
    close_pool()
    print("db ok")
