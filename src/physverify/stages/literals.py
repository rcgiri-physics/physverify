"""Stage `literals`: arithmetic that looks like a typo, and comparisons that are always false (PV601 to PV605)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from .common import WARN, Finding, _aliases, all_nodes

# --- literals ---------------------------------------------------------------------------------------

# 1e0 - 5: a number written with the exponent 0, then a small integer added or taken away (1e-99 + 1 is deliberate)
_E_TYPO = re.compile(r"^\s*(\d+(?:\.\d*)?)[eE]([+-]?0+)\s*([-+])\s*(\d{1,2})\s*$")


def _is_test(path: Path) -> bool:
    return path.name.startswith("test_") or path.name.endswith("_test.py") or "tests" in path.parts or "testsuite" in path.parts


def scan_literals(path: Path, tree, rel: str, source: str) -> list[Finding]:
    out = []
    testing = _is_test(path)  # tests compare with NaN on purpose, to check that the comparison is false
    np_names = _aliases(tree, "numpy") | {"math"}
    for n in all_nodes(tree):
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub)) \
                and isinstance(n.left, ast.Constant) and isinstance(n.right, ast.Constant):
            text = ast.get_source_segment(source, n) or ""
            m = _E_TYPO.match(text)
            if m and isinstance(n.right.value, int):
                meant = f"{m.group(1)}e{m.group(3)}{n.right.value}"
                a, b = n.left.value, n.right.value
                value = a - b if isinstance(n.op, ast.Sub) else a + b
                out.append(Finding("literals", WARN, rel, n.lineno,
                                   f"{text.strip()} is {value:g}; if {meant} was meant, the operator is inside the number", rule="PV601"))
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitXor) and isinstance(n.right, ast.Constant) \
                and n.right.value in (2, 3) and not isinstance(n.left, ast.Constant):
            text = ast.get_source_segment(source, n) or ""
            out.append(Finding("literals", WARN, rel, n.lineno,
                               f"{text.strip()}: ^ is exclusive or in Python, not a power (use **)", rule="PV602"))
        # A literal list, tuple, number or string indexed with a tuple, or called, raises TypeError when the line
        # runs; it is nearly always a lost comma or a lost name (corpus repo L313: `[c[0][...], [0][0,0,:,:]]`).
        # CPython warns about the same cases at compile time, but only when the file is compiled, and the warning
        # is easy to miss.
        literal = (ast.List, ast.Tuple, ast.Constant, ast.ListComp, ast.Dict, ast.Set)
        if isinstance(n, ast.Subscript) and isinstance(n.value, literal) and not isinstance(n.value, ast.Dict) \
                and (isinstance(n.slice, ast.Tuple) or (isinstance(n.value, (ast.List, ast.Tuple, ast.ListComp))
                                                        and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str))):
            text = ast.get_source_segment(source, n) or ""
            out.append(Finding("literals", WARN, rel, n.lineno,
                               f"{text.strip()[:60]}: indexing a literal {type(n.value).__name__.lower()} with a tuple or"
                               " string raises TypeError; a comma or a name is probably missing", rule="PV603"))
        if isinstance(n, ast.Call) and isinstance(n.func, literal) \
                and not (isinstance(n.func, ast.Constant) and n.func.value is None):
            text = ast.get_source_segment(source, n) or ""
            out.append(Finding("literals", WARN, rel, n.lineno,
                               f"{text.strip()[:60]}: a literal is called, which raises TypeError;"
                               " a comma is probably missing between two items", rule="PV604"))
        if isinstance(n, ast.Compare):
            for op, right in zip(n.ops, n.comparators):
                for side in (n.left, right):
                    if not testing and isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(side, ast.Attribute) \
                            and side.attr in ("nan", "NaN", "NAN") and getattr(side.value, "id", None) in np_names:
                        out.append(Finding("literals", WARN, rel, n.lineno,
                                           f"comparison with {side.value.id}.{side.attr} is {'never' if isinstance(op, ast.Eq) else 'always'}"
                                           " true (NaN equals nothing); use np.isnan", rule="PV605"))
    return out
