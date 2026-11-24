"""`# pv: ignore` comments and baseline files for `physverify scan`."""

import json

from physverify.cli import main
from physverify.scan import scan
from physverify.suppress import (
    apply_baseline,
    apply_ignores,
    changed_files,
    write_baseline,
)

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


def _git(root, *args):
    import subprocess
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                   env={**__import__("os").environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})


def test_changed_since_reports_only_changed_and_new_files(tmp_path, capsys):
    root = _project(tmp_path)
    (root / "old.py").write_text("x = np.NaN\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "start")
    (root / "m.py").write_text(CODE + "z = w\n", encoding="utf-8")   # changed
    (root / "new.py").write_text("q = r\n", encoding="utf-8")        # untracked
    assert main(["scan", str(root), "--changed-since", "HEAD"]) == 1
    out = capsys.readouterr().out
    assert "old.py" not in out and "m.py" in out and "new.py" in out
    assert "in files unchanged since HEAD not shown" in out
    assert main(["scan", str(root), "--changed-since", "no-such-ref"]) == 2


def test_changed_files_handles_non_ascii_paths(tmp_path):
    root = tmp_path / "src"
    root.mkdir()
    tracked = root / "é.py"
    tracked.write_text("x = 1\n", encoding="utf-8")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "start")
    tracked.write_text("x = 2\n", encoding="utf-8")
    (root / "β.py").write_text("y = 1\n", encoding="utf-8")
    assert changed_files(root, "HEAD") == {"é.py", "β.py"}
    assert changed_files(tracked, "HEAD") == {"é.py"}


def test_sarif_has_rules_levels_and_locations(tmp_path, monkeypatch):
    (tmp_path / "proj").mkdir()
    _project(tmp_path / "proj")
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "scan.sarif"
    assert main(["scan", "proj", "--sarif", str(out)]) == 1
    run = json.loads(out.read_text())["runs"][0]
    assert json.loads(out.read_text())["version"] == "2.1.0"
    assert [r["id"] for r in run["tool"]["driver"]["rules"]] == ["PV401", "PV502"]
    res = sorted(run["results"], key=lambda r: r["ruleId"])
    assert [(r["ruleId"], r["level"]) for r in res] == [("PV401", "warning"), ("PV502", "warning")]
    loc = res[0]["locations"][0]["physicalLocation"]
    assert loc == {"artifactLocation": {"uri": "proj/m.py"}, "region": {"startLine": 5}}
    for r in res:
        assert run["tool"]["driver"]["rules"][r["ruleIndex"]]["id"] == r["ruleId"]
