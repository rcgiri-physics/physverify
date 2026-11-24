"""Stage `tables`: Runge-Kutta tables written as literals, checked against their claimed order (PV101)."""

from __future__ import annotations

import ast
import math
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
    _scopes,
    all_nodes,
)

# --- numeric literals -----------------------------------------------------------------------------

_FUNCS = {"sqrt": math.sqrt, "Fraction": Fraction, "float": float, "mpf": float, "Rational": Fraction,
          "exp": math.exp, "log": math.log}


def _num(node):
    """Value of a numeric expression made of literals (1/3, sqrt(6), Fraction(1, 6), -0.5), else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        text = node.value.strip()
        if len(text) > 40 or not re.fullmatch(r"[-+]?\d+(\.\d*)?(/\d+)?", text):
            return None  # only "1/3"-style strings, as some tables are written; never huge exponents
        try:
            return float(Fraction(text))
        except (ValueError, ZeroDivisionError, OverflowError):
            return None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = _num(node.operand)
        return None if v is None else (-v if isinstance(node.op, ast.USub) else v)
    if isinstance(node, ast.BinOp):
        a, b = _num(node.left), _num(node.right)
        if a is None or b is None or isinstance(a, list) or isinstance(b, list):
            return None
        try:
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            if isinstance(node.op, ast.Div):
                return a / b
            if isinstance(node.op, ast.Pow) and abs(float(b)) <= 4:
                return float(a) ** float(b)
        except (ZeroDivisionError, OverflowError, ValueError):
            return None
        return None
    if isinstance(node, ast.Call):
        name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        if name in ("array", "asarray", "matrix", "tuple", "list", "tensor", "Tensor", "as_tensor") and len(node.args) == 1:
            return _array(node.args[0])
        if name in _FUNCS and node.args and not node.keywords:
            args = [_num(a) for a in node.args]
            if all(a is not None for a in args):
                try:
                    return float(_FUNCS[name](*args))
                except (ValueError, ZeroDivisionError, TypeError):
                    return None
    return None


def _array(node):
    """A list/tuple literal of numbers (or of such lists) as nested Python lists of floats, else None."""
    if isinstance(node, ast.Call):
        v = _num(node)
        return v if isinstance(v, list) else None
    if not isinstance(node, (ast.List, ast.Tuple)) or not node.elts:
        return None
    out = []
    for e in node.elts:
        v = _array(e) if isinstance(e, (ast.List, ast.Tuple, ast.Call)) else _num(e)
        if v is None:
            return None
        out.append(v if isinstance(v, list) else float(v))
    return out


# --- Butcher tables --------------------------------------------------------------------------------

_A_NAMES = re.compile(r"^(a|a_?mat|a_?matrix|butcher(_a)?|tableau(_a)?|coef(f)?s?_?a|aij|rk_?a)$", re.I)
_B_NAMES = re.compile(r"^(b|b_?sol|b_?vec|weights?|bs?_?high|b_?main|rk_?b)$", re.I)
_C_NAMES = re.compile(r"^(c|c_?vec|nodes?|rk_?c)$", re.I)
_E_NAMES = re.compile(r"^(e|err|b_?err(or)?|e_?vec|btilde|b_?tilde|b_?diff|d|db|b_?e|e_?weights)$", re.I)
_BHAT_NAMES = re.compile(r"^(bhat|b_?hat|b_?star|bs|b_?low|b_?emb(edded)?|b2|b_?alt)$", re.I)


def _square_lower(m) -> bool:
    if not isinstance(m, list) or len(m) < 2 or not all(isinstance(r, list) for r in m):
        return False
    s = len(m)
    if any(len(r) != s or any(isinstance(x, list) for x in r) for r in m):
        return False
    diagonal = all(m[i][j] == 0 for i in range(s) for j in range(i + 1, s))  # explicit or diagonally implicit
    return diagonal or s <= 6  # fully implicit tables are accepted only when small, to keep false matches rare


def _vector(v, s) -> bool:
    return isinstance(v, list) and len(v) == s and not any(isinstance(x, list) for x in v)


def _stated_order(scope, what="order"):
    """An order the code itself states: `order = 4` in the scope, or `def order(self): return 4` in a class.

    `what="orderembedded"` reads the order stated for the embedded weights the same way."""
    for node in getattr(scope, "body", []):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id.lower().replace("_", "") == what
                                                for t in node.targets):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, int):
                return node.value.value
        if isinstance(node, ast.FunctionDef) and node.name.lower().replace("_", "") == what:
            rets = [n for n in ast.walk(node) if isinstance(n, ast.Return)]
            if len(rets) == 1 and isinstance(rets[0].value, ast.Constant) and isinstance(rets[0].value.value, int):
                return rets[0].value.value
    return None


def _zeros(node):
    """np.zeros((s, s)) or np.zeros(s) with a literal size, as nested lists; else None."""
    if not (isinstance(node, ast.Call) and _call_name(node) in ("zeros", "zeros_like") and node.args):
        return None
    shape = node.args[0]
    dims = [d.value for d in (shape.elts if isinstance(shape, ast.Tuple) else [shape])
            if isinstance(d, ast.Constant) and isinstance(d.value, int)]
    if len(dims) == 1 and 1 <= dims[0] <= 32:
        return [0.0] * dims[0]
    if len(dims) == 2 and dims[0] == dims[1] and 1 <= dims[0] <= 32:
        return [[0.0] * dims[0] for _ in range(dims[0])]
    return None


def _set_element(out, target, value):
    """Apply A[i, j] = v, A[i, :k] = [...] or A[i] = [...] to a table in `out`; drop the table if not understood."""
    name = target.value.id if isinstance(target.value, ast.Name) else None
    if name not in out or not out[name][0] or not isinstance(out[name][0][0], list):
        return
    m, line = out[name]
    idx = target.slice.elts if isinstance(target.slice, ast.Tuple) else [target.slice]
    row = _num(idx[0])
    if not isinstance(row, (int, float)) or int(row) != row or not 0 <= int(row) < len(m):
        out.pop(name)
        return
    r = int(row)
    whole = len(idx) == 1 or (isinstance(idx[1], ast.Slice) and idx[1].lower is None and idx[1].step is None)
    if whole:
        vals = _array(value)
        stop = _num(idx[1].upper) if len(idx) == 2 and idx[1].upper is not None else len(m)
        if not isinstance(vals, list) or any(isinstance(x, list) for x in vals) or stop != len(vals):
            out.pop(name)
            return
        m[r][:len(vals)] = vals
    else:
        col, v = _num(idx[1]), _num(value)
        if not isinstance(col, (int, float)) or not isinstance(v, (int, float)) or not 0 <= int(col) < len(m):
            out.pop(name)
            return
        m[r][int(col)] = float(v)
    out[name] = (m, line)


def _assignments(scope):
    """name -> (value, line) for literal assignments directly in this scope (not in nested defs)."""
    out = {}
    body = list(getattr(scope, "body", []))
    while body:
        node = body.pop(0)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
            for field in ("body", "orelse", "finalbody", "handlers"):
                body.extend(getattr(node, field, []) or [])
            continue
        if isinstance(node, ast.ExceptHandler):
            body.extend(node.body)
            continue
        targets, value = [], None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Subscript):
            _set_element(out, node.targets[0], node.value)  # A[1, :2] = [...] after A = np.zeros((s, s))
            continue
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        for t in targets:
            name = t.id if isinstance(t, ast.Name) else (t.attr if isinstance(t, ast.Attribute) else None)
            if name is None:
                continue
            v = _array(value)
            if v is None:
                v = _zeros(value)
            if v is None and isinstance(value, ast.Subscript) and isinstance(value.value, ast.Name):
                # b = A[-1] (a stiffly accurate method: the weights are the last row)
                m, i = out.get(value.value.id, (None, None))[0], _num(value.slice)
                if isinstance(m, list) and m and isinstance(m[0], list) and isinstance(i, (int, float)) \
                        and int(i) == i and -len(m) <= int(i) < len(m):
                    v = list(m[int(i)])
            if v is not None:
                out[name] = (v, node.lineno)
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple):
            # return A, b, c  (a table factory)
            vals = [_array(e) for e in node.value.elts]
            for name, v in zip(("<A>", "<b>", "<c>", "<e>"), vals):
                if v is not None:
                    out.setdefault(name, (v, node.lineno))
    return out


def _check_table(lits, name, doc, stem, stated, rel, *, kind="table", stated_embedded=None):
    """Findings for every Butcher table among the literal arrays `lits` (name -> (value, line))."""
    from ..butcher import order_residuals, tableau_order

    found = []
    for an, (A, line) in lits.items():
        if not (_A_NAMES.match(an) or an == "<A>") or not _square_lower(A):
            continue
        s = len(A)
        bn = next((n for n in lits if (_B_NAMES.match(n) or n == "<b>") and _vector(lits[n][0], s)), None)
        if bn is None:
            continue
        b = lits[bn][0]
        if abs(sum(b) - 1) > 1e-6:
            continue  # not a set of weights, so probably not a Butcher table
        try:
            p = tableau_order(A, b, max_order=6, tol=_TOL)
            res = order_residuals(A, b, 6)
        except Exception:  # noqa: BLE001 - a malformed table is just not a table
            continue
        where = f"{kind} {an}/{bn} ({s} stages" + (f", in {name}" if name else "") + ")"
        msgs, level = [f"satisfies the order conditions up to order {p}"], NOTE
        cn = next((n for n in lits if (_C_NAMES.match(n) or n == "<c>") and _vector(lits[n][0], s)), None)
        if cn is not None:
            dev = max(abs(sum(row) - ci) for row, ci in zip(A, lits[cn][0]))
            if dev > _TOL:
                level = WARN
                i = max(range(s), key=lambda k: abs(sum(A[k]) - lits[cn][0][k]))
                msgs.append(f"row {i} of A sums to {sum(A[i]):.10g} but {cn}[{i}] = {lits[cn][0][i]:.10g}")
        if stated is not None:
            claimed, why = stated, f"order {stated} stated in the code"
        else:
            claimed, why = _claimed_order(f"{name} {doc} {stem}")
        if claimed is not None and claimed <= 6:
            if p < claimed:
                level = WARN
                worst = max(r for q, r in res.items() if p < q <= claimed)
                msgs.append(f"but '{why}' suggests order {claimed} (largest residual {worst:.1e}); check with"
                            f" physverify.butcher.check_tableau(A, b, c, claimed={claimed})")
            else:
                msgs.append(f"consistent with '{why}'")
        for en, (e, eline) in lits.items():
            if (_E_NAMES.match(en) or en == "<e>") and _vector(e, s) and en != bn:
                if abs(sum(e)) > 1e-8 and abs(sum(e) - 1) > 1e-8:
                    level = WARN
                    msgs.append(f"error weights {en} (line {eline}) sum to {sum(e):.6g}; the difference of two"
                                " weight vectors must sum to 0")
                elif abs(sum(e)) <= 1e-8:
                    bhat = [x - y for x, y in zip(b, e)]
                    msgs.append(f"embedded solution b - {en} has order {tableau_order(A, bhat, max_order=6, tol=_TOL)}")
            if _BHAT_NAMES.match(en) and _vector(e, s) and en != bn:
                if abs(sum(e) - 1) > 1e-8:
                    level = WARN
                    msgs.append(f"embedded weights {en} (line {eline}) sum to {sum(e):.6g} instead of 1")
                else:
                    pe = tableau_order(A, e, max_order=6, tol=_TOL)
                    if stated_embedded is not None and pe != stated_embedded:
                        level = WARN
                        msgs.append(f"embedded weights {en} have order {pe}, but order {stated_embedded} is stated")
                    else:
                        msgs.append(f"embedded weights {en} have order {pe}")
        table = {"name": name, "kind": kind, "A": A, "b": b, "c": lits[cn][0] if cn is not None else None,
                 "claimed": claimed if claimed is not None and claimed <= 6 else None, "claim_source": why,
                 "stated_embedded": stated_embedded,
                 "embedded": {en: e for en, (e, _l) in lits.items() if _BHAT_NAMES.match(en) and _vector(e, s) and en != bn},
                 "error_weights": {en: e for en, (e, _l) in lits.items()
                                   if (_E_NAMES.match(en) or en == "<e>") and _vector(e, s) and en != bn},
                 "order": p}
        found.append(Finding("tables", level, rel, line, f"{where}: " + "; ".join(msgs), table, rule="PV101"))
    return found


def _keyword_group(node):
    """A table passed as keywords (ButcherTableau(a=..., b=..., order=5)) or as a dict ({"A": ..., "b": ...})."""
    pairs, label = [], ""
    if isinstance(node, ast.Call) and node.keywords:
        pairs = [(k.arg, k.value) for k in node.keywords if k.arg]
        label = _call_name(node)
    elif isinstance(node, ast.Dict):
        pairs = [(k.value, v) for k, v in zip(node.keys, node.values)
                 if isinstance(k, ast.Constant) and isinstance(k.value, str)]
        label = "dict"
    if len(pairs) < 2:
        return None
    lits, stated = {}, None
    for key, value in pairs:
        if key.lower() == "order" and isinstance(value, ast.Constant) and isinstance(value.value, int):
            stated = value.value
            continue
        v = _array(value)
        if v is not None:
            lits[key] = (v, value.lineno)
    return (lits, label, stated) if len(lits) >= 2 else None


def _class_attrs(cls, classes, seen=()):
    """Literal attributes and stated orders of a class, over those of its base classes in the same file."""
    lits, order, emb = {}, None, None
    for base in cls.bases:
        bname = base.id if isinstance(base, ast.Name) else None
        if bname in classes and bname not in seen:
            bl, bo, be = _class_attrs(classes[bname], classes, seen + (cls.name,))
            lits.update(bl)
            order = bo if bo is not None else order
            emb = be if be is not None else emb
    lits.update(_assignments(cls))
    mine, mine_emb = _stated_order(cls), _stated_order(cls, "orderembedded")
    return lits, (mine if mine is not None else order), (mine_emb if mine_emb is not None else emb)


def scan_tables(path: Path, tree, rel: str) -> list[Finding]:
    found = []
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    for scope, name, doc in _scopes(tree):
        if isinstance(scope, ast.ClassDef) and scope.name in classes:
            own = _assignments(scope)
            stated_here = _stated_order(scope) is not None or _stated_order(scope, "orderembedded") is not None
            if not own and not stated_here:
                continue  # nothing of its own: the base class reports the table
            lits, stated, emb = _class_attrs(scope, classes)
            found += _check_table(lits, name, doc, path.stem, stated, rel, stated_embedded=emb)
            continue
        found += _check_table(_assignments(scope), name, doc, path.stem, _stated_order(scope), rel)
    # the function each call sits in gives the name and docstring (def Tsit5(): return ButcherTableau(...))
    owner, todo = {}, [(tree, None)]
    while todo:  # innermost enclosing function or class of every node, in one pass
        node, fn = todo.pop()
        owner[id(node)] = fn
        inner = node if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else fn
        todo.extend((child, inner) for child in ast.iter_child_nodes(node))
    for node in all_nodes(tree):
        if not isinstance(node, (ast.Call, ast.Dict)):
            continue
        group = _keyword_group(node)
        if group is None:
            continue
        lits, label, stated = group
        fn = owner.get(id(node))
        name = fn.name if fn is not None else label
        doc = (ast.get_docstring(fn) or "") if fn is not None else ""
        found += _check_table(lits, name, doc, path.stem, stated, rel, kind=f"{label}(...)")
    return found
