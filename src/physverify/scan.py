"""`physverify scan PATH`: checks that need no spec file and no adapter.

The scan only reads the source; it never imports or runs the code, so it is safe on code you do not trust.
Each stage comes from a kind of bug found in the corpus study:

- constants   numeric literals close to, but not equal to, a physical constant (`physverify.constants`)
- tables      Runge-Kutta (Butcher) tables written as literals: the order they really have, row sums
              against c, error weights that should sum to 0, and the order the names claim
              (mislabelled tables in two research packages; Tsit5 error weights summing to 0.97)
- grid        a spacing `(b - a) / N` next to `linspace(a, b, N)`, which has spacing `(b - a) / (N - 1)`
              (two quantum solvers, energies off at first order)
- pairs       functions whose names say they are inverses (`x_to_y` / `y_to_x`), listed as round trips
              worth running with `physverify.identities.check_roundtrip`; not run here

- names, api, literals, units   undefined names and files that do not parse, removed NumPy/SciPy/Python
              features, typo-like literals, unit tables with the wrong dimension
- flow        the order of statements in a function: possibly unbound locals, array aliases

Each stage is a module in `physverify.stages`; the rule IDs are in `physverify.rules`.

A finding is WARN (very likely a defect: a table that misses its claimed order, row sums that do not
match c, a spacing that does not match its grid) or NOTE (worth one look). A clean scan says only that
these patterns were not found.
"""

from __future__ import annotations

import ast
import warnings
from dataclasses import asdict
from pathlib import Path

from .stages.api import scan_api
from .stages.common import NOTE, SKIP_DIRS, WARN, Finding, all_nodes, python_files
from .stages.constants import scan_constants
from .stages.flow import scan_flow
from .stages.grid import _grid_findings, _grids_and_divs, _names, scan_grid
from .stages.literals import scan_literals
from .stages.names import parse_finding, scan_names
from .stages.pairs import scan_pairs
from .stages.stepper_tables import scan_code_tables
from .stages.tables import scan_tables
from .stages.units import scan_units

# --- driver ---------------------------------------------------------------------------------------

__all__ = ["NOTE", "SKIP_DIRS", "STAGES", "WARN", "Finding", "all_nodes", "extract_tables", "python_files",
           "scan", "to_dict"]

STAGES = ("constants", "tables", "grid", "pairs", "names", "api", "literals", "units", "flow")


def scan(path, *, stages=STAGES) -> tuple[list[Finding], list[str]]:
    """Findings for every Python file under `path`, and the files that could not be parsed."""
    root = Path(path)
    findings, unparsed, parsed = [], [], []
    for f in python_files(root):
        rel = str(f.relative_to(root)) if root.is_dir() else f.name
        try:
            text = f.read_text(encoding="utf-8-sig", errors="replace")  # a byte-order mark is valid Python
        except OSError as exc:  # a broken link or a file without read permission must not stop the scan
            unparsed.append(f"{rel}: not read: {type(exc).__name__}: {exc}")
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # invalid escapes in other people's strings are not our concern
                tree = ast.parse(text, str(f))
        except (SyntaxError, ValueError) as exc:
            if "names" in stages:
                findings.append(parse_finding(rel, exc, text))
            else:
                unparsed.append(f"{rel}: {type(exc).__name__}: {exc}")
            continue
        parsed.append((rel, tree))
        runs = (("constants", scan_constants), ("tables", scan_tables), ("tables", scan_code_tables),
                ("grid", scan_grid), ("pairs", scan_pairs), ("names", lambda f, t, r: scan_names(f, t, r, text)), ("api", scan_api),  # noqa: B023 (called in this iteration)
                ("literals", lambda f, t, r: scan_literals(f, t, r, text)), ("units", scan_units), ("flow", scan_flow))  # noqa: B023
        for stage, run in runs:
            if stage in stages:
                try:
                    findings += run(f, tree, rel)
                except Exception as exc:  # noqa: BLE001 - one odd file must not stop the scan of a project
                    unparsed.append(f"{rel}: {stage} stage stopped: {type(exc).__name__}: {exc}")
    if "grid" in stages and len(parsed) > 1:
        # a spacing in one file and the grid it belongs to in another (a Hamiltonian class and its particle grid)
        per_file = {rel: _grids_and_divs(tree) for rel, tree in parsed}
        seen = {id(d[0]) for f in findings if f.stage == "grid" for rel, (_g, divs) in per_file.items()
                if rel == f.path for d in divs if d[1] == f.line}
        # index the grids by the names in their number of points, so each division meets only grids it shares a name with
        by_name = {}
        for rel_g, (grids, _d) in per_file.items():
            for g in grids:
                for n in _names(g[2]):
                    by_name.setdefault(n, {}).setdefault(rel_g, []).append(g)
        for rel_d, (_g, divs) in per_file.items():
            for div in divs:
                if id(div[0]) in seen:
                    continue
                for rel_g in sorted({r for n in div[3] for r in by_name.get(n, {})} - {rel_d}):
                    grids = {id(g): g for n in div[3] for g in by_name.get(n, {}).get(rel_g, [])}
                    findings += _grid_findings(list(grids.values()), [div], rel_d, rel_g, seen)
    if "names" in stages:
        findings = _snippet_folders(findings, parsed, root if root.is_dir() else root.parent)
    return findings, unparsed


_SNIPPET_FILES = 3


def _snippet_folders(findings, parsed, root=None):
    """A folder of tutorial snippets meant to be pasted together uses in one file the names defined in another
    (corpus repo L204). When most undefined names of a folder with several such files are defined in a sibling file,
    report the folder once as a NOTE instead of one WARN per name. Not in a package (a folder with __init__.py):
    there a name defined in a sibling module but never imported raises NameError (corpus repos L086, L174)."""
    def folder(rel):
        return str(Path(rel).parent)
    defined = {}
    for rel, tree in parsed:
        names = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        names |= {t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
        defined.setdefault(folder(rel), {})[rel] = names
    undefined = [f for f in findings if f.stage == "names" and f.level == WARN and "never defined" in f.message]
    by_folder = {}
    for f in undefined:
        by_folder.setdefault(folder(f.path), []).append(f)
    drop, notes = set(), []
    for d, fs in by_folder.items():
        files = {f.path for f in fs}
        if root is not None and (Path(root) / d / "__init__.py").exists():
            continue  # in a package, a name defined in a sibling module but not imported is a real NameError
        # a subfolder of snippets may continue the files one level up (python/qutip/x.py after python/x.py)
        siblings = {**defined.get(str(Path(d).parent), {}), **defined.get(d, {})} if d != "." else defined.get(d, {})
        if len(siblings) < _SNIPPET_FILES:
            continue
        found = [f for f in fs if any(f.message.split()[0] in names for rel, names in siblings.items() if rel != f.path)]
        if 2 * len(found) >= len(fs):
            drop |= {id(f) for f in fs}
            notes.append(Finding("names", NOTE, sorted(files)[0], min(f.line for f in fs),
                                 f"{len(fs)} undefined names in {len(files)} files of {d or '.'}, most of them defined in a"
                                 " sibling file: this looks like a folder of snippets meant to be run together, so they are"
                                 " not reported one by one", rule="PV406"))
    return [f for f in findings if id(f) not in drop] + notes


def extract_tables(path) -> list[dict]:
    """Every Runge-Kutta table the scan finds under `path`, as dicts with A, b, c (or None), the claimed order and
    where the claim comes from, embedded and error weights, and the order the coefficients have. Runs nothing.

    For checks the scan does not make itself, pass them on, e.g.
    `physverify.butcher.check_tableau(t["A"], t["b"], t["c"], claimed=t["claimed"])`.
    """
    findings, _unparsed = scan(path, stages=("tables",))
    return [dict(f.table, path=f.path, line=f.line, level=f.level) for f in findings if f.table is not None]


def to_dict(findings, unparsed) -> dict:
    return {"findings": [asdict(f) for f in findings], "unparsed": unparsed,
            "warn": sum(f.level == WARN for f in findings), "note": sum(f.level == NOTE for f in findings)}
