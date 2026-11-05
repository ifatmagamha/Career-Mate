# src/storage/offer_search.py
"""
Hybrid offer search: keyword (Postgres full-text, ts_rank) + semantic (pgvector cosine), merged with
Reciprocal Rank Fusion. Filters (status, folder, contract...) apply before ranking.

- No search field is hardcoded: the embedded text is built from every text field an offer has.
- Embeddings are derived data: computed lazily before a semantic search, for offers that are new,
  edited, or were embedded with another model. Saving an offer never depends on the embedding API.
- If embeddings are unavailable (quota, missing key), search falls back to keyword-only.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from src.config.logging import logger
from src.storage import db

Embed = Callable[[List[str]], List[List[float]]]

RRF_K = 60              # standard RRF constant: dampens the weight of top ranks
DENSE_TOP_K = 20        # semantic candidates considered per query
MIN_SIMILARITY = 0.45     # fallbacks; the real values live in [roles.embed] of config/models.toml
SIMILARITY_MARGIN = 0.05
MAX_EMBED_CHARS = 6000  # ~1.5k tokens: within embedding model input limits
EMBED_BATCH = 50
MODES = ("hybrid", "keyword", "semantic")

# Never part of the searchable text: ids, provenance, bookkeeping
_NOT_TEXT = {"id", "url", "source", "model", "prompt_version", "match_score", "created_at", "updated_at",
             "application_id", "status", "next_action", "next_action_at", "applied_at", "folder_id",
             "notes", "contacts_count", "deadline"}
# Most informative fields first (the text is truncated); any other text field follows automatically
_FIRST = ("title", "company", "location", "contract_type", "remote_policy", "seniority", "summary",
          "skills", "nice_to_have", "missions", "requirements")


def offer_text(offer: Dict[str, Any]) -> str:
    """Everything searchable about an offer, as one text (field names included so 'remote' etc. mean something)."""
    keys = [k for k in _FIRST if k in offer] + sorted(k for k in offer if k not in _FIRST and k not in _NOT_TEXT)
    parts = []
    for k in keys:
        v = offer.get(k)
        if isinstance(v, list):
            v = ", ".join(str(x) for x in v if x)
        if v and v != "unknown" and isinstance(v, str):
            parts.append(f"{k.replace('_', ' ')}: {v}")
    return "\n".join(parts)[:MAX_EMBED_CHARS]


def _hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _default_embed(texts: List[str]) -> List[List[float]]:
    from src.llm.port import llm
    return llm.embed(texts)


def _embed_model() -> str:
    from src.llm.port import llm
    return llm.config("embed").model


def _thresholds() -> Tuple[float, Optional[float]]:
    """(floor, margin), set next to the embedding model they were measured for (config/models.toml, [roles.embed])."""
    import tomllib
    from src.llm.port import CONFIG_PATH
    try:
        embed = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))["roles"]["embed"]
        margin = embed.get("similarity_margin", SIMILARITY_MARGIN)
        return float(embed.get("min_similarity", MIN_SIMILARITY)), None if margin is None else float(margin)
    except (OSError, KeyError, ValueError):
        return MIN_SIMILARITY, SIMILARITY_MARGIN


def _vec(v: Sequence[float]) -> str:
    """pgvector's text format: '[1.0,2.0]'."""
    return "[" + ",".join(str(float(x)) for x in v) + "]"


def ensure_embeddings(conn, user_id: str, *, embed: Embed = _default_embed, model: Optional[str] = None) -> int:
    """Embed the user's offers that are new, edited, or embedded with another model. Returns how many were (re)embedded."""
    model = model or _embed_model()
    stored = {r["offer_id"]: (r["model"], r["text_hash"])
              for r in conn.execute("SELECT offer_id, model, text_hash FROM offer_embeddings WHERE user_id = %s", (user_id,))}
    todo = []
    for offer in db.list_offers(conn, user_id):
        text = offer_text(offer)
        if stored.get(offer["id"]) != (model, _hash(text)):
            todo.append((offer["id"], text))
    for i in range(0, len(todo), EMBED_BATCH):
        batch = todo[i : i + EMBED_BATCH]
        vectors = embed([t for _, t in batch])
        with conn.transaction(), conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO offer_embeddings (offer_id, user_id, model, text_hash, embedding) VALUES (%s, %s, %s, %s, %s::vector) "
                "ON CONFLICT (offer_id) DO UPDATE SET model = EXCLUDED.model, text_hash = EXCLUDED.text_hash, "
                "embedding = EXCLUDED.embedding, updated_at = now()",
                [(oid, user_id, model, _hash(t), _vec(v)) for (oid, t), v in zip(batch, vectors)],
            )
    if todo:
        logger.info(f"[search] embedded {len(todo)} offer(s) with {model}")
    return len(todo)


@lru_cache(maxsize=256)
def _query_vector(model: str, q: str, embed: Embed) -> Tuple[float, ...]:
    return tuple(embed([q])[0])


def semantic_ranking(conn, user_id: str, q: str, ids: Sequence[str], *, embed: Embed, model: str,
                     min_similarity: Optional[float] = None, margin: Optional[float] = None) -> List[Tuple[str, float]]:
    """(offer_id, cosine) for the given offers, best first, at most DENSE_TOP_K.

    Kept: cosine >= min_similarity (absolute floor) and, if margin is set, cosine >= best - margin.
    Absolute cosines shift with the query (short queries score lower overall), while the ranking holds,
    so the relative margin is what separates related from unrelated; the floor stops nonsense queries.
    """
    floor = MIN_SIMILARITY if min_similarity is None else min_similarity
    if not ids:
        return []
    # <=> is pgvector's cosine distance; similarity = 1 - distance. Exact scan: fast at personal scale.
    # ponytail: no ANN index (HNSW needs a fixed dimension); add one per model if offers reach ~100k.
    rows = conn.execute(
        "SELECT offer_id, 1 - (embedding <=> %(q)s::vector) AS sim FROM offer_embeddings "
        "WHERE user_id = %(uid)s AND model = %(model)s AND offer_id = ANY(%(ids)s::uuid[]) "
        "ORDER BY embedding <=> %(q)s::vector LIMIT %(k)s",
        {"q": _vec(_query_vector(model, q, embed)), "uid": user_id, "model": model, "ids": list(ids), "k": DENSE_TOP_K},
    ).fetchall()
    if not rows:
        return []
    cut = max(floor, rows[0]["sim"] - margin) if margin is not None else floor
    return [(r["offer_id"], r["sim"]) for r in rows if r["sim"] >= cut]


def rrf(*rankings: Sequence[str], k: int = RRF_K) -> Dict[str, float]:
    """Reciprocal Rank Fusion: score(d) = sum over rankings of 1 / (k + rank). Robust to incomparable raw scores."""
    scores: Dict[str, float] = {}
    for ranking in rankings:
        for rank, doc in enumerate(ranking, start=1):
            scores[doc] = scores.get(doc, 0.0) + 1.0 / (k + rank)
    return scores


def search_offers(conn, user_id: str, filters: Dict[str, Any], *, mode: str = "hybrid",
                  embed: Embed = _default_embed, model: Optional[str] = None) -> Tuple[List[Dict[str, Any]], str]:
    """Returns (offers, mode actually used). Without a query, this is plain filtering/sorting."""
    q = (filters.get("q") or "").strip()
    if not q or mode == "keyword":
        return db.query_offers(conn, user_id, filters), "keyword" if q else "none"
    if mode not in MODES:
        raise ValueError(f"Unknown search mode: {mode}")

    # Everything that passes the filters, in the requested order (used for explicit sorts and as the candidate set)
    explicit_sort = filters.get("sort") not in (None, "", "relevance")
    candidates = db.query_offers(conn, user_id, {**filters, "q": None, "sort": filters.get("sort") if explicit_sort else None})
    by_id = {o["id"]: o for o in candidates}
    keyword_ids = [o["id"] for o in db.query_offers(conn, user_id, {**filters, "sort": "relevance"})] if mode == "hybrid" else []

    try:
        model = model or _embed_model()
        floor, margin = _thresholds()
        with conn.transaction():  # a DB error here rolls back to this point, so the keyword fallback still runs
            ensure_embeddings(conn, user_id, embed=embed, model=model)
            dense_ids = [oid for oid, _ in semantic_ranking(conn, user_id, q, list(by_id), embed=embed, model=model,
                                                             min_similarity=floor, margin=margin)]
    except Exception as e:  # quota, missing key, provider down: keyword search still works
        logger.warning(f"[search] semantic search unavailable, keyword only: {str(e)[:200]}")
        return db.query_offers(conn, user_id, filters), "keyword (semantic unavailable)"

    scores = rrf(keyword_ids, dense_ids)
    if explicit_sort:
        return [o for o in candidates if o["id"] in scores], mode
    return [by_id[i] for i in sorted(scores, key=lambda i: -scores[i]) if i in by_id], mode


def _selftest() -> None:
    import uuid

    # rrf: an item ranked well in both lists beats one ranked first in a single list
    s = rrf(["a", "b", "c"], ["b", "d"])
    assert max(s, key=s.get) == "b" and s["a"] > s["d"]

    t = offer_text({"id": "x", "title": "Data Engineer", "company": "Acme", "contract_type": "unknown",
                    "skills": ["SQL", "dbt"], "notes": "private", "benefits": "Remote budget"})
    assert t.startswith("title: Data Engineer\ncompany: Acme\nskills: SQL, dbt") and "unknown" not in t
    assert "private" not in t and "benefits: Remote budget" in t  # unknown fields included, private notes excluded

    # Fake embedding: one dimension per topic word, so similarity is predictable
    topics = ["data", "sales", "design", "machine"]
    calls = []

    def fake_embed(texts):
        calls.append(len(texts))
        return [[float(t.lower().count(w)) + 0.01 for w in topics] for t in texts]

    def broken(texts):
        raise RuntimeError("quota")

    U, V = str(uuid.uuid4()), str(uuid.uuid4())
    with db.temp_schema() as c:
        a = db.insert_offer(c, U, {"title": "Data Engineer", "summary": "data pipelines and data quality"})
        b = db.insert_offer(c, U, {"title": "Account Executive", "summary": "sales sales pipeline"})
        db.insert_offer(c, U, {"title": "Product Designer", "summary": "design systems"}, status="applied")

        assert ensure_embeddings(c, U, embed=fake_embed, model="fake") == 3 and calls == [3]
        assert ensure_embeddings(c, U, embed=fake_embed, model="fake") == 0             # nothing changed
        db.update_offer(c, U, b["id"], {"summary": "sales and data reporting"})
        assert ensure_embeddings(c, U, embed=fake_embed, model="fake") == 1             # only the edited offer
        assert ensure_embeddings(c, U, embed=fake_embed, model="fake-v2") == 3          # model change: all

        _query_vector.cache_clear()
        res, mode = search_offers(c, U, {"q": "datas"}, embed=fake_embed, model="fake-v2")
        assert mode == "hybrid" and res[0]["id"] == a["id"], [o["title"] for o in res]  # semantic finds what keyword misses
        assert "Product Designer" not in [o["title"] for o in res]                       # unrelated: below MIN_SIMILARITY

        res, _ = search_offers(c, U, {"q": "datas", "status": ["applied"]}, embed=fake_embed, model="fake-v2")
        assert res == []                                                                  # filters still apply

        res, mode = search_offers(c, U, {"q": "pipeline"}, mode="keyword", embed=fake_embed, model="fake-v2")
        assert mode == "keyword" and [o["title"] for o in res] == ["Data Engineer"]  # prefix: "pipeline" matches "pipelines"

        _query_vector.cache_clear()
        res, mode = search_offers(c, U, {"q": "designer"}, embed=broken, model="fake-v3")
        assert mode.startswith("keyword") and [o["title"] for o in res] == ["Product Designer"]  # graceful fallback

        res, mode = search_offers(c, U, {"status": ["applied"]}, embed=broken)
        assert mode == "none" and len(res) == 1                                           # no query: no embedding call
        # another user's offers are never embedded or returned
        db.insert_offer(c, V, {"title": "Data Analyst", "summary": "data data data"})
        res, _ = search_offers(c, U, {"q": "data"}, embed=fake_embed, model="fake-v2")
        assert "Data Analyst" not in [o["title"] for o in res]
        assert c.execute("SELECT count(*) AS n FROM offer_embeddings WHERE user_id = %s", (V,)).fetchone()["n"] == 0
    print("offer_search ok")


if __name__ == "__main__":
    _selftest()
