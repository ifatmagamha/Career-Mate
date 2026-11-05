# src/agents/query_interpreter.py
"""
Natural-language search -> a search plan: the topic words for hybrid search + structured filters.

The plan's schema is built at run time from what exists (ENUM_FILTERS, your folders, the sort options),
so the model can only answer with real values, and a new filterable field needs no change here.
Anything that is not a filter (role, skills, location, company) stays in `q` for hybrid search.
"""
from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, create_model

from src.storage import db

# Optional meanings for values, so "CDI", "stage" or "télétravail" map to the right one.
# A value without a hint still works; it is just matched on its own name.
VALUE_HINTS = {
    "permanent": "CDI, permanent contract", "fixed_term": "CDD, fixed-term", "internship": "stage, internship",
    "apprenticeship": "alternance, apprenticeship", "freelance": "freelance, contractor", "part_time": "temps partiel",
    "onsite": "on site, présentiel, no remote", "hybrid": "hybride, partly remote", "remote": "full remote, télétravail",
    "saved": "captured but not acted on", "to_apply": "planned, à postuler", "applied": "already applied, candidaté",
    "interview": "interviewing, entretien", "offer": "received an offer", "accepted": "accepted",
    "rejected": "rejected, refusé", "archived": "archived",
}
SORT_HINTS = {"deadline": "soonest deadline first", "recent": "newest first", "updated": "recently changed",
              "title": "by job title", "company": "by company name"}

PROMPT = """You turn a job-offer search request into a search plan (JSON).
Today is {today}.

Filters you may set (omit any the request does not ask for):
{fields}

Rules:
- "q": only the words that describe what the offers are about and are not covered by a filter
  (role, skills, domain, location, company...). Keep the user's language. Empty if nothing is left.
- A filter is set only when the request clearly asks for it. Do not guess.
- "deadline_before": a date YYYY-MM-DD; resolve relative dates ("this month", "before Christmas") from today.
- "sort": only if the request asks for an order.

Request: {text}
"""


def _schema(conn, user_id: str) -> Dict[str, Tuple[str, ...]]:
    """Every field the plan may set, with its allowed values ('' = free text)."""
    fields: Dict[str, Tuple[str, ...]] = {k: values for k, (_, values) in db.ENUM_FILTERS.items()}
    folders = tuple(f["name"] for f in db.list_folders(conn, user_id))
    if folders:
        fields["folder"] = folders
    fields["sort"] = tuple(s for s in db.SORTS if s != "relevance")
    return fields


def _plan_model(fields: Dict[str, Tuple[str, ...]]) -> type[BaseModel]:
    spec: Dict[str, Any] = {"q": (str, Field(default="", description="topic words for search"))}
    for name, values in fields.items():
        spec[name] = (Optional[Literal[values]], None)  # type: ignore[valid-type]
    spec["deadline_before"] = (Optional[str], Field(default=None, description="YYYY-MM-DD"))
    return create_model("SearchPlan", **spec)


def _describe(fields: Dict[str, Tuple[str, ...]]) -> str:
    lines = []
    for name, values in fields.items():
        hints = SORT_HINTS if name == "sort" else VALUE_HINTS
        shown = ", ".join(f'"{v}"' + (f" ({hints[v]})" if v in hints else "") for v in values)
        lines.append(f"- {name}: one of {shown}")
    lines.append("- deadline_before: application deadline on or before this date")
    return "\n".join(lines)


def _default_structured(prompt: str, schema: type[BaseModel]) -> BaseModel:
    from src.llm.port import llm, prompt_version
    return llm.structured(prompt, schema, role="query", prompt_version=prompt_version(PROMPT))


@lru_cache(maxsize=128)
def _cached(text: str, fields_json: str, today: str, structured: Callable) -> str:
    fields = {k: tuple(v) for k, v in json.loads(fields_json).items()}
    prompt = PROMPT.format(today=today, fields=_describe(fields), text=text)
    return structured(prompt, _plan_model(fields)).model_dump_json()


def interpret(conn, user_id: str, text: str, *, today: Optional[date] = None,
              structured: Callable = _default_structured) -> Dict[str, Any]:
    """Returns {"q", "filters": {field: [value]}, "folder_id", "deadline_before", "sort", "applied": [labels]}."""
    fields = _schema(conn, user_id)
    raw = json.loads(_cached(text.strip(), json.dumps(fields), (today or date.today()).isoformat(), structured))

    filters = {k: [raw[k]] for k in db.ENUM_FILTERS if raw.get(k)}
    folder_id = None
    if raw.get("folder"):
        folder_id = next((f["id"] for f in db.list_folders(conn, user_id) if f["name"].casefold() == raw["folder"].casefold()), None)
    deadline = raw.get("deadline_before")
    try:
        deadline = date.fromisoformat(deadline).isoformat() if deadline else None
    except ValueError:
        deadline = None  # unusable date: ignore rather than fail the search
    sort = raw.get("sort") or None

    applied: List[str] = [f"{k.replace('_', ' ')}: {v[0]}" for k, v in filters.items()]
    if folder_id:
        applied.append(f"folder: {raw['folder']}")
    if deadline:
        applied.append(f"deadline before {deadline}")
    if sort:
        applied.append(f"sorted by {sort}")
    return {"q": (raw.get("q") or "").strip(), "filters": filters, "folder_id": folder_id,
            "deadline_before": deadline, "sort": sort, "applied": applied}


if __name__ == "__main__":
    import uuid

    U = str(uuid.uuid4())
    seen = {}

    def fake(prompt, schema):
        seen["prompt"], seen["fields"] = prompt, set(schema.model_fields)
        return schema.model_validate({"q": "data", "contract_type": "internship", "remote_policy": "remote",
                                      "folder": "Data roles", "deadline_before": "2026-11-30", "sort": "deadline"})

    with db.temp_schema() as c:
        db.create_folder(c, U, "Data roles")
        plan = interpret(c, U, "remote data internships in my Data roles folder, closing this month, soonest first",
                         today=date(2026, 11, 4), structured=fake)
        assert plan["q"] == "data" and plan["filters"] == {"contract_type": ["internship"], "remote_policy": ["remote"]}
        assert plan["folder_id"] and plan["deadline_before"] == "2026-11-30" and plan["sort"] == "deadline"
        assert "folder: Data roles" in plan["applied"] and "Today is 2026-11-04" in seen["prompt"]
        # the schema is built from the registry + real folders: a new ENUM_FILTERS entry appears automatically
        assert {"status", "contract_type", "remote_policy", "folder", "sort", "deadline_before", "q"} <= seen["fields"]
        assert '"internship" (stage, internship)' in seen["prompt"]

        # invalid values never reach the search: the schema rejects them
        Plan = _plan_model(_schema(c, U))
        try:
            Plan.model_validate({"contract_type": "CDI"})
            raise AssertionError("expected a validation error")
        except ValueError:
            pass

        def bad_date(prompt, schema):
            return schema.model_validate({"q": "x", "deadline_before": "end of month"})
        _cached.cache_clear()
        assert interpret(c, U, "x", structured=bad_date)["deadline_before"] is None  # unusable date dropped

        calls = []

        def counting(prompt, schema):
            calls.append(1)
            return schema.model_validate({"q": "sales"})
        _cached.cache_clear()
        interpret(c, U, "sales jobs", structured=counting)
        interpret(c, U, "sales jobs", structured=counting)
        assert len(calls) == 1  # same request, same schema, same day: answered from cache
    print("query_interpreter ok")
