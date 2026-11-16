"""Outreach messages: categories, reference messages (the library) and drafts / sent messages, per user.

Reference messages can contain placeholders filled from the chosen offer and contact and from your profile:
{first_name} {contact_name} {their_role} {company} {role} {my_name}
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from psycopg import sql
from psycopg.types.json import Jsonb

from src.storage import db

CHANNELS = {"linkedin-note": 300, "linkedin-message": 8000, "email": 20000, "other": 20000}  # max characters
DEFAULT_CATEGORIES = ("Recruiter", "Hiring manager", "Referral ask", "Follow-up", "Thank-you", "Networking")
PLACEHOLDERS = ("first_name", "contact_name", "their_role", "company", "role", "my_name")
MAX_HISTORY = 20
_PLACEHOLDER_RE = re.compile(r"\{([a-z_]+)\}")


def _owned(conn, table: str, user_id: str, row_id: Any) -> Optional[str]:
    """The id if that row exists and is the user's, else None (ids from the URL are never trusted alone)."""
    rid = db._id(row_id)
    if not rid:
        return None
    found = conn.execute(sql.SQL("SELECT 1 FROM {} WHERE id = %s AND user_id = %s").format(sql.Identifier(table)),
                         (rid, user_id)).fetchone()
    return rid if found else None


def _text(value: Any, field: str, limit: int) -> str:
    v = str(value or "").strip()
    if not 1 <= len(v) <= limit:
        raise ValueError(f"{field} must be 1 to {limit} characters")
    return v


def _check_body(body: Any, channel: str) -> str:
    if channel not in CHANNELS:
        raise ValueError(f"channel must be one of {', '.join(CHANNELS)}")
    return _text(body, "The message", CHANNELS[channel])


# --- categories ----------------------------------------------------------------------------------------------

def list_categories(conn, user_id: str) -> List[Dict[str, Any]]:
    """Your categories with how many reference messages each holds. The defaults are created on first use."""
    if not conn.execute("SELECT 1 FROM message_categories WHERE user_id = %s LIMIT 1", (user_id,)).fetchone():
        with conn.transaction():
            for i, name in enumerate(DEFAULT_CATEGORIES):
                conn.execute("INSERT INTO message_categories (user_id, name, position) VALUES (%s, %s, %s) "
                             "ON CONFLICT DO NOTHING", (user_id, name, i))
    return conn.execute(
        "SELECT c.*, (SELECT count(*) FROM message_templates t WHERE t.category_id = c.id) AS templates_count "
        "FROM message_categories c WHERE c.user_id = %s ORDER BY c.position, lower(c.name)", (user_id,)).fetchall()


def create_category(conn, user_id: str, name: str) -> Dict[str, Any]:
    """Raises db.IntegrityError on a duplicate name (case-insensitive)."""
    name = _text(" ".join(str(name or "").split()), "Category name", 80)
    with conn.transaction():
        return conn.execute(
            "INSERT INTO message_categories (user_id, name, position) VALUES (%s, %s, "
            "(SELECT coalesce(max(position), -1) + 1 FROM message_categories WHERE user_id = %s)) RETURNING *",
            (user_id, name, user_id)).fetchone()


def rename_category(conn, user_id: str, category_id: str, name: str) -> Optional[Dict[str, Any]]:
    name = _text(" ".join(str(name or "").split()), "Category name", 80)
    with conn.transaction():
        return conn.execute("UPDATE message_categories SET name = %s WHERE id = %s AND user_id = %s RETURNING *",
                            (name, db._id(category_id), user_id)).fetchone()


def delete_category(conn, user_id: str, category_id: str) -> bool:
    """Its reference messages and drafts are kept, as Uncategorized."""
    with conn.transaction():
        return conn.execute("DELETE FROM message_categories WHERE id = %s AND user_id = %s",
                            (db._id(category_id), user_id)).rowcount > 0


# --- reference messages (library) ----------------------------------------------------------------------------

def list_templates(conn, user_id: str, category_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Pinned first, then most recently changed. category_id='uncategorized' lists those without a category."""
    where, params = "user_id = %s", [user_id]
    if category_id == "uncategorized":
        where += " AND category_id IS NULL"
    elif category_id:
        where += " AND category_id = %s"
        params.append(db._id(category_id))
    return conn.execute(f"SELECT * FROM message_templates WHERE {where} ORDER BY pinned DESC, updated_at DESC", params).fetchall()


def create_template(conn, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    channel = data.get("channel") or "linkedin-message"
    body = _check_body(data.get("body"), channel)
    title = _text(data.get("title"), "Title", 120)
    category = data.get("category_id")
    if category and not _owned(conn, "message_categories", user_id, category):
        raise ValueError("Unknown category")
    with conn.transaction():
        return conn.execute(
            "INSERT INTO message_templates (user_id, category_id, title, channel, body, pinned) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING *",
            (user_id, db._id(category) if category else None, title, channel, body, bool(data.get("pinned")))).fetchone()


def update_template(conn, user_id: str, template_id: str, changes: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """A new text bumps the version and keeps the previous wording; title, category, channel and pin don't."""
    tid = _owned(conn, "message_templates", user_id, template_id)
    if not tid:
        return None
    current = conn.execute("SELECT * FROM message_templates WHERE id = %s", (tid,)).fetchone()
    fields: Dict[str, Any] = {}
    if "title" in changes:
        fields["title"] = _text(changes["title"], "Title", 120)
    if "category_id" in changes:
        cat = changes["category_id"]
        if cat and not _owned(conn, "message_categories", user_id, cat):
            raise ValueError("Unknown category")
        fields["category_id"] = db._id(cat) if cat else None
    if "pinned" in changes:
        fields["pinned"] = bool(changes["pinned"])
    channel = changes.get("channel", current["channel"])
    if "channel" in changes or "body" in changes:
        body = _check_body(changes.get("body", current["body"]), channel)
        fields["channel"] = channel
        if body != current["body"]:
            fields["body"] = body
            fields["version"] = current["version"] + 1
            old = {"version": current["version"], "body": current["body"],
                   "replaced_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            fields["history"] = Jsonb(([old] + current["history"])[:MAX_HISTORY])
    if not fields:
        return current
    with conn.transaction():
        return conn.execute(sql.SQL("UPDATE message_templates SET {}, updated_at = clock_timestamp() WHERE id = %s RETURNING *").format(
            sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(k)) for k in fields)),
            [*fields.values(), tid]).fetchone()


def delete_template(conn, user_id: str, template_id: str) -> bool:
    with conn.transaction():
        return conn.execute("DELETE FROM message_templates WHERE id = %s AND user_id = %s",
                            (db._id(template_id), user_id)).rowcount > 0


# --- placeholders -------------------------------------------------------------------------------------------

def placeholder_values(conn, user_id: str, offer_id: Optional[str] = None, contact_id: Optional[str] = None) -> Dict[str, str]:
    """What each placeholder becomes for this offer and contact (empty when unknown)."""
    values = dict.fromkeys(PLACEHOLDERS, "")
    profile = (db.get_profile(conn, user_id) or {}).get("profile") or {}
    values["my_name"] = profile.get("full_name") or ""
    offer = db.get_offer(conn, user_id, offer_id) if offer_id else None
    if offer:
        values["company"], values["role"] = offer["company"] or "", offer["title"] or ""
    if contact_id and _owned(conn, "contacts", user_id, contact_id):
        c = conn.execute("SELECT name, role FROM contacts WHERE id = %s", (db._id(contact_id),)).fetchone()
        values["contact_name"], values["their_role"] = c["name"], c["role"] or ""
        values["first_name"] = c["name"].split()[0] if c["name"].split() else ""
    return values


def fill(body: str, values: Dict[str, str]) -> Dict[str, Any]:
    """Replace known placeholders that have a value; report the ones left to fill by hand."""
    missing: List[str] = []

    def sub(m: re.Match) -> str:
        key = m.group(1)
        if values.get(key):
            return values[key]
        if key not in missing:
            missing.append(key)
        return m.group(0)

    return {"body": _PLACEHOLDER_RE.sub(sub, body), "missing": missing}


def generalize(body: str, values: Dict[str, str]) -> str:
    """The reverse of fill: turn this offer's and contact's names back into placeholders, so a draft that worked
    can be pinned as a reusable reference ("Hi Sam" -> "Hi {first_name}"). Longest values first, so the full
    name wins over the first name; very short values (1-2 letters) are left alone to avoid false matches."""
    for key, value in sorted(values.items(), key=lambda kv: -len(kv[1] or "")):
        if value and len(value) >= 3:
            body = re.sub(rf"(?<!\w){re.escape(value)}(?!\w)", "{" + key + "}", body)
    return body


# --- drafts and sent messages --------------------------------------------------------------------------------

def _message_fields(conn, user_id: str, data: Dict[str, Any], channel: str) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    for key, table in (("category_id", "message_categories"), ("template_id", "message_templates"),
                       ("offer_id", "offers"), ("contact_id", "contacts")):
        if key in data:
            if data[key] and not _owned(conn, table, user_id, data[key]):
                raise ValueError(f"Unknown {key.replace('_id', '')}")
            fields[key] = db._id(data[key]) if data[key] else None
    if "body" in data or "channel" in data:
        fields["body"] = _check_body(data.get("body"), channel)
        fields["channel"] = channel
    return fields


def list_messages(conn, user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Drafts or sent messages (newest first), with the offer and contact names for display."""
    where, params = "m.user_id = %s", [user_id]
    if status:
        where += " AND m.status = %s"
        params.append(status)
    return conn.execute(
        "SELECT m.*, o.title AS offer_title, o.company AS offer_company, k.name AS contact_name "
        "FROM outreach_messages m LEFT JOIN offers o ON o.id = m.offer_id LEFT JOIN contacts k ON k.id = m.contact_id "
        f"WHERE {where} ORDER BY m.updated_at DESC", params).fetchall()


def create_message(conn, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    channel = data.get("channel") or "linkedin-message"
    fields = _message_fields(conn, user_id, {**data, "body": data.get("body")}, channel)
    with conn.transaction():
        return conn.execute(sql.SQL("INSERT INTO outreach_messages (user_id, {}) VALUES (%s, {}) RETURNING *").format(
            sql.SQL(", ").join(map(sql.Identifier, fields)), sql.SQL(", ").join(sql.Placeholder() * len(fields))),
            [user_id, *fields.values()]).fetchone()


def update_message(conn, user_id: str, message_id: str, changes: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Edit a draft, or mark it sent (status='sent'), which also ticks the contact's 'reached out'."""
    mid = _owned(conn, "outreach_messages", user_id, message_id)
    if not mid:
        return None
    current = conn.execute("SELECT * FROM outreach_messages WHERE id = %s", (mid,)).fetchone()
    channel = changes.get("channel", current["channel"])
    data = {k: v for k, v in changes.items() if k in ("category_id", "template_id", "offer_id", "contact_id", "body", "channel")}
    if "channel" in data and "body" not in data:
        data["body"] = current["body"]
    fields = _message_fields(conn, user_id, data, channel)
    if "status" in changes:
        if changes["status"] not in ("draft", "sent"):
            raise ValueError("status must be draft or sent")
        fields["status"] = changes["status"]
        fields["sent_at"] = datetime.now(timezone.utc) if changes["status"] == "sent" else None
    if not fields:
        return current
    with conn.transaction():
        row = conn.execute(sql.SQL("UPDATE outreach_messages SET {}, updated_at = clock_timestamp() WHERE id = %s RETURNING *").format(
            sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(k)) for k in fields)),
            [*fields.values(), mid]).fetchone()
        if fields.get("status") == "sent" and row["contact_id"]:
            contact = conn.execute("SELECT reached_out FROM contacts WHERE id = %s", (row["contact_id"],)).fetchone()
            if contact and not contact["reached_out"]:
                db.update_contact(conn, user_id, row["contact_id"], {"reached_out": True})
    return row


def delete_message(conn, user_id: str, message_id: str) -> bool:
    with conn.transaction():
        return conn.execute("DELETE FROM outreach_messages WHERE id = %s AND user_id = %s",
                            (db._id(message_id), user_id)).rowcount > 0


if __name__ == "__main__":
    import uuid

    U, V = str(uuid.uuid4()), str(uuid.uuid4())

    def raises(exc, fn):
        try:
            fn()
        except exc:
            return
        raise AssertionError(f"expected {exc.__name__}")

    # placeholders (no database)
    out = fill("Hi {first_name}, I saw the {role} role at {company}. {hook} – {my_name}",
               {"first_name": "Sam", "role": "Data Engineer", "company": "Acme", "my_name": ""})
    assert out["body"] == "Hi Sam, I saw the Data Engineer role at Acme. {hook} – {my_name}", out
    assert out["missing"] == ["hook", "my_name"]

    with db.temp_schema() as c:
        cats = list_categories(c, U)
        assert [x["name"] for x in cats] == list(DEFAULT_CATEGORIES)                     # defaults on first use
        assert len(list_categories(c, U)) == len(DEFAULT_CATEGORIES)                      # created once
        rec = cats[0]
        mine = create_category(c, U, " Alumni ")
        assert mine["name"] == "Alumni" and list_categories(c, U)[-1]["name"] == "Alumni"
        raises(db.IntegrityError, lambda: create_category(c, U, "alumni"))
        assert rename_category(c, V, mine["id"], "x") is None and not delete_category(c, V, mine["id"])

        t = create_template(c, U, {"title": "Warm intro", "channel": "linkedin-note", "category_id": rec["id"],
                                   "body": "Hi {first_name}, I'm applying for {role} at {company}."})
        raises(ValueError, lambda: create_template(c, U, {"title": "x", "channel": "linkedin-note", "body": "y" * 301}))
        raises(ValueError, lambda: create_template(c, U, {"title": "x", "channel": "fax", "body": "y"}))
        raises(ValueError, lambda: create_template(c, V, {"title": "x", "body": "y", "category_id": rec["id"]}))  # not V's
        t2 = update_template(c, U, t["id"], {"body": "Hello {first_name}! {role} at {company} caught my eye."})
        assert t2["version"] == 2 and t2["history"][0]["body"].startswith("Hi {first_name}")
        assert update_template(c, U, t["id"], {"pinned": True})["version"] == 2             # pin: no new version
        assert update_template(c, V, t["id"], {"pinned": False}) is None
        create_template(c, U, {"title": "Older one", "category_id": rec["id"], "body": "Plain text"})
        assert [x["title"] for x in list_templates(c, U, rec["id"])] == ["Warm intro", "Older one"]   # pinned first
        assert list_templates(c, V) == []

        # placeholders from a real offer + contact + profile
        o = db.insert_offer(c, U, {"title": "Data Engineer", "company": "Acme"})
        k = db.add_contact(c, U, o["application_id"], {"name": "Sam Lee", "role": "Data lead"})
        db.save_profile(c, U, {"full_name": "Ada L."})
        vals = placeholder_values(c, U, o["id"], k["id"])
        assert (vals["first_name"], vals["their_role"], vals["company"], vals["role"], vals["my_name"]) == \
            ("Sam", "Data lead", "Acme", "Data Engineer", "Ada L.")
        assert placeholder_values(c, V, o["id"], k["id"])["company"] == ""                 # V can't read U's offer
        assert fill(t2["body"], vals)["body"] == "Hello Sam! Data Engineer at Acme caught my eye."
        # generalize is the reverse of fill: names back to placeholders, whole words only
        draft = "Hi Sam Lee, the Data Engineer role at Acme fits me. Sam, thanks! Acmeville is not Acme. – Ada L."
        assert generalize(draft, vals) == ("Hi {contact_name}, the {role} role at {company} fits me. {first_name}, thanks! "
                                           "Acmeville is not {company}. – {my_name}"), generalize(draft, vals)
        assert generalize("Hello Sam", {"first_name": "Sam", "company": ""}) == "Hello {first_name}"

        # drafts -> sent ticks the contact
        m = create_message(c, U, {"body": "Hello Sam!", "channel": "linkedin-note", "offer_id": o["id"],
                                  "contact_id": k["id"], "template_id": t["id"], "category_id": rec["id"]})
        assert m["status"] == "draft"
        raises(ValueError, lambda: create_message(c, V, {"body": "x", "offer_id": o["id"]}))      # not V's offer
        assert update_message(c, U, m["id"], {"body": "Hello Sam, quick question."})["body"] == "Hello Sam, quick question."
        raises(ValueError, lambda: update_message(c, U, m["id"], {"channel": "linkedin-note", "body": "z" * 301}))
        sent = update_message(c, U, m["id"], {"status": "sent"})
        assert sent["status"] == "sent" and sent["sent_at"]
        assert db.list_contacts(c, U, o["application_id"])[0]["reached_out"] is True
        assert [x["contact_name"] for x in list_messages(c, U, "sent")] == ["Sam Lee"] and list_messages(c, U, "draft") == []
        assert update_message(c, V, m["id"], {"status": "draft"}) is None and not delete_message(c, V, m["id"])

        # deleting a category or template keeps the messages
        assert delete_category(c, U, rec["id"]) and list_templates(c, U, "uncategorized")[0]["title"] == "Warm intro"
        assert delete_template(c, U, t["id"]) and list_messages(c, U)[0]["template_id"] is None
        assert delete_message(c, U, m["id"]) and list_messages(c, U) == []
    print("outreach ok")
