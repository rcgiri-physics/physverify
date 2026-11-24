"""SARIF 2.1.0 output for `physverify scan`, for GitHub code scanning and other SARIF viewers.

Format: OASIS SARIF 2.1.0 (https://docs.oasis-open.org/sarif/sarif/v2.1.0/). GitHub reads `ruleId`, `level`,
`message.text` and one physical location per result; WARN is "warning", NOTE is "note". SKIP results are not
findings and are left out.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import __version__
from .rules import RULES

SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
_LEVEL = {"WARN": "warning", "NOTE": "note"}


def _uri(scan_path: Path, rel: str) -> str:
    """The file's path relative to the working directory, as code scanning expects (repository root in CI)."""
    f = scan_path / rel if scan_path.is_dir() else scan_path
    try:
        f = Path(os.path.relpath(f.resolve(), Path.cwd().resolve()))
    except ValueError:  # another drive on Windows
        pass
    return f.as_posix()


def to_sarif(findings, scan_path) -> dict:
    scan_path = Path(scan_path)
    results = [f for f in findings if f.level in _LEVEL and f.rule]
    used = sorted({f.rule for f in results})
    rules = [{"id": r, "name": RULES[r].name, "shortDescription": {"text": RULES[r].summary},
              "helpUri": f"https://rcgiri-physics.github.io/physverify/scan-rules/#{RULES[r].stage}",
              "properties": {"stage": RULES[r].stage}} for r in used]
    index = {r: i for i, r in enumerate(used)}
    return {"$schema": SCHEMA, "version": "2.1.0", "runs": [{
        "tool": {"driver": {"name": "physverify", "version": __version__,
                            "informationUri": "https://github.com/rcgiri-physics/physverify", "rules": rules}},
        "results": [{"ruleId": f.rule, "ruleIndex": index[f.rule], "level": _LEVEL[f.level],
                     "message": {"text": f.message},
                     "locations": [{"physicalLocation": {
                         "artifactLocation": {"uri": _uri(scan_path, f.path)},
                         "region": {"startLine": max(1, f.line)}}}]} for f in results],
    }]}


def write_sarif(findings, scan_path, out) -> None:
    Path(out).write_text(json.dumps(to_sarif(findings, scan_path), indent=1) + "\n", encoding="utf-8")
