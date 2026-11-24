"""Rule IDs of `physverify scan`: every finding the source can make names a known rule of its own stage."""

import ast
from pathlib import Path

from physverify.rules import RULES
from physverify.scan import Finding

SRC = Path(__file__).resolve().parents[1] / "src" / "physverify"


def _finding_calls():
    for path in sorted(SRC.rglob("*.py")):
        name = path.relative_to(SRC).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "Finding" and n.args:
                yield name, n


def test_every_finding_names_a_rule_of_its_stage():
    seen = set()
    for name, n in _finding_calls():
        level = ast.unparse(n.args[1])
        rule = next((k.value.value for k in n.keywords if k.arg == "rule"), None)
        if level == "SKIP":
            assert rule is None, f"{name}:{n.lineno}: a SKIP is not a finding and has no rule"
            continue
        assert rule in RULES, f"{name}:{n.lineno}: rule {rule!r} is not in physverify.rules"
        assert ast.literal_eval(n.args[0]) == RULES[rule].stage, f"{name}:{n.lineno}: {rule} belongs to another stage"
        seen.add(rule)
    assert seen == set(RULES), f"rules that nothing reports: {sorted(set(RULES) - seen)}"


def test_ids_and_names_are_unique():
    assert len({r.name for r in RULES.values()}) == len(RULES)
    assert all(k == r.id and k.startswith("PV") and len(k) == 5 for k, r in RULES.items())


def test_rule_is_shown_and_kept_in_json():
    f = Finding("names", "WARN", "a.py", 3, "x is used but never defined", rule="PV401")
    assert str(f) == "WARN names     a.py:3: [PV401] x is used but never defined"
    from dataclasses import asdict
    assert asdict(f)["rule"] == "PV401" and Finding(**asdict(f)) == f


def test_docs_page_lists_every_rule():
    page = (SRC.parents[1] / "docs" / "scan-rules.md").read_text(encoding="utf-8")
    for r in RULES.values():
        assert f"| {r.id} | `{r.name}` | {r.summary} |" in page, f"{r.id} is missing from docs/scan-rules.md"
