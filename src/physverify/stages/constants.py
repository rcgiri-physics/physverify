"""Stage `constants`: numeric literals close to, but not equal to, a physical constant (PV301, PV302)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from .common import NOTE, Finding, all_nodes

# --- constants ------------------------------------------------------------------------------------

# Pure numbers sit within 10% of many ordinary literals (2.5 and 3.3 are "near" e and pi), so the scan notes
# them only when they are close; dimensional constants (6.6e-11, 3e8) rarely match by chance.
_PURE = {"pi", "e (Euler)", "T_c (2D Ising)", "G M_sun / 4 pi^2 (au, yr)"}
_PURE_REL = 2e-3
# Constants with units: an old edition or a rounded value is within 0.1%, while values 2-10% away were almost all
# other quantities in the corpus rescan (test values, the atomic mass unit next to the proton mass).
_DIM_REL = 1e-2
_TABLE_MIN = 8
_MANY_CONSTANTS = 20
# Units and constants fixed by definition: a slip or an old value sits within 0.1%, so only that close is noted.
_DEFINED = {"N_A", "R (gas constant)", "sigma (Stefan-Boltzmann)", "astronomical unit", "light year", "parsec",
            "standard atmosphere", "torr", "nautical mile", "h (CGS)", "k_B (CGS)", "c (CGS)", "e (esu)", "m_e (g)",
            "G (CGS)"}
_DEFINED_REL = 1e-3


_FIT_TERMS = 4


def _fit_coefficients(tree) -> set[int]:
    """Numbers that are coefficients in a sum of at least four numeric products (a fitted formula such as
    c0 + c1*x + c2*x**2 + ...): their values come from the fit, not from a constant (corpus repos L171, L174)."""
    out, seen = set(), set()
    for n in all_nodes(tree):
        if not (isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub))) or id(n) in seen:
            continue
        terms, todo = [], [n]
        while todo:
            t = todo.pop()
            if isinstance(t, ast.BinOp) and isinstance(t.op, (ast.Add, ast.Sub)):
                seen.add(id(t))
                todo += [t.left, t.right]
            else:
                terms.append(t.operand if isinstance(t, ast.UnaryOp) else t)
        products = [t for t in terms if isinstance(t, ast.BinOp) and isinstance(t.op, ast.Mult)
                    and any(isinstance(c, ast.Constant) for c in (t.left, t.right))]
        if len(products) >= _FIT_TERMS:
            out |= {id(c) for t in terms for c in ([t] if isinstance(t, ast.Constant) else [t.left, t.right] if isinstance(t, ast.BinOp) else [])
                    if isinstance(c, ast.Constant)}
    return out


def _source_names(tree) -> str:
    """Identifiers and docstrings of a file, to read what it says it implements."""
    words = [n.id for n in all_nodes(tree) if isinstance(n, ast.Name)]
    words += [n.value for n in all_nodes(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and len(n.value) < 2000]
    return " ".join(words)


def scan_constants(path: Path, tree, rel: str) -> list[Finding]:
    """Near-miss constants, one finding per constant and file, with the lines where they occur."""
    from .. import constants

    names = constants._assigned_names(tree)
    # numbers in long literal tables are data (measurements, reference values), not constants typed by hand
    tabulated = {id(e) for n in all_nodes(tree) if isinstance(n, (ast.List, ast.Tuple)) and len(n.elts) >= _TABLE_MIN
                 for e in n.elts}
    fitted = _fit_coefficients(tree)
    # the 1976 US Standard Atmosphere defines its own R* = 8.31432 J/(mol K) (corpus repo L168)
    standard_atm = bool(re.search(r"coesa|ussa|1976|standard[ _]atmosphere", Path(rel).name + " " + _source_names(tree), re.I))
    hits = {}
    for node in all_nodes(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool)):
            continue
        if id(node) in tabulated or id(node) in fitted:
            continue
        try:
            v = float(node.value)
        except OverflowError:
            continue
        hit = constants.check_value(abs(v), max_rel=0.1)
        if not hit:
            continue
        name, ref, r, comment = hit
        if name == "R (gas constant)" and standard_atm:
            continue
        assigned = names.get(id(node), set())
        short_int = isinstance(node.value, int) and constants._digits(v) < 6  # 149597870691 is no accident
        if name == "g" or short_int or constants._digits(v) < 3:
            if not assigned & constants.NAMES.get(name, set()):
                continue
        elif name in _PURE and abs(r) > _PURE_REL:
            continue
        elif name not in _PURE and abs(r) > _DIM_REL:
            continue  # 1.44e-19 is a test value, not a mistyped elementary charge
        if name in _DEFINED and abs(r) > (_DEFINED_REL / 10 if isinstance(node.value, int) else _DEFINED_REL):
            continue  # a definition typed wrong or taken from an old edition is close; 14666785333344 is not an au
        hits.setdefault((name, ast.unparse(node)), []).append((node.lineno, ref, r, comment))
    if len(hits) > _MANY_CONSTANTS:
        first = min(w[0][0] for w in hits.values())
        return [Finding("constants", NOTE, rel, first,
                        f"{len(hits)} different numbers in this file are close to physical constants; so many usually means"
                        " the file holds data (fits, tables, generated code), so they are not listed one by one", rule="PV302")]
    out = []
    for (name, literal), where in sorted(hits.items(), key=lambda kv: kv[1][0][0]):
        line, ref, r, comment = where[0]
        more = f" (also lines {', '.join(str(w[0]) for w in where[1:6])}{', ...' if len(where) > 6 else ''})" if len(where) > 1 else ""
        out.append(Finding("constants", NOTE, rel, line,
                           f"{literal} is {r:+.2g} relative to {name} ({ref:.10g}){more}; {comment}", rule="PV301"))
    return out
