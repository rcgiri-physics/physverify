"""Probe `branches`: a result does not jump where the code switches formula (PV903)."""

from __future__ import annotations

import ast
import math
import re

from ..probing.common import _finite, _Fn, _names_in
from ..stages.common import NOTE, Finding


def _thresholds(f: _Fn):
    """`(param, threshold expression, line)` for comparisons like `if x < a` on a scalar parameter."""
    # `r = np.asarray(rho_m, float)` makes r stand for the parameter rho_m
    alias, locals_ = {}, set()
    for n in ast.walk(f.node):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                for e in ast.walk(t):
                    if isinstance(e, ast.Name):
                        locals_.add(e.id)
            v = n.value
            if (len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and isinstance(v, ast.Call) and v.args
                    and isinstance(v.args[0], ast.Name) and v.args[0].id in f.params
                    and re.search(r"(^|\.)(asarray|array|float|asanyarray|atleast_1d)$", ast.unparse(v.func))):
                alias[n.targets[0].id] = v.args[0].id
    locals_ -= set(f.params)
    found = []
    # any comparison: `if`, `np.where` and masks such as `inside = r <= d / 2; out[inside] = ...` (J400)
    for c in ast.walk(f.node):
        if isinstance(c, ast.Compare) and len(c.ops) == 1 and isinstance(c.ops[0], (ast.Lt, ast.LtE, ast.Gt, ast.GtE)):
            left, right = c.left, c.comparators[0]
            for a, b in ((left, right), (right, left)):
                name = alias.get(a.id, a.id) if isinstance(a, ast.Name) else None
                if name in f.params and not (isinstance(b, ast.Name) and b.id == a.id) and not _names_in(b) & locals_:
                    found.append((name, b, c.lineno))
    return found


def _probe_branches(f, args, y0, out, rel):
    import numpy as np

    seen = set()
    for p, expr, line in _thresholds(f):
        v = args.get(p)
        if not isinstance(v, float) or (p, ast.unparse(expr)) in seen:  # integers switch formula by design
            continue
        seen.add((p, ast.unparse(expr)))
        try:
            a = float(eval(compile(ast.Expression(expr), "<threshold>", "eval"), vars(f.module), dict(args)))  # noqa: S307
        except Exception:  # noqa: BLE001 - thresholds that need local variables are not probed
            continue
        if not math.isfinite(a):
            continue
        d = 1e-7 * max(abs(a), 1.0)
        try:
            ys = [f.call({**args, p: a + k * d})[0] for k in (-2, -1, 1, 2)]
        except Exception:  # noqa: BLE001
            continue
        if any(y is None or not _finite(y) or y.shape != ys[0].shape for y in ys):
            continue
        jump = np.max(np.abs(ys[2] - ys[1]))
        slope = max(np.max(np.abs(ys[1] - ys[0])), np.max(np.abs(ys[3] - ys[2])))
        scale = max(np.max(np.abs(ys[1])), np.max(np.abs(ys[2])), 1e-300)
        if jump > 1e-6 * scale and jump > 100 * slope:
            out.append(Finding("branches", NOTE, rel, line,
                               f"{f.name}: the result jumps by {jump:.3g} (relative {jump / scale:.2g}) as {p} crosses"
                               f" {ast.unparse(expr)} = {a:.6g}, where the code switches formula; a physical quantity"
                               " should be continuous there unless the model has a real step", rule="PV903"))
