"""
Set up and check a Career Mate instance (one private copy per person).

  uv run python -m src.cli init           create .env, the data folder and the database (safe to re-run)
  uv run python -m src.cli check          show what is configured and what is missing
  uv run python -m src.cli check --live   also send one tiny request to each configured model
  uv run python -m src.cli reindex        embed offers for meaning-based search (otherwise done on first search)
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from contextlib import closing
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
OK, WARN, FAIL = "[ok]", "[..]", "[!!]"


def data_dir(root: Path) -> Path:
    d = Path(os.getenv("DATA_DIR") or "data")
    return d if d.is_absolute() else root / d


def init(root: Path = ROOT) -> list[str]:
    """Idempotent: never overwrites .env or existing data. Returns the actions taken."""
    done = []
    env, example = root / ".env", root / ".env.example"
    if env.exists():
        done.append(f"{OK} .env already exists (left unchanged)")
    else:
        shutil.copyfile(example, env)
        done.append(f"{OK} created .env from .env.example -> add your API keys")
    load_dotenv(env, override=False)

    data = data_dir(root)
    for sub in ("", "cvs"):
        (data / sub).mkdir(parents=True, exist_ok=True)
    done.append(f"{OK} data folder: {data}")

    from src.storage import db  # imported after .env is loaded so DATA_DIR applies
    path = data / "career_mate.db"
    existed = path.exists()
    with closing(db.connect(path)) as conn:  # creates or migrates the schema
        n = conn.execute("SELECT COUNT(*) FROM offers").fetchone()[0]
    done.append(f"{OK} database {'up to date' if existed else 'created'}: {path} ({n} offers)")
    return done


def check(live: bool = False, root: Path = ROOT) -> bool:
    load_dotenv(root / ".env", override=False)
    ok = True

    def line(status: str, msg: str):
        nonlocal ok
        ok = ok and status != FAIL
        print(f"  {status} {msg}")

    print("Environment")
    line(OK if sys.version_info >= (3, 11) else FAIL, f"Python {sys.version.split()[0]} (needs 3.11+)")
    line(OK if (root / ".env").exists() else FAIL, ".env present" if (root / ".env").exists() else ".env missing: run `uv run python -m src.cli init`")
    for tool, why in (("node", "the web UI"), ("npm", "the web UI")):
        line(OK if shutil.which(tool) else WARN, f"{tool} {'found' if shutil.which(tool) else f'not found (needed for {why})'}")
    line(OK if (root / "ui" / "node_modules").exists() else WARN,
         "UI dependencies installed" if (root / "ui" / "node_modules").exists() else "UI dependencies missing: run `npm --prefix ui install`")

    print("Data")
    path = data_dir(root) / "career_mate.db"
    if path.exists():
        from src.storage import db
        with closing(db.connect(path)) as conn:
            n = conn.execute("SELECT COUNT(*) FROM offers").fetchone()[0]
            v = conn.execute("PRAGMA user_version").fetchone()[0]
        line(OK, f"database {path} (schema v{v}, {n} offers)")
        with closing(db.connect(path)) as conn:
            e = conn.execute("SELECT COUNT(*) FROM offer_embeddings").fetchone()[0]
        line(OK if e >= n else WARN, f"{e}/{n} offers embedded for meaning-based search"
             + ("" if e >= n else " (done on the next search, or run `uv run python -m src.cli reindex`)"))
    else:
        line(FAIL, f"no database at {path}: run `uv run python -m src.cli init`")
    profile = data_dir(root) / "profile.json"
    line(OK if profile.exists() else WARN, "CV profile saved" if profile.exists() else "no CV yet (upload one in the Profile tab)")

    print("Models (config/models.toml)")
    from src.llm.port import LLMError, llm
    tested = set()
    for role in ("extract", "write", "route", "chat", "judge", "embed"):
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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create .env, data folder and database")
    c = sub.add_parser("check", help="show configuration status")
    c.add_argument("--live", action="store_true", help="send one tiny request to each configured model")
    sub.add_parser("reindex", help="embed new or changed offers for meaning-based search")
    sub.add_parser("selftest")
    args = ap.parse_args()

    if args.cmd == "init":
        print("\n".join(init()))
        print("\nNext: put your keys in .env, then `uv run python -m src.cli check --live`.")
    elif args.cmd == "check":
        sys.exit(0 if check(args.live) else 1)
    elif args.cmd == "reindex":
        load_dotenv(ROOT / ".env", override=False)
        from src.storage import db
        from src.storage.offer_search import ensure_embeddings
        with closing(db.connect(data_dir(ROOT) / "career_mate.db")) as conn:
            print(f"{OK} {ensure_embeddings(conn)} offer(s) embedded (unchanged ones are skipped)")
    else:
        _selftest()


def _selftest() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / ".env.example").write_text("DATA_DIR=mydata\n", encoding="utf-8")
        os.environ.pop("DATA_DIR", None)
        first = init(root)
        assert (root / ".env").read_text(encoding="utf-8") == "DATA_DIR=mydata\n"
        assert (root / "mydata" / "career_mate.db").exists() and (root / "mydata" / "cvs").is_dir()
        assert "created .env" in first[0] and "created" in first[2], first
        (root / ".env").write_text("DATA_DIR=mydata\nHF_TOKEN=mine\n", encoding="utf-8")
        second = init(root)  # re-run: keeps .env and data
        assert "HF_TOKEN=mine" in (root / ".env").read_text(encoding="utf-8")
        assert "left unchanged" in second[0] and "up to date" in second[2], second
        os.environ.pop("DATA_DIR", None)
    print("cli ok")


if __name__ == "__main__":
    main()
