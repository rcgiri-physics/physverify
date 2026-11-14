"""The committed corpus ledger is what scripts/corpus_ledger.py writes from ledger.csv and funnel.csv (issue #29)."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location("corpus_ledger", ROOT / "scripts" / "corpus_ledger.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ledger_matches_committed(tmp_path):
    out = tmp_path / "LEDGER.md"
    _module().main(out)
    committed = (ROOT / "results" / "corpus" / "LEDGER.md").read_text(encoding="utf-8")
    assert out.read_text(encoding="utf-8") == committed


def test_ledger_totals():
    import csv
    rows = list(csv.DictReader(open(ROOT / "results" / "corpus" / "ledger.csv", encoding="utf-8")))
    assert len(rows) == 74
    assert sum(int(r["scan_recovers"]) for r in rows) == 18
    assert sum(r["found_by"] == "physverify check" for r in rows) == 14
