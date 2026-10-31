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
              features, typo-like literals, unit tables with the wrong dimension (`physverify.lint`)

A finding is WARN (very likely a defect: a table that misses its claimed order, row sums that do not
match c, a spacing that does not match its grid) or NOTE (worth one look). A clean scan says only that
these patterns were not found.
"""

from __future__ import annotations

import ast
import math
import re
import warnings
from dataclasses import asdict, dataclass, field
from fractions import Fraction
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

    def __str__(self):
        return f"{self.level} {self.stage:9s} {self.path}:{self.line}: {self.message}"


def python_files(path) -> list[Path]:
    path = Path(path)
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*.py") if not SKIP_DIRS & set(p.relative_to(path).parts[:-1]))


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
_ORDER_HINT = re.compile(r"(\d)(?:st|nd|rd|th)[ -]order|(?:order|ord)[ _=:(]*(\d)|(?:^|[^a-z0-9])(?:rk|erk|irk|dirk|sdirk|esdirk)[ _-]?(\d)(?!\d)", re.I)
# Coefficients are often typed with 7 to 10 digits; a missing order shows residuals of 1e-4 or more.
_TOL = 1e-6
_NAMED = {"heun": 2, "midpoint": 2, "ralston": 2, "kutta3": 3, "ssprk3": 3, "rk38": 4, "three_eighths": 4,
          "classic": 4, "fehlberg": 4, "cash_karp": 5, "cashkarp": 5, "dopri": 5, "dormand": 5, "tsit": 5,
          "verner": 6, "bogacki": 3}


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


def _own_nodes(scope):
    """Nodes of a scope, without descending into nested functions or classes."""
    todo = list(ast.iter_child_nodes(scope))
    while todo:
        node = todo.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        yield node
        todo.extend(ast.iter_child_nodes(node))


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
    from .butcher import order_residuals, tableau_order

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
        found.append(Finding("tables", level, rel, line, f"{where}: " + "; ".join(msgs), table))
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


def _call_name(n) -> str:
    return n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")


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
    from .butcher import order_residuals, tableau_order

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
        found.append(Finding("tables", level, rel, line, f"{fn.name}: " + "; ".join(msgs), table))
    return found


# --- grid spacing ---------------------------------------------------------------------------------

def _src(node) -> str:
    return re.sub(r"\s+", "", ast.unparse(node))


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
                                     + ("" if rel_grid is None else "; different files, so check that they describe the same grid")))
    return found


def scan_grid(path: Path, tree, rel: str) -> list[Finding]:
    grids, divs = _grids_and_divs(tree)
    return _grid_findings(grids, divs, rel)


# --- inverse pairs --------------------------------------------------------------------------------

_PAIR = re.compile(r"^(?P<pre>.*?)(?P<x>[a-z0-9]+)(?P<sep>_to_|2)(?P<y>[a-z0-9]+)(?P<post>.*)$", re.I)


def scan_pairs(path: Path, tree, rel: str) -> list[Finding]:
    # test_x_to_y / test_y_to_x test an inverse pair; they are not converters to run
    funcs = {n.name: n.lineno for n in all_nodes(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("test")}
    found, seen = [], set()
    for fname, line in funcs.items():
        m = _PAIR.match(fname)
        if not m or m["x"].lower() == m["y"].lower():
            continue
        other = f"{m['pre']}{m['y']}{m['sep']}{m['x']}{m['post']}"
        if other in funcs and frozenset((fname, other)) not in seen:
            seen.add(frozenset((fname, other)))
            found.append(Finding("pairs", NOTE, rel, line,
                                 f"{fname} and {other} look like inverses: run"
                                 f" physverify.identities.check_roundtrip({fname}, {other}, inputs) on typical inputs"))
    return found


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
    from . import constants

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
                        " the file holds data (fits, tables, generated code), so they are not listed one by one")]
    out = []
    for (name, literal), where in sorted(hits.items(), key=lambda kv: kv[1][0][0]):
        line, ref, r, comment = where[0]
        more = f" (also lines {', '.join(str(w[0]) for w in where[1:6])}{', ...' if len(where) > 6 else ''})" if len(where) > 1 else ""
        out.append(Finding("constants", NOTE, rel, line,
                           f"{literal} is {r:+.2g} relative to {name} ({ref:.10g}){more}; {comment}"))
    return out


# --- driver ---------------------------------------------------------------------------------------

STAGES = ("constants", "tables", "grid", "pairs", "names", "api", "literals", "units")


def scan(path, *, stages=STAGES) -> tuple[list[Finding], list[str]]:
    """Findings for every Python file under `path`, and the files that could not be parsed."""
    from . import lint

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
                findings.append(lint.parse_finding(rel, exc, text))
            else:
                unparsed.append(f"{rel}: {type(exc).__name__}: {exc}")
            continue
        parsed.append((rel, tree))
        runs = (("constants", scan_constants), ("tables", scan_tables), ("tables", scan_code_tables),
                ("grid", scan_grid), ("pairs", scan_pairs), ("names", lambda f, t, r: lint.scan_names(f, t, r, text)), ("api", lint.scan_api),
                ("literals", lambda f, t, r: lint.scan_literals(f, t, r, text)), ("units", lint.scan_units))
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
                                 " not reported one by one"))
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
