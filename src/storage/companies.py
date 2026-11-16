"""Company directory: links, dated notes (flag + pin) and to-dos per company, for the signed-in user only.

Offers belong to a company when their `company` field matches its name (ignoring case and spaces at the ends).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from psycopg import sql
from psycopg.types.json import Jsonb

from src.storage import db

MAX_LINKS = 20


def _url(v: Any) -> Optional[str]:
    """Links are rendered as <a href>: only http(s), never javascript:."""
    v = str(v or "").strip()
    if not v:
        return None
    p = urlparse(v)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise ValueError("links must be http(s):// URLs")
    return v


def _clean(data: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if "name" in data:
        out["name"] = " ".join(str(data["name"] or "").split())
        if not 1 <= len(out["name"]) <= 200:
            raise ValueError("Company name must be 1 to 200 characters")
    if "website" in data:
        out["website"] = _url(data["website"])
    if "links" in data:
        links = [{"label": str(link.get("label") or "").strip()[:80], "url": _url(link.get("url"))}
                 for link in (data["links"] or []) if isinstance(link, dict) and str(link.get("url") or "").strip()]
        if len(links) > MAX_LINKS:
            raise ValueError(f"At most {MAX_LINKS} links")
        out["links"] = Jsonb(links)
    return out


def _offers(conn, user_id: str, name: str) -> List[Dict[str, Any]]:
    key = name.strip().casefold()
    return [o for o in db.list_offers(conn, user_id) if (o["company"] or "").strip().casefold() == key]


def list_companies(conn, user_id: str) -> List[Dict[str, Any]]:
    """Every company with how many offers you saved there and how many to-dos are still open."""
    return conn.execute(
        "SELECT c.id, c.name, c.website, c.updated_at, "
        "(SELECT count(*) FROM offers o WHERE o.user_id = c.user_id AND lower(trim(o.company)) = lower(c.name)) AS offers_count, "
        "(SELECT count(*) FROM company_todos t WHERE t.company_id = c.id AND NOT t.done) AS open_todos, "
        "(SELECT count(*) FROM company_notes n WHERE n.company_id = c.id) AS notes_count, "
        "(SELECT count(*) FROM company_notes n WHERE n.company_id = c.id AND (n.flag IS NOT NULL OR n.pinned)) AS flagged_notes "
        "FROM companies c WHERE c.user_id = %s ORDER BY lower(c.name)", (user_id,)).fetchall()


def get_company(conn, user_id: str, company_id: str) -> Optional[Dict[str, Any]]:
    """Full company file: fields, notes (pinned first, then newest), to-dos (open first), and the offers saved there."""
    cid = db._id(company_id)
    c = conn.execute("SELECT id, user_id, name, website, links, created_at, updated_at FROM companies "
                     "WHERE id = %s AND user_id = %s", (cid, user_id)).fetchone() if cid else None
    if not c:
        return None
    c["notes"] = conn.execute("SELECT * FROM company_notes WHERE company_id = %s ORDER BY pinned DESC, created_at DESC",
                              (c["id"],)).fetchall()
    c["todos"] = conn.execute("SELECT * FROM company_todos WHERE company_id = %s ORDER BY done, due_date NULLS LAST, created_at",
                              (c["id"],)).fetchall()
    c["offers"] = _offers(conn, user_id, c["name"])
    return c


def find_company(conn, user_id: str, name: Optional[str]) -> Optional[Dict[str, Any]]:
    """The company file matching an offer's company name, if you created one."""
    if not (name or "").strip():
        return None
    row = conn.execute("SELECT id FROM companies WHERE user_id = %s AND lower(name) = lower(%s)",
                       (user_id, " ".join(name.split()))).fetchone()
    return get_company(conn, user_id, row["id"]) if row else None


def create_company(conn, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Raises db.IntegrityError if you already have a company with that name (case-insensitive).
    An optional `notes` text becomes the company's first note."""
    fields = _clean({"name": data.get("name"), **{k: data[k] for k in ("website", "links") if k in data}})
    with conn.transaction():
        row = conn.execute(sql.SQL("INSERT INTO companies (user_id, {}) VALUES (%s, {}) RETURNING id").format(
            sql.SQL(", ").join(map(sql.Identifier, fields)), sql.SQL(", ").join(sql.Placeholder() * len(fields))),
            [user_id, *fields.values()]).fetchone()
        if str(data.get("notes") or "").strip():
            add_note(conn, user_id, row["id"], {"body": data["notes"]})
    return get_company(conn, user_id, row["id"])


def update_company(conn, user_id: str, company_id: str, changes: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    fields = _clean({k: v for k, v in changes.items() if k in ("name", "website", "links")})
    if not get_company(conn, user_id, company_id):
        return None
    if fields:
        with conn.transaction():
            conn.execute(sql.SQL("UPDATE companies SET {}, updated_at = now() WHERE id = %s AND user_id = %s").format(
                sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(k)) for k in fields)),
                [*fields.values(), db._id(company_id), user_id])
    return get_company(conn, user_id, company_id)


def delete_company(conn, user_id: str, company_id: str) -> bool:
    """Deletes the file and its to-dos; the offers themselves are kept."""
    with conn.transaction():
        return conn.execute("DELETE FROM companies WHERE id = %s AND user_id = %s",
                            (db._id(company_id), user_id)).rowcount > 0


NOTE_FLAGS = ("important", "follow-up", "question", "risk")
MAX_NOTE_CHARS = 5000


def _note_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if "body" in data:
        out["body"] = str(data["body"] or "").strip()
        if not 1 <= len(out["body"]) <= MAX_NOTE_CHARS:
            raise ValueError(f"A note must be 1 to {MAX_NOTE_CHARS} characters")
    if "flag" in data:
        out["flag"] = data["flag"] or None
        if out["flag"] not in (None, *NOTE_FLAGS):
            raise ValueError(f"flag must be one of {', '.join(NOTE_FLAGS)} (or empty)")
    if "pinned" in data:
        out["pinned"] = bool(data["pinned"])
    return out


def add_note(conn, user_id: str, company_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """A new dated note on the company, optionally flagged and pinned. None if the company is not the user's."""
    fields = _note_fields({"body": data.get("body"), **{k: data[k] for k in ("flag", "pinned") if k in data}})
    cid = db._id(company_id)
    if not cid or not conn.execute("SELECT 1 FROM companies WHERE id = %s AND user_id = %s", (cid, user_id)).fetchone():
        return None
    with conn.transaction():
        conn.execute("UPDATE companies SET updated_at = now() WHERE id = %s", (cid,))
        return conn.execute(sql.SQL("INSERT INTO company_notes (user_id, company_id, {}) VALUES (%s, %s, {}) RETURNING *").format(
            sql.SQL(", ").join(map(sql.Identifier, fields)), sql.SQL(", ").join(sql.Placeholder() * len(fields))),
            [user_id, cid, *fields.values()]).fetchone()


def update_note(conn, user_id: str, note_id: str, changes: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Edit the text, change the flag (None removes it) or pin/unpin."""
    fields = _note_fields({k: v for k, v in changes.items() if k in ("body", "flag", "pinned")})
    nid = db._id(note_id)
    if not nid:
        return None
    if not fields:
        return conn.execute("SELECT * FROM company_notes WHERE id = %s AND user_id = %s", (nid, user_id)).fetchone()
    with conn.transaction():
        return conn.execute(sql.SQL("UPDATE company_notes SET {}, updated_at = now() WHERE id = %s AND user_id = %s RETURNING *").format(
            sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(k)) for k in fields)),
            [*fields.values(), nid, user_id]).fetchone()


def delete_note(conn, user_id: str, note_id: str) -> bool:
    with conn.transaction():
        return conn.execute("DELETE FROM company_notes WHERE id = %s AND user_id = %s",
                            (db._id(note_id), user_id)).rowcount > 0


def _todo_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if "text" in data:
        out["text"] = str(data["text"] or "").strip()
        if not 1 <= len(out["text"]) <= 500:
            raise ValueError("To-do text must be 1 to 500 characters")
    if "due_date" in data:
        out["due_date"] = db._date(data["due_date"]) if data["due_date"] else None
        if data["due_date"] and not out["due_date"]:
            raise ValueError("due_date must be YYYY-MM-DD")
    if "done" in data:
        out["done"] = bool(data["done"])
        out["done_at"] = datetime.now(timezone.utc) if out["done"] else None
    return out


def add_todo(conn, user_id: str, company_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    fields = _todo_fields({"text": data.get("text"), **({"due_date": data["due_date"]} if "due_date" in data else {})})
    cid = db._id(company_id)
    if not cid or not conn.execute("SELECT 1 FROM companies WHERE id = %s AND user_id = %s", (cid, user_id)).fetchone():
        return None
    with conn.transaction():
        return conn.execute("INSERT INTO company_todos (user_id, company_id, text, due_date) VALUES (%s, %s, %s, %s) RETURNING *",
                            (user_id, cid, fields["text"], fields.get("due_date"))).fetchone()


def update_todo(conn, user_id: str, todo_id: str, changes: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    fields = _todo_fields({k: v for k, v in changes.items() if k in ("text", "done", "due_date")})
    tid = db._id(todo_id)
    if not tid:
        return None
    if not fields:
        return conn.execute("SELECT * FROM company_todos WHERE id = %s AND user_id = %s", (tid, user_id)).fetchone()
    with conn.transaction():
        return conn.execute(sql.SQL("UPDATE company_todos SET {} WHERE id = %s AND user_id = %s RETURNING *").format(
            sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(k)) for k in fields)),
            [*fields.values(), tid, user_id]).fetchone()


def delete_todo(conn, user_id: str, todo_id: str) -> bool:
    with conn.transaction():
        return conn.execute("DELETE FROM company_todos WHERE id = %s AND user_id = %s",
                            (db._id(todo_id), user_id)).rowcount > 0


if __name__ == "__main__":
    import uuid

    U, V = str(uuid.uuid4()), str(uuid.uuid4())

    def raises(exc, fn):
        try:
            fn()
        except exc:
            return
        raise AssertionError(f"expected {exc.__name__}")

    with db.temp_schema() as c:
        db.insert_offer(c, U, {"title": "Data Engineer", "company": " acme "})
        db.insert_offer(c, U, {"title": "Other", "company": "Beta"})
        db.insert_offer(c, V, {"title": "V's offer", "company": "Acme"})

        a = create_company(c, U, {"name": "  Acme  ", "website": "https://acme.io",
                                  "links": [{"label": "Careers", "url": "https://acme.io/jobs"}, {"label": "empty", "url": ""}],
                                  "notes": "Series B, 200 people"})
        assert a["name"] == "Acme" and a["links"] == [{"label": "Careers", "url": "https://acme.io/jobs"}]
        assert [o["title"] for o in a["offers"]] == ["Data Engineer"]               # matched by name, U's only
        raises(db.IntegrityError, lambda: create_company(c, U, {"name": "ACME"}))
        create_company(c, V, {"name": "Acme"})                                        # same name, other user: fine
        raises(ValueError, lambda: create_company(c, U, {"name": " "}))
        raises(ValueError, lambda: create_company(c, U, {"name": "X", "website": "javascript:alert(1)"}))
        raises(ValueError, lambda: update_company(c, U, a["id"], {"links": [{"label": "x", "url": "ftp://x"}]}))

        t1 = add_todo(c, U, a["id"], {"text": "Ask Sam about the team", "due_date": "2026-11-20"})
        t2 = add_todo(c, U, a["id"], {"text": "Read the engineering blog"})
        raises(ValueError, lambda: add_todo(c, U, a["id"], {"text": ""}))
        raises(ValueError, lambda: add_todo(c, U, a["id"], {"text": "x", "due_date": "soon"}))
        done = update_todo(c, U, t2["id"], {"done": True})
        assert done["done"] and done["done_at"]
        assert update_todo(c, U, t2["id"], {"done": False})["done_at"] is None
        update_todo(c, U, t1["id"], {"done": True})

        listed = {x["name"]: x for x in list_companies(c, U)}
        assert listed["Acme"]["offers_count"] == 1 and listed["Acme"]["open_todos"] == 1
        assert [t["text"] for t in get_company(c, U, a["id"])["todos"]] == ["Read the engineering blog", "Ask Sam about the team"]
        assert find_company(c, U, "acme")["id"] == a["id"] and find_company(c, U, "Nope") is None

        # isolation: V sees and changes nothing of U's
        assert get_company(c, V, a["id"]) is None and update_company(c, V, a["id"], {"name": "x"}) is None
        assert add_todo(c, V, a["id"], {"text": "x"}) is None and update_todo(c, V, t1["id"], {"done": False}) is None
        assert not delete_todo(c, V, t1["id"]) and not delete_company(c, V, a["id"])
        assert [x["name"] for x in list_companies(c, V)] == ["Acme"] and find_company(c, V, "Acme")["id"] != a["id"]

        # notes: several per company, flags, pins; pinned first, then newest
        assert [n["body"] for n in get_company(c, U, a["id"])["notes"]] == ["Series B, 200 people"]   # from create
        n1 = add_note(c, U, a["id"], {"body": "Call with Sam: team of 6, dbt + Airflow", "flag": "important"})
        n2 = add_note(c, U, a["id"], {"body": "Ask about on-call", "flag": "question"})
        raises(ValueError, lambda: add_note(c, U, a["id"], {"body": "x", "flag": "urgent"}))
        raises(ValueError, lambda: add_note(c, U, a["id"], {"body": "  "}))
        assert add_note(c, V, a["id"], {"body": "x"}) is None                                  # not V's company
        assert update_note(c, V, n1["id"], {"pinned": True}) is None and not delete_note(c, V, n1["id"])
        update_note(c, U, n1["id"], {"pinned": True})
        assert [n["body"][:4] for n in get_company(c, U, a["id"])["notes"]] == ["Call", "Ask ", "Seri"]
        assert update_note(c, U, n2["id"], {"flag": None, "body": "Ask about on-call duty"})["flag"] is None
        row = {x["name"]: x for x in list_companies(c, U)}["Acme"]
        assert (row["notes_count"], row["flagged_notes"]) == (3, 1)
        assert delete_note(c, U, n2["id"]) and len(get_company(c, U, a["id"])["notes"]) == 2
        assert delete_todo(c, U, t1["id"]) and delete_company(c, U, a["id"])
        assert c.execute("SELECT count(*) n FROM company_todos").fetchone()["n"] == 0   # to-dos go with the company
        assert c.execute("SELECT count(*) n FROM company_notes").fetchone()["n"] == 0   # notes too
        assert len(db.list_offers(c, U)) == 2                                            # offers are kept
    print("companies ok")
