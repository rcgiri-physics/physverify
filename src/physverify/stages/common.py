"""Shared pieces of the static scan: the Finding record, levels, file discovery and AST walking."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

WARN = "WARN"
NOTE = "NOTE"
SKIP_DIRS = {".git", ".venv", "venv", "env", "__pycache__", "build", "dist", "node_modules", "site-packages", ".tox"}


@dataclass
class Finding:
    stage: str
    level: str
    path: str
    line: int
    message: str
    table: dict | None = field(default=None, repr=False)  # the Runge-Kutta table a "tables" finding was made from
    rule: str = field(default="", kw_only=True)  # the stable ID in physverify.rules ("" for a SKIP)

    def __str__(self):
        rule = f" [{self.rule}]" if self.rule else ""
        return f"{self.level} {self.stage:9s} {self.path}:{self.line}:{rule} {self.message}"


def python_files(path) -> list[Path]:
    path = Path(path)
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*.py") if not SKIP_DIRS & set(p.relative_to(path).parts[:-1]))
_ORDER_HINT = re.compile(r"(\d)(?:st|nd|rd|th)[ -]order|(?:order|ord)[ _=:(]*(\d)|(?:^|[^a-z0-9])(?:rk|erk|irk|dirk|sdirk|esdirk)[ _-]?(\d)(?!\d)", re.I)
# Coefficients are often typed with 7 to 10 digits; a missing order shows residuals of 1e-4 or more.
_TOL = 1e-6
_NAMED = {"heun": 2, "midpoint": 2, "ralston": 2, "kutta3": 3, "ssprk3": 3, "rk38": 4, "three_eighths": 4,
          "classic": 4, "fehlberg": 4, "cash_karp": 5, "cashkarp": 5, "dopri": 5, "dormand": 5, "tsit": 5,
          "verner": 6, "bogacki": 3}


def _claimed_order(text: str):
    """(order, the words that claim it) from a name or docstring; an explicit "order 4" or "rk4" wins over a method name."""
    t = text.lower()
    m = _ORDER_HINT.search(t)
    if m:
        return int(next(g for g in m.groups() if g)), m.group(0).strip(" _-=:(")
    m = re.search(r"(?:^|[^a-z])(heun|ralston|kutta|wray|ssprk|bs|bogacki|midpoint|euler|gauss|radau|lobatto)_?(\d)(?!\d)", t)
    if m:
        return int(m.group(2)), m.group(0).strip(" _")
    for key, p in _NAMED.items():
        if key in t:
            return p, key
    return None, None


def all_nodes(tree) -> list:
    """Every node of a file's tree, computed once and shared by the stages (walking the tree is most of the cost)."""
    cached = getattr(tree, "_pv_nodes", None)
    if cached is None:
        cached = tree._pv_nodes = list(ast.walk(tree))
    return cached


def _scopes(tree):
    """Module, each class and each function: (node, name, docstring) to look for tables in (computed once per tree)."""
    cached = getattr(tree, "_pv_scopes", None)
    if cached is None:
        cached = [(tree, "", (ast.get_docstring(tree) or "") if isinstance(tree, ast.Module) else "")]
        cached += [(n, n.name, ast.get_docstring(n) or "") for n in all_nodes(tree)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        tree._pv_scopes = cached
    return cached


def _call_name(n) -> str:
    return n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")


def _src(node) -> str:
    return re.sub(r"\s+", "", ast.unparse(node))


_GUARDS = {"NameError", "ImportError", "ModuleNotFoundError", "AttributeError", "Exception", "BaseException"}


def _guards(node) -> bool:
    """A try that catches NameError, ImportError, ... (so a missing name there is expected)."""
    if not isinstance(node, ast.Try):
        return False
    caught = set()
    for h in node.handlers:
        if h.type is None:
            caught.add("Exception")
        types = [h.type] if h.type is not None else []
        if isinstance(h.type, ast.Tuple):
            types += list(h.type.elts)
        caught.update(getattr(t, "id", getattr(t, "attr", "")) for t in types)
    return bool(caught & _GUARDS)


def _version_branch(node) -> bool:
    """`if sys.version_info < (3,)`, `if PY2`, `if six.PY3`: code for another Python version."""
    if not isinstance(node, ast.If):
        return False
    test = ast.unparse(node.test)
    # also lowercase flags (`py3 = sys.version_info[0] == 3; if py3:`), as in corpus repo L212
    return "version_info" in test or bool(re.search(r"\b(?:is_)?PY[23]K?\b|six\.PY", test, re.I))


def _guarded(tree) -> set[int]:
    """Nodes where a missing name is expected: inside such a try body, or inside a branch for another Python version."""
    cached = getattr(tree, "_pv_guarded", None)
    if cached is not None:
        return cached
    out, todo = set(), [(tree, False)]
    while todo:
        node, inside = todo.pop()
        if inside:
            out.add(id(node))
        if _guards(node):
            todo.extend((c, True) for c in node.body)
            todo.extend((c, inside) for part in (node.handlers, node.orelse, node.finalbody) for c in part)
        elif _version_branch(node):
            todo.extend((c, True) for c in node.body + node.orelse)
            todo.append((node.test, inside))
        else:
            todo.extend((c, inside) for c in ast.iter_child_nodes(node))
    tree._pv_guarded = out
    return out


def _aliases(tree, module: str) -> set[str]:
    cache = tree.__dict__.setdefault("_pv_aliases", {})
    if module in cache:
        return cache[module]
    out = cache[module] = set()
    for n in all_nodes(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name == module:
                    out.add(a.asname or a.name)
    return out


def _own_nodes(scope):
    """Nodes of a scope, without descending into nested functions or classes."""
    todo = list(ast.iter_child_nodes(scope))
    while todo:
        node = todo.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        yield node
        todo.extend(ast.iter_child_nodes(node))
