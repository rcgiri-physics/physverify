"""Stage `grid`: a spacing (b - a) / N next to linspace(a, b, N), whose spacing is (b - a) / (N - 1) (PV201)."""

from __future__ import annotations

import ast
from pathlib import Path

from .common import NOTE, WARN, Finding, _own_nodes, _scopes, _src


def _names(node) -> set[str]:
    """Free names of an expression, with attributes by their last part (H.N -> N, self.extent -> extent)."""
    out, inner = set(), set()
    for n in ast.walk(node):
        if isinstance(n, ast.Attribute):
            out.add(n.attr)
            inner.add(id(n.value))
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and id(n) not in inner:
            out.add(n.id)
    return out


def _value(node, env):
    """Value of +, -, *, / expressions over names and attributes, with names taken from `env`; None if anything else."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        try:
            return float(node.value)
        except OverflowError:
            return None
    if isinstance(node, ast.Name):
        return env.get(node.id)
    if isinstance(node, ast.Attribute):
        return env.get(node.attr)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = _value(node.operand, env)
        return None if v is None else (-v if isinstance(node.op, ast.USub) else v)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv)):
        a, b = _value(node.left, env), _value(node.right, env)
        if a is None or b is None:
            return None
        if isinstance(node.op, ast.Add):
            return a + b
        if isinstance(node.op, ast.Sub):
            return a - b
        if isinstance(node.op, ast.Mult):
            return a * b
        try:
            return None if b == 0 else a / b
        except OverflowError:
            return None
    return None


def _same(x, y, names) -> bool | None:
    """Whether two expressions agree for three random assignments of their names (None if not computable)."""
    import random

    rng = random.Random(1)
    for _ in range(3):
        env = {n: rng.uniform(3.3, 97.7) for n in names}
        a, b = _value(x, env), _value(y, env)
        if a is None or b is None:
            return None
        if abs(a - b) > 1e-9 * max(1.0, abs(a), abs(b)):
            return False
    return True


def _constant_offset(x, y, names) -> bool:
    """x - y is the same number for random values of the names (so x and y differ by a constant)."""
    import random

    rng = random.Random(2)
    diffs = []
    for _ in range(3):
        env = {n: rng.uniform(3.3, 97.7) for n in names}
        a, b = _value(x, env), _value(y, env)
        if a is None or b is None:
            return False
        diffs.append(a - b)
    return max(diffs) - min(diffs) < 1e-9 * max(1.0, *map(abs, diffs))


def _grids_and_divs(tree):
    """linspace calls and divisions, each with the function (or class, or module) it is written in."""
    cached = getattr(tree, "_pv_grids", None)
    if cached is not None:
        return cached
    grids, divs = [], []
    for scope, _name, _doc in _scopes(tree):
        g, d = _own_grids_and_divs(scope)
        grids += [x + (id(scope),) for x in g]
        divs += [(x[0], x[1], id(scope), x[2]) for x in d]
    tree._pv_grids = (grids, divs)
    return grids, divs


def _own_grids_and_divs(scope):
    grids, divs = [], []
    nodes = list(_own_nodes(scope))
    # a division used as the step of a slice (np.mgrid[a:b:(b-a)/n], arange-style) builds its own grid
    steps = {id(n.step) for n in nodes if isinstance(n, ast.Slice) and n.step is not None}
    periodic = []  # linspace(a, b, M, endpoint=False): its spacing really is (b - a) / M
    for node in nodes:
        if id(node) in steps:
            continue
        if isinstance(node, ast.Call):
            fn = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if fn == "linspace" and len(node.args) >= 3:
                if any(k.arg == "endpoint" and isinstance(k.value, ast.Constant) and k.value.value is False
                       for k in node.keywords):
                    periodic.append(node.args[2])
                    continue
                grids.append((node.args[0], node.args[1], node.args[2], node.lineno))
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            den_names = _names(node.right)
            if den_names:  # x / 2 cannot be a grid spacing with a named number of points
                divs.append((node, node.lineno, den_names))
    # dd = (b - a) / n; linspace(a + dd/2, b - dd/2, n): cell centres, whose spacing really is (b - a) / n
    half = {_src(x.left) for node in nodes if isinstance(node, ast.Call)
            and (node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")) == "linspace"
            and node.args and isinstance(node.args[0], ast.BinOp) and isinstance(node.args[0].op, ast.Add)
            for x in [node.args[0].right] if isinstance(x, ast.BinOp) and isinstance(x.op, ast.Div)
            and isinstance(x.right, ast.Constant) and x.right.value == 2}
    if half:
        cell = {id(n.value) for n in nodes if isinstance(n, ast.Assign) and len(n.targets) == 1
                and _src(n.targets[0]) in half}
        divs = [d for d in divs if id(d[0]) not in cell]
    if periodic:
        # a spacing L / M next to its own periodic grid of M points is right; do not pair it with grids elsewhere
        divs = [d for d in divs if not any(_src(d[0].right) == _src(m) or _src(d[0].right) == f"({_src(m)})"
                                           for m in periodic)]
    return grids, divs


def _grid_findings(grids, divs, rel_div, rel_grid=None, seen=None) -> list[Finding]:
    """A division (b - a) / D that is a spacing of linspace(a, b, M) with D != M - 1 (one finding per division)."""
    found = []
    seen = set() if seen is None else seen
    for a, b, m, gline, gscope in grids:
        span = ast.BinOp(b, ast.Sub(), a)
        m_names = _names(m)
        if not m_names or not (_names(a) | _names(b)):
            continue  # linspace(0, 1, 101): nothing to mix up with a named N
        for div, dline, dscope, den_names in divs:
            num, den = div.left, div.right
            if not (den_names & m_names):
                continue
            names = _names(num) | _names(den) | m_names | _names(a) | _names(b)
            if _same(num, span, names) is not True:
                continue
            m1 = ast.BinOp(m, ast.Sub(), ast.Constant(1))
            ok = _same(den, m1, names)
            # D must be M - 1 give or take a constant (N vs N - 1, N - 1 vs N + 1 - 1); n against 100*n is another grid
            if ok is False and not _constant_offset(den, m1, names):
                continue
            if ok is False and id(div) not in seen:
                seen.add(id(div))
                width = _src(num) if isinstance(num, (ast.Name, ast.Attribute, ast.Constant)) else f"({_src(num)})"
                where = f" on line {gline}" if rel_grid is None else f" in {rel_grid}:{gline}"
                if rel_grid is None and gscope != dscope:
                    where += " (in another function, so check that they describe the same grid)"
                level = WARN if rel_grid is None and gscope == dscope else NOTE
                found.append(Finding("grid", level, rel_div, dline,
                                     f"spacing {_src(div)} with linspace({_src(a)}, {_src(b)}, {_src(m)}){where},"
                                     f" whose spacing is {width}/({_src(m)}-1)"
                                     + ("" if rel_grid is None else "; different files, so check that they describe the same grid"), rule="PV201"))
    return found


def scan_grid(path: Path, tree, rel: str) -> list[Finding]:
    grids, divs = _grids_and_divs(tree)
    return _grid_findings(grids, divs, rel)
