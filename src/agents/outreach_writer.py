"""Adapt with AI: personalize a reference message for one offer and contact.

Context = the offer, the company's pinned / flagged notes, the contact, the candidate's profile and writing
instructions. Placeholders are filled first (no model needed for names). The model must keep the reference's
voice and stay under the channel's length limit; one retry asks it to shorten, and the caller is told if it
still doesn't fit. Nothing is saved here: the user reviews the result, then saves or pins it.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from src.storage import db, outreach

CHANNEL_LABELS = {"linkedin-note": "LinkedIn connection note", "linkedin-message": "LinkedIn message",
                  "email": "Email", "other": "Message"}


class Adapted(BaseModel):
    message: str
    changes: List[str] = Field(default_factory=list)


def _clip(text: Any, n: int) -> str:
    text = str(text or "").strip()
    return text if len(text) <= n else text[:n] + " […]"


def gather_context(conn, user_id: str, offer_id: Optional[str], contact_id: Optional[str]) -> Dict[str, str]:
    """Everything the model may use, as short text blocks (only the user's own data)."""
    from src.storage import companies
    values = outreach.placeholder_values(conn, user_id, offer_id, contact_id)
    offer = db.get_offer(conn, user_id, offer_id) if offer_id else None

    recipient = (f"{values['contact_name']}" + (f", {values['their_role']}" if values["their_role"] else "")
                 + (f" at {values['company']}" if values["company"] else "")) if values["contact_name"] else "No specific person."
    offer_text = "No offer selected."
    notes_text = "No notes."
    if offer:
        offer_text = "\n".join(f"{k}: {v}" for k, v in (
            ("Title", offer["title"]), ("Company", offer["company"]), ("Location", offer["location"]),
            ("Skills", ", ".join(offer["skills"][:12])), ("Missions", "; ".join(offer["missions"][:5])),
            ("Summary", _clip(offer["summary"], 400))) if v)
        company = companies.find_company(conn, user_id, offer["company"])
        if company and company["notes"]:
            # pinned / flagged first (already sorted pinned first), then the most recent ones
            ranked = sorted(company["notes"], key=lambda n: not (n["pinned"] or n["flag"]))[:6]
            notes_text = "\n".join(f"- [{n['flag'] or 'note'}{', pinned' if n['pinned'] else ''}] {_clip(n['body'], 300)}"
                                   for n in ranked)

    saved = db.get_profile(conn, user_id)
    p = (saved or {}).get("profile") or {}
    roles = [f"{e.get('role') or e.get('title') or '?'} at {e.get('company') or '?'}" for e in p.get("experience") or []
             if isinstance(e, dict)]
    profile_text = (f"Name: {p.get('full_name') or 'unknown'}\nSummary: {_clip(p.get('summary'), 400)}\n"
                    f"Skills: {', '.join((p.get('skills') or [])[:15])}\nExperience: {'; '.join(roles[:6])}\n"
                    f"CV excerpt: {_clip(p.get('cv_text'), 1500)}") if saved else "No profile: do not mention any experience."
    return {"recipient": recipient, "offer": offer_text, "company_notes": notes_text, "profile": profile_text,
            "instructions": _clip(db.get_instructions(conn, user_id), 800) or "None.", "values": values}


def adapt(user_id: str, body: str, channel: str, offer_id: Optional[str] = None, contact_id: Optional[str] = None,
          extra: str = "", *, connection: Callable = None, structured: Callable = None) -> Dict[str, Any]:
    """Returns {"body", "changes", "missing", "over_limit", "limit"}. Raises ValueError on bad input, LLMError on model failure."""
    from src.llm.port import llm, prompt_version
    from src.utils.prompts import load_prompt
    connection = connection or db.connection
    if channel not in outreach.CHANNELS:
        raise ValueError(f"channel must be one of {', '.join(outreach.CHANNELS)}")
    if not (body or "").strip():
        raise ValueError("Write or pick a message to adapt first")
    limit = outreach.CHANNELS[channel]

    with connection() as conn:
        ctx = gather_context(conn, user_id, offer_id, contact_id)
    filled = outreach.fill(body.strip(), ctx["values"])["body"]

    template = load_prompt("outreach_adapt")
    prompt = template
    for key in ("recipient", "offer", "company_notes", "profile", "instructions"):
        prompt = prompt.replace("{" + key + "}", ctx[key])
    prompt = (prompt.replace("{channel}", CHANNEL_LABELS[channel]).replace("{limit}", str(limit))
              .replace("{extra}", _clip(extra, 500) or "None.")
              .replace("{message}", filled))  # last: the user's text must not be re-substituted
    structured = structured or (lambda p: llm.structured(p, Adapted, role="write", prompt_version=prompt_version(template),
                                                         offer_id=offer_id, temperature=0.4))

    out = structured(prompt)
    if len(out.message) > limit:  # one retry: ask for a shorter version of what it just wrote
        out = structured(f"{prompt}\n\nYour previous answer was {len(out.message)} characters, over the {limit} limit:\n"
                         f"{out.message}\nShorten it to well under {limit} characters, keeping the same content.")
    message = out.message.strip()
    return {"body": message, "changes": [c for c in out.changes if c.strip()][:8],
            "missing": outreach.fill(message, {})["missing"], "over_limit": len(message) > limit, "limit": limit}


if __name__ == "__main__":
    import uuid
    from contextlib import nullcontext
    from src.storage import companies

    U = str(uuid.uuid4())
    with db.temp_schema() as c:
        o = db.insert_offer(c, U, {"title": "Data Engineer", "company": "Acme", "skills": ["dbt", "Airflow"],
                                   "missions": ["Build batch pipelines"]})
        k = db.add_contact(c, U, o["application_id"], {"name": "Sam Lee", "role": "Data lead"})
        db.save_profile(c, U, {"full_name": "Ada L.", "cv_text": "Built dbt models at Beta.", "skills": ["dbt", "SQL"]})
        co = companies.create_company(c, U, {"name": "Acme"})
        companies.add_note(c, U, co["id"], {"body": "Old note about parking"})
        companies.add_note(c, U, co["id"], {"body": "Sam spoke at dbt Coalesce on testing", "flag": "important", "pinned": True})
        db.save_instructions(c, U, "Never use exclamation marks.")

        seen: List[str] = []
        replies = iter([Adapted(message="x" * 320, changes=["too long"]),
                        Adapted(message="Hi Sam, loved your Coalesce talk on dbt testing. I build dbt models at Beta.",
                                changes=["Mentioned his talk", "Linked to dbt work"])])

        def fake(prompt):
            seen.append(prompt)
            return next(replies)

        out = adapt(U, "Hi {first_name}, {hook} I'd like to join {company}.", "linkedin-note", o["id"], k["id"],
                    extra="mention testing", connection=lambda: nullcontext(c), structured=fake)
        p = seen[0]
        assert "Hi Sam, {hook} I'd like to join Acme." in p                 # placeholders filled before the model
        assert p.index("Sam spoke at dbt Coalesce") < p.index("Old note about parking")   # pinned/flagged first
        assert all(s in p for s in ("Built dbt models at Beta.", "Never use exclamation marks.", "mention testing",
                                    "Sam Lee, Data lead at Acme", "Hard limit: 300 characters"))
        assert len(seen) == 2 and "over the 300 limit" in seen[1]          # one retry when too long
        assert out["body"].startswith("Hi Sam, loved") and not out["over_limit"] and out["changes"][0] == "Mentioned his talk"

        # still too long after the retry: returned, but flagged
        out2 = adapt(U, "Hello", "linkedin-note", connection=lambda: nullcontext(c),
                     structured=lambda p: Adapted(message="y" * 350))
        assert out2["over_limit"] and out2["limit"] == 300
        # placeholders the model left are reported; no offer: context says so
        out3 = adapt(U, "Hello", "email", connection=lambda: nullcontext(c),
                     structured=lambda p: (seen.append(p), Adapted(message="Hi {first_name}"))[1])
        assert out3["missing"] == ["first_name"] and "No offer selected." in seen[-1]
        for bad in (lambda: adapt(U, "  ", "email", connection=lambda: nullcontext(c), structured=fake),
                    lambda: adapt(U, "x", "fax", connection=lambda: nullcontext(c), structured=fake)):
            try:
                bad()
                raise AssertionError("expected ValueError")
            except ValueError:
                pass
    print("outreach_writer ok")
