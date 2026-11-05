"""
Set up and check a Career Mate instance.

  uv run python -m src.cli init           create .env (if missing) and the database schema (safe to re-run)
  uv run python -m src.cli migrate        apply pending database migrations (the container does this on start)
  uv run python -m src.cli check          show what is configured and what is missing
  uv run python -m src.cli check --live   also send one tiny request to each configured model
  uv run python -m src.cli reindex        embed offers for meaning-based search (otherwise done on first search)
  uv run python -m src.cli import-sqlite --user <uuid>
                                          copy a pre-PostgreSQL data/career_mate.db (+ data/profile.json) to a user
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
OK, WARN, FAIL = "[ok]", "[..]", "[!!]"


def init(root: Path = ROOT) -> list[str]:
    """Idempotent: never overwrites .env. Returns the actions taken."""
    done = []
    env, example = root / ".env", root / ".env.example"
    if env.exists():
        done.append(f"{OK} .env already exists (left unchanged)")
    else:
        shutil.copyfile(example, env)
        done.append(f"{OK} created .env from .env.example -> set DATABASE_URL and your API keys")
    load_dotenv(env, override=False)

    from src.storage import db  # imported after .env is loaded so DATABASE_URL applies
    from src.config.settings import settings
    if not settings.DATABASE_URL:
        done.append(f"{FAIL} DATABASE_URL is empty: start Postgres (`docker compose up -d db`) and set it in .env")
        return done
    with db.connect() as conn:
        applied = db.migrate(conn)
    done.append(f"{OK} database schema '{settings.DB_SCHEMA}': " + (f"applied {', '.join(applied)}" if applied else "up to date"))
    return done


def check(live: bool = False, root: Path = ROOT) -> bool:
    load_dotenv(root / ".env", override=False)
    from src.config.settings import settings
    ok = True

    def line(status: str, msg: str):
        nonlocal ok
        ok = ok and status != FAIL
        print(f"  {status} {msg}")

    print("Environment")
    line(OK if sys.version_info >= (3, 11) else FAIL, f"Python {sys.version.split()[0]} (needs 3.11+)")
    line(OK if (root / ".env").exists() else WARN, ".env present" if (root / ".env").exists() else ".env missing (fine if variables come from the host)")
    line(OK, f"APP_ENV={settings.APP_ENV}, CORS_ORIGINS={settings.CORS_ORIGINS}")

    print("Auth (Supabase)")
    if settings.SUPABASE_URL:
        line(OK, f"tokens verified against {settings.SUPABASE_URL}" + (" (+ legacy HS256 secret)" if settings.SUPABASE_JWT_SECRET else ""))
    else:
        line(FAIL if settings.APP_ENV == "production" else WARN,
             "SUPABASE_URL not set: no login, every request is the local dev user" + (" - not allowed in production" if settings.APP_ENV == "production" else ""))

    print("Database")
    if not settings.DATABASE_URL:
        line(FAIL, "DATABASE_URL not set")
    else:
        from src.storage import db
        try:
            with db.connect() as conn:
                version = conn.execute("SHOW server_version").fetchone()["server_version"]
                exists = conn.execute("SELECT to_regclass('schema_migrations') IS NOT NULL AS e").fetchone()["e"]
                done = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations")} if exists else set()
                pending = [p.name for p in sorted(db.MIGRATIONS_DIR.glob("*.sql")) if p.name not in done]
                line(OK, f"PostgreSQL {version}, schema '{settings.DB_SCHEMA}'")
                line(FAIL if pending else OK, f"pending migrations: {', '.join(pending)} (run `uv run python -m src.cli migrate`)"
                     if pending else "migrations up to date")
                if not pending:
                    n = conn.execute("SELECT count(*) AS n FROM offers").fetchone()["n"]
                    e = conn.execute("SELECT count(*) AS n FROM offer_embeddings").fetchone()["n"]
                    users = conn.execute("SELECT count(DISTINCT user_id) AS n FROM offers").fetchone()["n"]
                    line(OK, f"{n} offers from {users} user(s); {e} embedded for meaning-based search")
        except Exception as e:
            line(FAIL, f"cannot connect: {str(e).splitlines()[0][:160]}")

    print("Models (config/models.toml)")
    import tomllib
    from src.llm.port import CONFIG_PATH, LLMError, llm
    tested = set()
    for role in tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))["roles"]:  # every role the config defines
        try:
            cfg = llm.config(role)
        except LLMError as e:
            line(FAIL, f"{role:<8} {e}")
            continue
        status, note = OK, ""
        if live and (cfg.provider, cfg.model) not in tested:
            tested.add((cfg.provider, cfg.model))
            try:
                if role == "embed":
                    llm.embed(["ok"], role=role)
                else:
                    llm.complete("Reply with: ok", role=role)
                note = " - answered"
            except LLMError as e:
                status, note = FAIL, f" - {str(e)[:120]}"
        line(status, f"{role:<8} {cfg.provider} / {cfg.model}{note}")
    if not live:
        print(f"  {WARN} keys are only checked for presence; add --live to send one tiny request per model")
    return ok


def import_sqlite(conn, user_id: str, sqlite_path: Path, profile_path: Path | None = None,
                  cv_dir: Path | None = None) -> dict:
    """Copy offers (+ status, folder, notes, contacts), folders, views and the CV profile from the old SQLite file.
    Offers whose URL the user already has are skipped, so re-running is safe."""
    from src.storage import db
    src = sqlite3.connect(sqlite_path)
    src.row_factory = sqlite3.Row
    counts = {"offers": 0, "skipped": 0, "folders": 0, "contacts": 0, "views": 0, "profile": 0}
    try:
        folders = {}
        mine = {f["name"].casefold(): f["id"] for f in db.list_folders(conn, user_id)}
        for f in src.execute("SELECT * FROM folders"):
            if f["name"].casefold() not in mine:
                mine[f["name"].casefold()] = db.create_folder(conn, user_id, f["name"])["id"]
                counts["folders"] += 1
            folders[f["id"]] = mine[f["name"].casefold()]

        rows = src.execute("SELECT o.*, a.id AS app_id, a.status AS app_status, a.folder_id AS app_folder, "
                           "a.notes AS app_notes FROM offers o JOIN applications a ON a.offer_id = o.id").fetchall()
        for o in rows:
            if o["url"] and db.find_offer_by_url(conn, user_id, o["url"]):
                counts["skipped"] += 1
                continue
            data = {k: o[k] for k in o.keys() if k != "id"}  # new ids: the old ones may exist for another user
            for f in ("skills", "nice_to_have", "missions", "requirements"):
                data[f] = json.loads(data.get(f) or "[]")
            new = db.insert_offer(conn, user_id, data, status=o["app_status"], actor="automation")
            app = new["application_id"]
            if o["app_folder"] in folders:
                db.set_folder(conn, user_id, app, folders[o["app_folder"]], actor="automation")
            if o["app_notes"]:
                db.set_notes(conn, user_id, app, o["app_notes"])
            for c in src.execute("SELECT * FROM contacts WHERE application_id = ?", (o["app_id"],)):
                db.add_contact(conn, user_id, app, dict(c))
                counts["contacts"] += 1
            counts["offers"] += 1

        for v in src.execute("SELECT * FROM views"):
            try:
                db.save_view(conn, user_id, v["name"], json.loads(v["filters"]), v["layout"])
                counts["views"] += 1
            except db.IntegrityError:  # same name already there
                pass
    finally:
        src.close()

    if profile_path and profile_path.exists():
        saved = json.loads(profile_path.read_text(encoding="utf-8"))
        name = saved.get("source_file")
        cv = (cv_dir / name) if cv_dir and name else None
        content = cv.read_bytes() if cv and cv.exists() else None
        db.save_profile(conn, user_id, saved["profile"], source_file=name, cv_file=content,
                        cv_mime=("application/pdf" if name.lower().endswith(".pdf") else "text/plain") if content else None)
        counts["profile"] = 1
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create .env and the database schema")
    sub.add_parser("migrate", help="apply pending database migrations")
    c = sub.add_parser("check", help="show configuration status")
    c.add_argument("--live", action="store_true", help="send one tiny request to each configured model")
    sub.add_parser("reindex", help="embed new or changed offers for meaning-based search")
    i = sub.add_parser("import-sqlite", help="copy an old SQLite database to a user")
    i.add_argument("--user", required=True, help="the user's id (Supabase: Authentication > Users; local dev: "
                                                 "00000000-0000-0000-0000-000000000001)")
    i.add_argument("--db", type=Path, default=ROOT / "data" / "career_mate.db")
    i.add_argument("--profile", type=Path, default=ROOT / "data" / "profile.json")
    sub.add_parser("selftest")
    args = ap.parse_args()

    if args.cmd == "init":
        print("\n".join(init()))
        print("\nNext: put your keys in .env, then `uv run python -m src.cli check --live`.")
        return
    if args.cmd == "check":
        sys.exit(0 if check(args.live) else 1)
    if args.cmd == "selftest":
        return _selftest()

    load_dotenv(ROOT / ".env", override=False)
    from src.storage import db
    with db.connect() as conn:  # the with block commits on success
        if args.cmd == "migrate":
            applied = db.migrate(conn)
            print(f"{OK} " + (f"applied {', '.join(applied)}" if applied else "schema up to date"))
        elif args.cmd == "reindex":
            from src.storage.offer_search import ensure_embeddings
            users = [r["user_id"] for r in conn.execute("SELECT DISTINCT user_id FROM offers")]
            n = sum(ensure_embeddings(conn, u) for u in users)
            print(f"{OK} {n} offer(s) embedded for {len(users)} user(s) (unchanged ones are skipped)")
        elif args.cmd == "import-sqlite":
            if not db._id(args.user):
                sys.exit(f"{FAIL} --user must be a uuid")
            counts = import_sqlite(conn, db._id(args.user), args.db, args.profile, args.profile.parent / "cvs")
            print(f"{OK} imported: " + ", ".join(f"{v} {k}" for k, v in counts.items()))


def _selftest() -> None:
    import os
    import tempfile
    import uuid

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / ".env.example").write_text("HF_TOKEN=\n", encoding="utf-8")
        init(root)
        assert (root / ".env").read_text(encoding="utf-8") == "HF_TOKEN=\n"
        (root / ".env").write_text("HF_TOKEN=mine\n", encoding="utf-8")
        assert "left unchanged" in init(root)[0]  # re-run keeps .env
        assert "HF_TOKEN=mine" in (root / ".env").read_text(encoding="utf-8")
        os.environ.pop("HF_TOKEN", None)

        # import from a small database in the old SQLite format
        old = root / "old.db"
        s = sqlite3.connect(old)
        s.executescript("""
            CREATE TABLE offers (id TEXT, url TEXT, title TEXT, company TEXT, location TEXT, remote_policy TEXT,
                contract_type TEXT, seniority TEXT, salary TEXT, deadline TEXT, skills TEXT, nice_to_have TEXT,
                missions TEXT, requirements TEXT, summary TEXT, raw_text TEXT, source TEXT, model TEXT,
                prompt_version TEXT, match_score INTEGER, created_at TEXT, updated_at TEXT);
            CREATE TABLE applications (id TEXT, offer_id TEXT, status TEXT, folder_id TEXT, notes TEXT);
            CREATE TABLE folders (id TEXT, name TEXT, created_at TEXT);
            CREATE TABLE contacts (id TEXT, application_id TEXT, name TEXT, role TEXT, linkedin_url TEXT, notes TEXT,
                reached_out INTEGER, reached_at TEXT, created_at TEXT, updated_at TEXT);
            CREATE TABLE views (id TEXT, name TEXT, filters TEXT, layout TEXT, created_at TEXT);
            INSERT INTO offers (id, url, title, skills, deadline, created_at, updated_at)
                VALUES ('o1', 'https://x/1', 'Data Eng', '["SQL"]', '2026-12-01', '2025-01-02T03:04:05+00:00', '2025-01-02T03:04:05+00:00');
            INSERT INTO applications VALUES ('a1', 'o1', 'applied', 'f1', 'call back');
            INSERT INTO folders VALUES ('f1', 'Data', '2025-01-01');
            INSERT INTO contacts (id, application_id, name, role) VALUES ('c1', 'a1', 'Sam', 'Recruiter');
            INSERT INTO views VALUES ('v1', 'Applied', '{"status": ["applied"]}', 'table', '2025-01-01');
        """)
        s.commit()
        s.close()
        (root / "profile.json").write_text(json.dumps({"source_file": "cv.pdf", "profile": {"full_name": "Ada"}}), encoding="utf-8")
        (root / "cvs").mkdir()
        (root / "cvs" / "cv.pdf").write_bytes(b"%PDF")

        from src.storage import db
        U = str(uuid.uuid4())
        with db.temp_schema() as conn:
            counts = import_sqlite(conn, U, old, root / "profile.json", root / "cvs")
            assert counts == {"offers": 1, "skipped": 0, "folders": 1, "contacts": 1, "views": 1, "profile": 1}, counts
            o = db.find_offer_by_url(conn, U, "https://x/1")
            assert (o["status"], o["notes"], o["skills"], o["deadline"]) == ("applied", "call back", ["SQL"], "2026-12-01"), o
            assert o["created_at"].startswith("2025-01-02") and o["folder_id"] == db.list_folders(conn, U)[0]["id"]
            assert db.get_cv_file(conn, U)["cv_file"] == b"%PDF"
            again = import_sqlite(conn, U, old)  # re-run: nothing duplicated
            assert again["offers"] == 0 and again["skipped"] == 1 and again["folders"] == 0 and again["views"] == 0, again
    print("cli ok")


if __name__ == "__main__":
    main()
