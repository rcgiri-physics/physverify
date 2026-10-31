"""Is the reference independent? A static look at a spec file before it runs.

The mistake the docs warn about most (AGENTS.md, docs/pitfalls.md) is a reference computed with the code
under test: a bug in the solver is then copied into the reference and the check passes. Here a function whose
name says it is a reference (`exact`, `reference`, `analytic`, `expected`, `*_ref`) is flagged when it uses a
module the spec imports that is not a standard numerical library. A function can be a fair reference and
still use such a module (a constant table, a unit), so these are notes, not failures.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

_TRUSTED = {"numpy", "np", "scipy", "math", "cmath", "sympy", "mpmath", "physverify", "pytest", "functools",
            "itertools", "fractions", "decimal", "dataclasses", "typing", "pathlib", "os", "sys", "json", "time",
            "warnings", "statistics", "random", "collections", "importlib", "matplotlib", "pandas", "astropy", "pint"}
_REFERENCE = re.compile(r"exact|reference|analytic|expected|truth|^ref_|_ref$|_ref_|^ref$", re.I)
_LOADERS = {"load_module_from_path", "import_module", "extract_functions", "load_spec"}


def _solver_names(tree) -> set[str]:
    """Names bound to modules that are neither standard nor numerical libraries (the code under test)."""
    stdlib = set(getattr(sys, "stdlib_module_names", ()))
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                top = a.name.split(".")[0]
                if top not in _TRUSTED and top not in stdlib:
                    out.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            top = n.module.split(".")[0]
            if top not in _TRUSTED and top not in stdlib:
                out.update(a.asname or a.name for a in n.names if a.name != "*")
        elif isinstance(n, ast.ImportFrom) and n.level > 0:  # from . import solver
            out.update(a.asname or a.name for a in n.names if a.name != "*")
        elif isinstance(n, ast.Assign) and isinstance(n.value, ast.Call):
            fn = n.value.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name in _LOADERS:
                out.update(t.id for t in n.targets if isinstance(t, ast.Name))
    return out


def reference_notes(path) -> list[str]:
    """One note per reference-like function in the spec that uses the code under test."""
    path = Path(path)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), str(path))
    except (OSError, SyntaxError, ValueError):
        return []
    solver = _solver_names(tree)
    if not solver:
        return []
    notes = []
    for f in ast.walk(tree):
        if not (isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) and _REFERENCE.search(getattr(f, "name", ""))):
            continue
        used = sorted({n.id for n in ast.walk(f) if isinstance(n, ast.Name) and n.id in solver})
        if used:
            notes.append(f"{path.name}:{f.lineno}: the reference {f.name}() uses {', '.join(used)}, which the spec imports"
                         " as the code under test; a reference computed with the solver passes even when the solver is"
                         " wrong (derive it from the physics instead, or say why this use is safe)")
    return notes
