"""`# pv: ignore` comments and baseline files for `physverify scan`."""

import json

from physverify.cli import main
from physverify.scan import scan
from physverify.suppress import apply_baseline, apply_ignores, write_baseline

CODE = "import numpy as np\n\n\ndef f(x):\n    return np.NaN + y\n"


def _project(tmp_path, code=CODE):
    (tmp_path / "m.py").write_text(code, encoding="utf-8")
    return tmp_path


def _rules(findings):
    return sorted(f.rule for f in findings)


def test_the_example_has_two_rules(tmp_path):
    findings, _ = scan(_project(tmp_path))
    assert _rules(findings) == ["PV401", "PV502"]


def test_ignore_one_rule_several_or_all(tmp_path):
    line = "    return np.NaN + y"
    for comment, left in (("# pv: ignore[PV401]", ["PV502"]), ("# pv: ignore[pv401, PV502]", []),
                          ("# pv: ignore", []), ("# pv: ignore[PV999]", ["PV401", "PV502"])):
        root = _project(tmp_path, CODE.replace(line, f"{line}  {comment}"))
        kept, hidden = apply_ignores(scan(root)[0], root)
        assert _rules(kept) == left and hidden == 2 - len(left), comment


def test_ignore_on_another_line_hides_nothing(tmp_path):
    root = _project(tmp_path, CODE.replace("def f(x):", "def f(x):  # pv: ignore"))
    assert apply_ignores(scan(root)[0], root)[1] == 0


def test_baseline_survives_lines_added_above_and_reports_new_findings(tmp_path):
    root = _project(tmp_path)
    base = tmp_path.parent / f"{tmp_path.name}_baseline.json"
    assert write_baseline(scan(root)[0], root, base) == 2
    # two lines added above shift the old findings; a new copy of one is added below
    _project(tmp_path, "# a\n# b\n" + CODE + "\n\ndef g():\n    return np.NaN\n")
    kept, known = apply_baseline(scan(root)[0], root, base)
    assert known == 2 and _rules(kept) == ["PV502"] and kept[0].line == 11


def test_cli_baseline_round_trip(tmp_path, capsys):
    (tmp_path / "p").mkdir()
    root = _project(tmp_path / "p")
    base = tmp_path / "baseline.json"
    assert main(["scan", str(root), "--write-baseline", str(base)]) == 0
    assert len(json.loads(base.read_text())["findings"]) == 2
    assert main(["scan", str(root), "--baseline", str(base)]) == 0
    assert "2 in the baseline not shown" in capsys.readouterr().out
    assert main(["scan", str(root)]) == 1


def test_cli_rejects_a_broken_baseline(tmp_path):
    root = _project(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text('{"version": 99, "findings": []}')
    assert main(["scan", str(root / "m.py"), "--baseline", str(bad)]) == 2
