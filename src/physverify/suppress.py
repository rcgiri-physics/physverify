"""Leaving out scan findings: `# pv: ignore[RULE]` comments and a baseline file.

A comment on the line of a finding hides it: `# pv: ignore[PV401]` hides that rule, `# pv: ignore[PV401,PV502]`
several, and `# pv: ignore` every rule on the line. A baseline file lists the findings a project already has, so
an existing project can adopt `scan` in CI and see only new ones. A finding is matched by its file, its rule and
the text of its line, not by the line number, so it stays matched when lines above it are added or removed.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path

_IGNORE = re.compile(r"#\s*pv:\s*ignore(?:\[([A-Za-z0-9_, ]*)\])?", re.I)
BASELINE_VERSION = 1


def _lines(root: Path, rel: str, cache: dict) -> list[str]:
    if rel not in cache:
        f = root / rel if root.is_dir() else root
        try:
            cache[rel] = f.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        except OSError:
            cache[rel] = []
    return cache[rel]


def _line_text(root: Path, f, cache: dict) -> str:
    lines = _lines(root, f.path, cache)
    return lines[f.line - 1].strip() if 0 < f.line <= len(lines) else ""


def ignored_by_comment(finding, line: str) -> bool:
    """True if `line` carries a `# pv: ignore` comment that covers this finding's rule."""
    for m in _IGNORE.finditer(line):
        if m.group(1) is None:
            return True
        if finding.rule and finding.rule.upper() in {r.strip().upper() for r in m.group(1).split(",")}:
            return True
    return False


def apply_ignores(findings, path) -> tuple[list, int]:
    """The findings not hidden by a `# pv: ignore` comment on their line, and how many were hidden."""
    root, cache = Path(path), {}
    kept = [f for f in findings if not (f.rule and ignored_by_comment(f, _line_text(root, f, cache)))]
    return kept, len(findings) - len(kept)


def _key(root: Path, f, cache: dict) -> tuple[str, str, str]:
    return (Path(f.path).as_posix(), f.rule, _line_text(root, f, cache))


def write_baseline(findings, path, out) -> int:
    """Write every finding with a rule to the baseline file `out`; returns how many were written."""
    root, cache = Path(path), {}
    rows = sorted(_key(root, f, cache) for f in findings if f.rule)
    data = {"version": BASELINE_VERSION, "tool": "physverify scan",
            "findings": [{"path": p, "rule": r, "line_text": t} for p, r, t in rows]}
    Path(out).write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    return len(rows)


def apply_baseline(findings, path, baseline) -> tuple[list, int]:
    """The findings not listed in the baseline file, and how many were left out.

    Each baseline entry matches one finding, so a second copy of a known finding on a new line is still reported.
    """
    data = json.loads(Path(baseline).read_text(encoding="utf-8"))
    if data.get("version") != BASELINE_VERSION:
        raise ValueError(f"{baseline}: baseline version {data.get('version')!r}, expected {BASELINE_VERSION}")
    known = Counter((e["path"], e["rule"], e["line_text"]) for e in data["findings"])
    root, cache, kept = Path(path), {}, []
    for f in findings:
        k = _key(root, f, cache)
        if f.rule and known[k] > 0:
            known[k] -= 1
        else:
            kept.append(f)
    return kept, len(findings) - len(kept)


def changed_files(path, ref: str) -> set[str]:
    """Python files under `path` that differ from the git revision `ref` (or are new and untracked), as paths
    relative to `path` like the findings use. Raises RuntimeError when git cannot answer."""
    root = Path(path)
    where = root if root.is_dir() else root.parent
    out = set()
    # NUL-delimited paths are emitted verbatim, including non-ASCII and newline characters.
    for cmd in (["git", "diff", "--name-only", "-z", "--relative", "--diff-filter=ACMR", ref, "--"],
                ["git", "ls-files", "-z", "--others", "--exclude-standard"]):
        r = subprocess.run(cmd, cwd=where, capture_output=True, stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            detail = os.fsdecode(r.stderr).strip()[:200]
            raise RuntimeError(f"{' '.join(cmd[:2])} failed: {detail}")
        out.update(Path(os.fsdecode(name)).as_posix() for name in r.stdout.split(b"\0") if name.endswith(b".py"))
    if not root.is_dir():
        return {root.name} & out  # git ran in the file's folder, so the file is listed by its name
    return out


def only_changed(findings, path, ref: str) -> tuple[list, int]:
    """The findings in files changed since `ref`, and how many in unchanged files were left out."""
    changed = changed_files(path, ref)
    kept = [f for f in findings if Path(f.path).as_posix() in changed]
    return kept, len(findings) - len(kept)
