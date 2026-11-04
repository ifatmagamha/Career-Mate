"""
Measure the natural-language query interpreter on labeled requests (role "query" in config/models.toml).

  uv run python scripts/measure_query.py
Uses a throwaway database (your data is not touched); one model call per request.
Re-run after changing the query model or the interpreter prompt.
"""
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, ".")
from src.agents.query_interpreter import interpret  # noqa: E402
from src.storage import db  # noqa: E402

TODAY = date(2026, 11, 4)
# expected filters (field -> allowed answers), words that must appear in q, words that must not
CASES = [
    ("remote data internships", {"contract_type": {"internship"}, "remote_policy": {"remote"}}, ["data"], ["remote", "intern"]),
    ("offres en CDI à Paris", {"contract_type": {"permanent"}}, ["paris"], ["cdi"]),
    ("offers I already applied to", {"status": {"applied"}}, [], ["applied"]),
    ("hybrid machine learning jobs, soonest deadline first", {"remote_policy": {"hybrid"}, "sort": {"deadline"}},
     ["machine learning"], ["hybrid"]),
    ("alternance data analyst", {"contract_type": {"apprenticeship"}}, ["data analyst"], ["alternance"]),
    ("jobs in my Data roles folder closing before the end of November", {"folder": {"Data roles"},
     "deadline_before": {"2026-11-30"}}, [], ["folder"]),
    ("postes en télétravail chez Doctolib", {"remote_policy": {"remote"}}, ["doctolib"], ["télétravail"]),
    ("offers where I have an interview", {"status": {"interview"}}, [], ["interview"]),
    ("python developer", {}, ["python"], []),
    ("CDD ou stage en marketing", {"contract_type": {"fixed_term", "internship"}}, ["marketing"], ["cdd", "stage"]),
]

with tempfile.TemporaryDirectory() as d:
    conn = db.connect(Path(d) / "q.db")
    folder_id = db.create_folder(conn, "Data roles")["id"]
    exact, tp, fp, fn, q_ok, latencies = 0, 0, 0, 0, 0, []
    for text, expected, must, must_not in CASES:
        t0 = time.monotonic()
        plan = interpret(conn, text, today=TODAY)
        latencies.append(time.monotonic() - t0)
        got = {k: v[0] for k, v in plan["filters"].items()}
        if plan["folder_id"]:
            got["folder"] = "Data roles" if plan["folder_id"] == folder_id else "?"
        if plan["deadline_before"]:
            got["deadline_before"] = plan["deadline_before"]
        if plan["sort"]:
            got["sort"] = plan["sort"]
        right = {k for k, v in got.items() if v in expected.get(k, set())}
        tp += len(right)
        fp += len(set(got) - right)
        fn += len(set(expected) - right)
        q = plan["q"].lower()
        q_good = all(w in q for w in must) and not any(w in q for w in must_not)
        q_ok += q_good
        ok = right == set(expected) and len(got) == len(expected) and q_good
        exact += ok
        print(f"{'OK ' if ok else 'ERR'} {text!r:<70} -> q={plan['q']!r} {got}")
    conn.close()

n = len(CASES)
print(f"\nfully correct {exact}/{n} | filters precision {tp / max(tp + fp, 1):.2f} recall {tp / max(tp + fn, 1):.2f}"
      f" | q correct {q_ok}/{n} | latency median {sorted(latencies)[n // 2]:.1f}s")
