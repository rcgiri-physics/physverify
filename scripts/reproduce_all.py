"""Regenerate every benchmark table in results/ (and the corpus ledger) from a clean checkout.

    python scripts/reproduce_all.py          # seeded-bug matrix, catalogue, comparison (deterministic)
    python scripts/reproduce_all.py --slow   # also the Monte Carlo (Ising) matrix, several minutes

The Markdown tables are deterministic and must match the committed ones
(tests/test_seeded_bugs.py checks this); detection_matrix.json and run_time.md
also record the machine and the run times, which differ between runs.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    ["-m", "pvbench.matrix", "results/detection_matrix.md"],
    ["-m", "pvbench.compare", "results/comparison.md"],
    ["scripts/make_figures.py"],
    ["scripts/corpus_ledger.py"],
]
SLOW = [["-m", "pvbench.ising_matrix", "results/ising_matrix.md"]]


def main() -> int:
    steps = STEPS + (SLOW if "--slow" in sys.argv[1:] else [])
    for step in steps:
        print("python", " ".join(step), flush=True)
        env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT / "benchmark")])}
        subprocess.run([sys.executable, *step], cwd=ROOT, check=True, stdout=subprocess.DEVNULL, env=env)
    print("done; `git diff results/` shows what changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
