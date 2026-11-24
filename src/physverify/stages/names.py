"""Stage `names`: names used but never defined, and files that do not parse (PV401 to PV406)."""

from __future__ import annotations

import ast
import builtins
import re
from pathlib import Path

from .common import NOTE, WARN, Finding, _guarded, all_nodes

# --- names ------------------------------------------------------------------------------------------

_MODULE_NAMES = {"__file__", "__name__", "__doc__", "__spec__", "__loader__", "__package__", "__builtins__",
                 "__path__", "__annotations__", "__dict__", "__class__", "__qualname__", "__module__",
                 "get_ipython", "display", "In", "Out", "exit", "quit", "__IPYTHON__"}  # the last ones come with IPython


def _bound_names(tree) -> set[str]:
    """Every name bound anywhere in the file, in any scope."""
    out = set()
    for n in all_nodes(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.arg):
            out.add(n.arg)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                out.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            out.update(n.names)
        elif isinstance(n, ast.MatchAs) and n.name:
            out.add(n.name)
        elif isinstance(n, ast.MatchStar) and n.name:
            out.add(n.name)
        elif isinstance(n, ast.MatchMapping) and n.rest:
            out.add(n.rest)
        elif type(n).__name__ in ("TypeVar", "ParamSpec", "TypeVarTuple"):  # def f[T](...) (Python 3.12)
            out.add(n.name)
    return out


def _dynamic(tree) -> bool:
    """The file defines names in ways the scan cannot follow: `from x import *`, exec, globals()[...]."""
    for n in all_nodes(tree):
        if isinstance(n, ast.ImportFrom) and any(a.name == "*" for a in n.names):
            return True
        if isinstance(n, ast.Call) and getattr(n.func, "id", None) in ("exec", "globals", "locals", "vars", "setattr"):
            return True
    return False


def _annotation_nodes(tree) -> set[int]:
    """Nodes inside type annotations (arguments, return values, annotated assignments)."""
    roots = []
    for n in all_nodes(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.returns is not None:
            roots.append(n.returns)
        elif isinstance(n, ast.arg) and n.annotation is not None:
            roots.append(n.annotation)
        elif isinstance(n, ast.AnnAssign):
            roots.append(n.annotation)
    return {id(m) for r in roots for m in ast.walk(r)}


# a file with this many undefined names, none of them a usual module alias, is treated as getting them at run time
_INJECTED_MIN = 6
_COMMON_ALIASES = {"np", "plt", "pd", "sp", "scipy", "numpy", "math", "os", "sys", "re", "json", "time", "random",
                   "torch", "jnp", "jax", "tf", "mpl", "sns", "nx", "integrate", "interpolate", "optimize", "linalg"}
_NOQA = re.compile(r"#\s*noqa(?::[^#]*\bF821\b|\s*$|\s*#)", re.I)


def scan_names(path: Path, tree, rel: str, source: str = "") -> list[Finding]:
    if _dynamic(tree):
        return []
    known = _bound_names(tree) | set(dir(builtins)) | _MODULE_NAMES
    if path.name.endswith("_config.py") and re.search(r"jupyter|ipython|nbconvert", path.name, re.I):
        known |= {"c", "get_config", "load_subconfig"}  # Jupyter and IPython inject these into their config files
    guarded = _guarded(tree)
    annotations = _annotation_nodes(tree)
    lazy = any(isinstance(n, ast.ImportFrom) and n.module == "__future__" and any(a.name == "annotations" for a in n.names)
               for n in tree.body)
    lines_text = source.splitlines()
    unknown, in_annotation = {}, {}
    for n in all_nodes(tree):
        if not (isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in known and id(n) not in guarded):
            continue
        if 0 < n.lineno <= len(lines_text) and _NOQA.search(lines_text[n.lineno - 1]):
            continue  # the authors marked it as known (a noqa comment for F821)
        if id(n) in annotations:
            if not lazy:
                in_annotation.setdefault(n.id, []).append(n.lineno)
            continue  # annotations are not evaluated with `from __future__ import annotations` (or from Python 3.14)
        unknown.setdefault(n.id, []).append(n.lineno)
    out = []
    if len(unknown) >= _INJECTED_MIN and not unknown.keys() & _COMMON_ALIASES:
        # many names and none of them a forgotten import: the file most likely gets them at run time
        # (a host program such as SpaceClaim, or a library that defines names in the caller's namespace)
        first = min(lines[0] for lines in unknown.values())
        shown = ", ".join(sorted(unknown)[:8]) + (", ..." if len(unknown) > 8 else "")
        return [Finding("names", NOTE, rel, first,
                        f"{len(unknown)} names are used but never defined or imported ({shown}); so many usually means they"
                        " are provided at run time by a host program or a library, so they are not reported one by one", rule="PV402")]
    for name, lines in sorted(unknown.items(), key=lambda kv: kv[1][0]):
        close = [k for k in sorted(known) if k != name and len(k) > 2 and _one_edit(name, k)]
        hint = f" (did you mean {close[0]}?)" if close else ""
        more = f", also lines {', '.join(map(str, lines[1:6]))}" if len(lines) > 1 else ""
        out.append(Finding("names", WARN, rel, lines[0],
                           f"{name} is used but never defined or imported in this file{hint}{more}; it raises NameError when reached", rule="PV401"))
    for name, lines in sorted(in_annotation.items(), key=lambda kv: kv[1][0]):
        if name not in unknown:
            out.append(Finding("names", NOTE, rel, lines[0],
                               f"{name} is used only in type annotations and never defined or imported; Python 3.13 and"
                               " older evaluate annotations at definition time, so this raises NameError there", rule="PV403"))
    return out


def _one_edit(a: str, b: str) -> bool:
    """a and b differ by one inserted, deleted or changed character."""
    if abs(len(a) - len(b)) > 1 or a == b:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    return any(long_[:i] + long_[i + 1:] == short for i in range(len(long_)))


def parse_finding(rel: str, exc: Exception, source: str = "") -> Finding:
    """A file that does not parse is a finding: it cannot run (a template is only a NOTE)."""
    msg = getattr(exc, "msg", str(exc))
    line = getattr(exc, "lineno", 0) or 0
    if re.search(r"\{\{.*\}\}|\{%.*%\}", source):
        return Finding("names", NOTE, rel, line, f"the file does not parse, but looks like a template ({{{{ }}}} or {{% %}}): {msg}", rule="PV405")
    why = " (Python 2 code)" if "print" in msg and "parenthes" in msg else ""
    # a loose script in misc/, scripts/ or examples/ is not part of the package (corpus repo L164): one look, not a defect
    loose = bool(set(Path(rel).parts[:-1]) & _LOOSE_DIRS)
    return Finding("names", NOTE if loose else WARN, rel, line,
                   f"the file does not parse{why}: {msg}" + ("; it is outside the package, in a folder of loose scripts" if loose else ""), rule="PV404")


_LOOSE_DIRS = {"misc", "scripts", "script", "examples", "example", "old", "legacy", "attic", "archive", "sandbox"}
