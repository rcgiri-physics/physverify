"""Mutation score of the benchmark specs: does each problem's spec fail when its solver is changed?

    python -m pvbench.mutation results/mutation

Next to the seeded bugs (pvbench.matrix), this runs `physverify mutate` on the code under test of each
problem: only the functions named in TARGETS are changed, never the reference code in the same file. The
spec is the problem's checks() without a seeded bug. Lines that run only when a seeded bug is switched on
are NOT RUN; they are left out of the score, which is caught / (changes on lines the spec runs).

Writes one JSON file per problem and summary.md. The changes are made by a program, not by a person, so
the score measures these changes, not bugs in general.
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

from physverify.mutate import run_mutants, to_json

BENCH = Path(__file__).resolve().parents[1]
PROBLEMS = BENCH / "pvbench" / "problems"
TARGETS = {  # problem -> the functions that are the code under test
    "projectile": ("rhs_seeded", "range_seeded"),
    "pendulum": ("rhs_seeded",),
    "kepler": ("rhs_seeded",),
    "heat1d": ("solve",),
    "sod": ("solve",),
}
SPEC = """import sys
sys.path.insert(0, {bench!r})
from pvbench.problems import {name}


def checks():
    return {name}.checks()
"""


def run(out_dir: Path, timeout: float = 600.0) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for name, functions in TARGETS.items():
            spec = Path(tmp) / f"verify_{name}.py"
            spec.write_text(SPEC.format(bench=str(BENCH), name=name), encoding="utf-8")
            target = PROBLEMS / f"{name}.py"
            start = time.perf_counter()
            _, found = run_mutants([spec], target, timeout,
                                   progress=lambda m, name=name: print(f"  {name} {m.line}:{m.col} {m.status}", file=sys.stderr),
                                   functions=functions)
            record = json.loads(to_json(f"benchmark/pvbench/problems/{name}.py", found))
            record["functions"] = list(functions)
            record["seconds"] = round(time.perf_counter() - start, 1)
            (out_dir / f"{name}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            rows.append({"problem": name, **{k: record[k] for k in ("functions", "total", "caught", "not_run", "survived")},
                         "survivors": [m for m in record["mutants"] if m["status"] == "survived"]})
    (out_dir / "summary.md").write_text(summary(rows), encoding="utf-8")
    return rows


def summary(rows) -> str:
    lines = ["# Mutation score of the benchmark specs", "",
             "Made by `python -m pvbench.mutation`. Each change is one program-made edit inside the listed functions;"
             " NOT RUN changes are on lines that run only when a seeded bug is switched on and are left out of the"
             " score.", "",
             "| Problem | Functions | Changes | Not run | Caught | Survived | Score |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        tried = r["total"] - r["not_run"]
        score = f"{r['caught']}/{tried}" if tried else "-"
        lines.append(f"| {r['problem']} | {', '.join(r['functions'])} | {r['total']} | {r['not_run']} | {r['caught']}"
                     f" | {r['survived']} | {score} |")
    lines += ["", "## Survivors", ""]
    for r in rows:
        for m in r["survivors"]:
            lines.append(f"- {r['problem']}.py:{m['line']}:{m['col']}: {m['change']}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    run(Path(sys.argv[1] if len(sys.argv) > 1 else "results/mutation"))
