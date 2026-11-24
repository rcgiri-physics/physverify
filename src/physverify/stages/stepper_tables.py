"""Stage `tables`: Runge-Kutta steppers whose stages are written as code, read back into a table (PV102)."""

from __future__ import annotations

import ast
import re
from fractions import Fraction
from pathlib import Path

from .common import (
    _TOL,
    NOTE,
    WARN,
    Finding,
    _call_name,
    _claimed_order,
    _src,
    all_nodes,
)

# --- Runge-Kutta stages written as code -----------------------------------------------------------
#
# Many codes never write a table: they write the stages, `k2 = h*f(t + h/2, y + k1/2)`. The stages are
# read here as linear combinations: each call of the right-hand side is a new stage F_i, and every other
# expression is a sum of terms coefficient * h^p * basis, where a basis is a stage, or any other name or
# subscript (the state y[n], the time t). A and c follow from the stage arguments, b from the update.

_NOT_RHS = {"zeros", "zeros_like", "ones", "array", "asarray", "empty", "size", "len", "range", "sqrt", "exp",
            "sin", "cos", "abs", "sum", "dot", "max", "min", "norm", "copy", "append", "print", "float", "int",
            "reshape", "linspace", "arange", "concatenate", "stack", "where", "clip", "isinstance", "enumerate",
            "format", "join", "get", "setdefault", "update", "power", "maximum", "minimum", "full", "matmul"}
_OPAQUE = "opaque"  # a factor that is not part of the method, such as a change of variables


class _Lin:
    """sum of coefficient * h^p * basis; the basis "" is a plain number."""

    def __init__(self, terms=None):
        self.terms = {k: v for k, v in (terms or {}).items() if v != 0}

    @staticmethod
    def const(v, p=0):
        return _Lin({("", p): float(v)})

    def scalar(self) -> bool:
        return all(b == "" for b, _p in self.terms)

    def __add__(self, o):
        t = dict(self.terms)
        for k, v in o.terms.items():
            t[k] = t.get(k, 0.0) + v
        return _Lin(t)

    def scale(self, o):
        """Product with a plain number (o.scalar())."""
        t = {}
        for (b, p), v in self.terms.items():
            for (_b, q), w in o.terms.items():
                t[(b, p + q)] = t.get((b, p + q), 0.0) + v * w
        return _Lin(t)


class _Stages:
    def __init__(self, rhs: str, hname: str):
        self.rhs, self.h = rhs, hname
        self.calls = []        # argument forms of each stage, in order
        self.env = {}          # name -> form
        self.updates = []      # (target, form, line) of combinations made after a stage

    def eval(self, node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            try:
                return _Lin.const(float(node.value))
            except OverflowError:
                return None
        if isinstance(node, ast.Name):
            if node.id == self.h:
                return _Lin.const(1.0, 1)
            return self.env.get(node.id) or _Lin({(node.id, 0): 1.0})
        if isinstance(node, (ast.Subscript, ast.Attribute)):
            return _Lin({(_src(node), 0): 1.0})
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            v = self.eval(node.operand)
            if not isinstance(v, _Lin):
                return v
            return v.scale(_Lin.const(-1.0)) if isinstance(node.op, ast.USub) else v
        if isinstance(node, ast.Call):
            fn = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if fn == self.rhs:
                args = [self.eval(a) for a in node.args]
                if any(not isinstance(a, _Lin) for a in args):
                    return None
                self.calls.append(args)
                return _Lin({(f"F{len(self.calls) - 1}", 0): 1.0})
            return _OPAQUE
        if isinstance(node, ast.BinOp):
            a, b = self.eval(node.left), self.eval(node.right)
            if a is None or b is None:
                return None
            if isinstance(node.op, (ast.Add, ast.Sub)):
                if _OPAQUE in (a, b):
                    return None
                return a + (b.scale(_Lin.const(-1.0)) if isinstance(node.op, ast.Sub) else b)
            if isinstance(node.op, ast.Mult):
                if a == _OPAQUE or b == _OPAQUE:
                    other = b if a == _OPAQUE else a
                    return None if other == _OPAQUE else other
                if b.scalar():
                    return a.scale(b)
                if a.scalar():
                    return b.scale(a)
                return None
            if isinstance(node.op, ast.Div) and _OPAQUE not in (a, b) and b.scalar() and len(b.terms) == 1:
                ((_, p), v), = b.terms.items()
                return a.scale(_Lin.const(1.0 / v, -p))
            return None
        return None

    def run(self, body):
        for node in body:
            if isinstance(node, (ast.For, ast.While, ast.With, ast.If)):
                self.run(node.body)
                continue
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target, value = node.targets[0], node.value
            elif isinstance(node, ast.AugAssign):
                target, value = node.target, ast.BinOp(node.target, node.op, node.value)
            elif isinstance(node, ast.Return) and node.value is not None:
                target, value = None, node.value
            else:
                continue
            values = value.elts if isinstance(value, ast.Tuple) else [value]
            for v in values:
                before = len(self.calls)
                lin = self.eval(v)
                if not isinstance(lin, _Lin):
                    continue
                if isinstance(target, ast.Name) and len(values) == 1:
                    self.env[target.id] = lin
                if len(self.calls) == before and self.calls:
                    self.updates.append(("return" if target is None else _src(target), lin, node.lineno))


def _rhs_name(fn) -> str | None:
    """The function called once per stage: the most frequent call with at least two arguments, twice or more."""
    counts = {}
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and len(n.args) >= 2:
            name = _call_name(n)
            if name and name not in _NOT_RHS:
                counts[name] = counts.get(name, 0) + 1
    best = max(counts.items(), key=lambda kv: kv[1], default=(None, 0))
    return best[0] if best[1] >= 2 else None


_STEP_NAMES = ("h", "dt", "dx", "tau", "step", "hh", "delta_t", "ds", "dh")


def _step_name(fn, rhs) -> str | None:
    """The step size: a step-like name multiplied into the arguments of the stages."""
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and _call_name(n) == rhs:
            for a in n.args:
                for m in ast.walk(a):
                    if isinstance(m, ast.BinOp) and isinstance(m.op, (ast.Mult, ast.Div)):
                        for side in (m.left, m.right):
                            if isinstance(side, ast.Name) and side.id.lower() in _STEP_NAMES:
                                return side.id
    for a in fn.args.args:
        if a.arg.lower() in _STEP_NAMES:
            return a.arg
    for n in ast.walk(fn):  # h = x[1] - x[0]
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            if n.targets[0].id.lower() in _STEP_NAMES:
                return n.targets[0].id
    return None


def _split(lin: _Lin, s: int):
    """{(stage, power of h): coefficient} and the other terms of a form."""
    stages, other = {}, {}
    for (b, p), v in lin.terms.items():
        if re.fullmatch(r"F\d+", b) and int(b[1:]) < s:
            stages[(int(b[1:]), p)] = v
        else:
            other[(b, p)] = v
    return stages, other


def _docstring_table(doc: str):
    """A Butcher table drawn in a docstring ("1/2 | 1/2 0" rows and a "| b1 b2" row) as (A, b, c), or None."""
    rows, b, cs = [], None, []
    for line in doc.splitlines():
        if "|" not in line or set(line.strip()) <= set("-|=_ "):
            continue
        left, right = line.split("|", 1)
        try:
            nums = [float(Fraction(x)) for x in right.split()]
            c = float(Fraction(left.strip())) if left.strip() else None
        except (ValueError, ZeroDivisionError):
            return None
        if not nums:
            continue
        if c is None:
            b = nums
        else:
            rows.append(nums)
            cs.append(c)
    if b is None or not rows or len(rows) != len(b) or any(len(r) != len(b) for r in rows):
        return None
    return rows, b, cs


def _code_table(fn):
    """(A, b, c or None, odd combinations, line of the update) for a function whose stages are written as code."""
    rhs = _rhs_name(fn)
    hname = _step_name(fn, rhs) if rhs else None
    if hname is None:
        return None
    st = _Stages(rhs, hname)
    try:
        st.run(fn.body)
    except RecursionError:
        return None
    s = len(st.calls)
    if not 2 <= s <= 16:
        return None
    nargs = min(len(c) for c in st.calls)
    carriers = [j for j in range(nargs) if any(_split(c[j], s)[0] for c in st.calls[1:])]
    if len(carriers) != 1:
        return None  # no stage feeds another, or a system split into parts (y and z, x and v): not read here
    state_ix = carriers[0]
    if any(p >= 2 for call in st.calls for (_j, p) in _split(call[state_ix], s)[0]):
        return None  # h^2 terms: one part of a split system feeds the other
    time_ix = next((j for j in range(nargs) if j != state_ix and any(("", 1) in c[j].terms for c in st.calls)), None)
    at_start = time_ix is None and nargs == 2  # f(t, y) with no h in any time: every stage at t, or f(y, params)
    # y + h*(a21*k1): earlier stages enter a stage at h^1, whether k = h*f or k = f
    no_h = [i + 1 for i, call in enumerate(st.calls) if any(p == 0 for (_j, p) in _split(call[state_ix], s)[0])]
    if len(no_h) > s // 2:
        return None
    A, c = [[0.0] * s for _ in range(s)], [None] * s
    for i, call in enumerate(st.calls):
        for (j, _p), v in _split(call[state_ix], s)[0].items():
            if j >= i:
                return None  # implicit, or out of order: not handled here
            A[i][j] = v
        if time_ix is not None:
            c[i] = call[time_ix].terms.get(("", 1), 0.0)
        elif at_start:
            c[i] = 0.0
    b, line, odd = None, fn.lineno, []
    for target, lin, uline in st.updates:
        coeffs = _split(lin, s)[0]
        if len({j for j, _p in coeffs}) < max(2, s - 2):
            continue
        w = [sum(v for (j, _p), v in coeffs.items() if j == k) for k in range(s)]
        total = sum(w)
        if b is None and abs(total - 1) < 1e-6:
            b, line = w, uline
        elif abs(total) > 1e-6 and abs(total - 1) > 1e-6:
            odd.append((target, uline, total))
    if b is None:
        return None
    return A, b, (c if all(x is not None for x in c) else None), odd, line, no_h, at_start


def scan_code_tables(path: Path, tree, rel: str) -> list[Finding]:
    from ..butcher import order_residuals, tableau_order

    found = []
    for fn in all_nodes(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        names = [_call_name(n) for n in ast.walk(fn) if isinstance(n, ast.Call) and len(n.args) >= 2]
        if len(names) - len(set(names)) < 1:
            continue  # no function is called twice with two or more arguments: no stages to read
        got = _code_table(fn)
        if got is None:
            continue
        A, b, c, odd, line, no_h, c_guessed = got
        s = len(b)
        try:
            p = tableau_order(A, b, max_order=6, tol=_TOL)
            res = order_residuals(A, b, 6)
        except Exception:  # noqa: BLE001 - not a usable table after all
            continue
        level, msgs = NOTE, [f"stages written as code: {s} stages, order {p} from the order conditions"]
        if no_h:
            level = WARN
            msgs.append(f"stage{'s' if len(no_h) > 1 else ''} {', '.join(map(str, no_h))} add earlier stages without"
                        " the step size h (y + a*k1 where y + h*a*k1 is meant, or the reverse)")
        doc = ast.get_docstring(fn) or ""
        drawn = _docstring_table(doc)
        if c is not None and c_guessed:
            # no h in any argument: compare the times only with a table that states them
            c = c if drawn is not None and len(drawn[2]) == s and any(drawn[2]) else None
        if c is not None:
            i = max(range(s), key=lambda k: abs(sum(A[k]) - c[k]))
            if abs(sum(A[i]) - c[i]) > _TOL:
                level = WARN
                msgs.append(f"stage {i + 1} is evaluated at t + {c[i]:.6g} h but its weights sum to {sum(A[i]):.6g}")
        for target, uline, total in odd:
            level = WARN
            msgs.append(f"{target} (line {uline}) combines the stages with weights summing to {total:.6g};"
                        " a solution needs 1 and an error estimate 0")
        if drawn is not None and len(drawn[1]) == s:
            dA, db, _dc = drawn
            worst = max([abs(x - y) for r1, r2 in zip(A, dA) for x, y in zip(r1, r2)] + [abs(x - y) for x, y in zip(b, db)])
            if worst > _TOL:
                level = WARN
                msgs.append(f"differs from the Butcher table in its docstring by up to {worst:.3g}")
            else:
                msgs.append("matches the Butcher table in its docstring")
        claimed, why = _claimed_order(f"{fn.name} {doc.splitlines()[0] if doc else ''}")
        if claimed is not None and claimed <= 6:
            if p < claimed:
                level = WARN
                worst = max(r for q, r in res.items() if p < q <= claimed)
                msgs.append(f"but '{why}' suggests order {claimed} (largest residual {worst:.1e})")
            else:
                msgs.append(f"consistent with '{why}'")
        table = {"name": fn.name, "kind": "stages written as code", "A": A, "b": b, "c": c,
                 "claimed": claimed if claimed is not None and claimed <= 6 else None, "claim_source": why,
                 "stated_embedded": None, "embedded": {}, "error_weights": {}, "order": p,
                 "docstring_table": {"A": drawn[0], "b": drawn[1]} if drawn is not None and len(drawn[1]) == s else None}
        found.append(Finding("tables", level, rel, line, f"{fn.name}: " + "; ".join(msgs), table, rule="PV102"))
    return found
