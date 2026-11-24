"""Static checks of `physverify scan` about the order of statements in a function (stage "flow").

Each rule comes from one bug found in the corpus study (issue #46):

- unbound    a local assigned only inside an `if` with no `else` and read after it, so the other branch
             raises UnboundLocalError (a charge-density routine that crashed on one plane)
- alias      `A = B` for an array, then `A` changed in place, then `B` read again: `A` is the same array,
             so `B` changed too (an RK2 written this way advanced 1.5 dt per step)
- spacing    a west/south coefficient (`uw`, `DW`) built only from east/north spacings (`DXe`, `DYn`);
             invisible on a uniform grid, wrong on a stretched one
- numba      `@jit("f8(f8)")` / `@njit(signature)` on a function that calls SciPy, which numba cannot type;
             an eager signature compiles at import, and since numba 0.59 there is no object-mode fallback
- factorial2 `factorial2(2*n - 1)`: SciPy returns 0 for factorial2(-1) (older versions returned 1), so a
             normalisation with n = 0 divides by zero
- steps      `int(tmax / dt)` truncates: int(1.0 / 0.1) == 9, so the run can end one step short

Like the rest of the scan these only read the source. On 150 corpus repositories (5007 files) on 2026-11-08,
before release: unbound 63 hits in 17 repositories, alias 2 in 2 (both harmless on inspection), steps 8 in 4,
spacing, numba and factorial2 none. unbound and alias cannot follow branches (a name read under the same
condition that bound it, an alias whose source is read only on the other branch), so they are NOTEs and do not
change the exit code; spacing and numba are WARNs.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from .scan import NOTE, WARN, Finding, all_nodes

_FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)


def _own_nodes(fn):
    """Nodes of a function body, not of functions, lambdas or classes nested in it."""
    out, stack = [], list(fn.body)
    while stack:
        n = stack.pop()
        out.append(n)
        for c in ast.iter_child_nodes(n):
            # comprehensions have their own scope, so their loop variables are not locals of the function
            if not isinstance(c, (*_FUNCS, ast.Lambda, ast.ClassDef, ast.ListComp, ast.SetComp, ast.DictComp,
                                  ast.GeneratorExp)):
                stack.append(c)
    return out


def _stored(nodes) -> set[str]:
    names = set()
    for n in nodes:
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            names.add(n.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            names |= {(a.asname or a.name).split(".")[0] for a in n.names}
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            names |= set(n.names)
        elif isinstance(n, _FUNCS + (ast.ClassDef,)):
            names.add(n.name)
    return names


def _walk_own(stmts):
    out = []
    for s in stmts:
        out += [s] + _own_nodes_stmt(s)
    return out


def _own_nodes_stmt(s):
    if isinstance(s, (*_FUNCS, ast.ClassDef)):
        return []
    return _own_nodes(ast.Module(body=[s], type_ignores=[]))


def _ends(stmts) -> bool:
    """The block always leaves the function or loop (return, raise, continue, break as its last statement)."""
    return bool(stmts) and isinstance(stmts[-1], (ast.Return, ast.Raise, ast.Continue, ast.Break))


def _sure_block(stmts):
    """Names a block binds, or None when it always leaves (any name counts as bound after it)."""
    return None if _ends(stmts) else _stored(_walk_own(stmts))


def _sure_chain(if_node):
    body = _sure_block(if_node.body)
    if not if_node.orelse:
        rest = set()
    elif len(if_node.orelse) == 1 and isinstance(if_node.orelse[0], ast.If):
        rest = _sure_chain(if_node.orelse[0])
    else:
        rest = _sure_block(if_node.orelse)
    if body is None:
        return rest
    if rest is None:
        return body
    return body & rest


def _staying(if_node) -> set[str]:
    """Names bound in the branches of an if/elif chain that do not leave the function or loop."""
    out = set() if _ends(if_node.body) else _stored(_walk_own(if_node.body))
    if len(if_node.orelse) == 1 and isinstance(if_node.orelse[0], ast.If):
        return out | _staying(if_node.orelse[0])
    return out | (set() if _ends(if_node.orelse) else _stored(_walk_own(if_node.orelse)))


def _surely_bound(if_node) -> set[str]:
    """Names bound on every path through an if/elif/else chain that continues after it."""
    return _sure_chain(if_node) or set()


def _unbound(fn, rel) -> list[Finding]:
    args = fn.args
    bound = {a.arg for a in args.posonlyargs + args.args + args.kwonlyargs}
    bound |= {a.arg for a in (args.vararg, args.kwarg) if a}
    own = [[s] + _own_nodes_stmt(s) for s in fn.body]  # computed once: this is most of the cost
    loads = [[n for n in o if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)] for o in own]
    out, reported = [], set()
    for i, stmt in enumerate(fn.body):
        if isinstance(stmt, ast.If):
            maybe = _staying(stmt) - _surely_bound(stmt) - bound
            for k in range(i + 1, len(fn.body)):
                if not maybe:
                    break
                # a read inside a later block is often under the same condition again (`if debug:` twice),
                # so only reads in plain statements are reported
                compound = isinstance(fn.body[k], (ast.If, ast.For, ast.While, ast.Try, ast.With))
                for n in ([] if compound else loads[k]):
                    if n.id in maybe and n.id not in reported:
                        reported.add(n.id)
                        out.append(Finding("flow", NOTE, rel, n.lineno,
                                           f"'{n.id}' is assigned only inside the if at line {stmt.lineno}, so"
                                           f" {fn.name}() raises UnboundLocalError when that branch is not taken", rule="PV801"))
                # a later statement that binds the name on every path ends the risk
                if not isinstance(fn.body[k], (ast.If, ast.For, ast.While, ast.Try, ast.With)):
                    maybe -= _stored(own[k])
            bound |= _surely_bound(stmt)
        else:
            bound |= _stored(own[i])
    return out


_NP_MAKERS = re.compile(r"^(np|numpy|jnp|cp|torch)\.")


def _alias(fn, rel) -> list[Finding]:
    nodes = sorted((n for n in _own_nodes(fn) if hasattr(n, "lineno")), key=lambda n: (n.lineno, n.col_offset))
    np_made = set()
    out = []
    for n in nodes:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) \
                and isinstance(n.value, ast.Call) and _NP_MAKERS.match(ast.unparse(n.value.func)):
            np_made.add(n.targets[0].id)
    for n in nodes:
        if not (isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
                and isinstance(n.value, ast.Name)):
            continue
        a, b, line = n.targets[0].id, n.value.id, n.lineno
        if a == b:
            continue
        mutated_at = None
        for m in nodes:
            if m.lineno <= line:
                continue
            if isinstance(m, (ast.Assign, ast.AnnAssign)):
                tg = m.targets if isinstance(m, ast.Assign) else [m.target]
                if any(isinstance(t, ast.Name) and t.id in (a, b) for t in tg):
                    break  # rebinding either name ends the alias
                if mutated_at is None and any(isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)
                                              and t.value.id == a for t in tg):
                    mutated_at = m.lineno
            elif isinstance(m, ast.AugAssign) and mutated_at is None:
                t = m.target
                if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == a:
                    mutated_at = m.lineno
                elif isinstance(t, ast.Name) and t.id == a and b in np_made:
                    mutated_at = m.lineno
            elif mutated_at is not None and m.lineno > mutated_at and isinstance(m, ast.Name) \
                    and isinstance(m.ctx, ast.Load) and m.id == b:
                out.append(Finding("flow", NOTE, rel, line,
                                   f"'{a} = {b}' makes {a} the same array as {b}; {a} is changed in place at line"
                                   f" {mutated_at} and {b} is read at line {m.lineno}, so {b} has changed too."
                                   f" If a copy was meant, write {a} = {b}.copy()", rule="PV802"))
                break
    return out


_WEST = re.compile(r"^[A-Za-z]{1,2}_?(w|W)$|^[A-Za-z]{1,2}_?S$")
_EAST_SP = re.compile(r"^d[xyz]_?[en]$|^D[XYZxyz]_?[enEN]$")
_WEST_SP = re.compile(r"^d[xyz]_?[ws]$|^D[XYZxyz]_?[wsWS]$")


def _spacing(fn, rel) -> list[Finding]:
    nodes = _own_nodes(fn)
    names = {n.id for n in nodes if isinstance(n, ast.Name)} | {x.arg for x in ast.walk(fn.args) if isinstance(x, ast.arg)}
    if not any(_WEST_SP.match(x) for x in names):
        return []  # no west spacing in the function: the grid may be uniform by design
    out = []
    for n in nodes:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) \
                and _WEST.match(n.targets[0].id):
            rhs = {m.id for m in ast.walk(n.value) if isinstance(m, ast.Name)}
            east = sorted(x for x in rhs if _EAST_SP.match(x))
            if east and not any(_WEST_SP.match(x) for x in rhs):
                out.append(Finding("flow", WARN, rel, n.lineno,
                                   f"west/south coefficient '{n.targets[0].id}' uses only east/north spacings"
                                   f" ({', '.join(east)}) although west spacings exist in {fn.name}(); the two"
                                   " agree only on a uniform grid", rule="PV803"))
    return out


def _scipy_names(tree) -> set[str]:
    out = set()
    for n in all_nodes(tree):
        if isinstance(n, ast.Import):
            out |= {(a.asname or a.name).split(".")[0] for a in n.names if a.name.split(".")[0] == "scipy"}
        elif isinstance(n, ast.ImportFrom) and n.module and n.module.split(".")[0] == "scipy":
            out |= {a.asname or a.name for a in n.names}
    return out


def _numba(fn, rel, scipy_names) -> list[Finding]:
    eager = None
    for d in fn.decorator_list:
        if isinstance(d, ast.Call) and ast.unparse(d.func).split(".")[-1] in ("jit", "njit"):
            sig = d.args[:1] or [k.value for k in d.keywords if k.arg == "signature"]
            if sig and not (isinstance(sig[0], ast.Constant) and sig[0].value is None):
                eager = d
    if eager is None or not scipy_names:
        return []
    for n in _own_nodes(fn):
        if isinstance(n, ast.Call):
            root = ast.unparse(n.func).split(".")[0]
            if root in scipy_names:
                return [Finding("flow", WARN, rel, eager.lineno,
                                f"{fn.name}() is compiled at import by an eager numba signature but calls"
                                f" {ast.unparse(n.func)}, which numba cannot type; since numba 0.59 this raises"
                                " TypingError at import (there is no object-mode fallback)", rule="PV804")]
    return []


_T_END = re.compile(r"^(t_?max|t_?end|t_?final|t_?f|t_?stop|t_?total|T|T_?max|T_?end|duration|sim_?time|total_?time)$", re.I)


def _last(node) -> str:
    return node.attr if isinstance(node, ast.Attribute) else getattr(node, "id", "")


def scan_flow(path: Path, tree, rel: str) -> list[Finding]:
    out = []
    scipy_names = _scipy_names(tree)
    for n in all_nodes(tree):
        if isinstance(n, _FUNCS):
            out += _unbound(n, rel) + _alias(n, rel) + _spacing(n, rel) + _numba(n, rel, scipy_names)
        if isinstance(n, ast.Call) and _last(n.func) == "factorial2" and n.args:
            a = n.args[0]
            if isinstance(a, ast.BinOp) and isinstance(a.op, ast.Sub) and isinstance(a.right, ast.Constant) \
                    and a.right.value == 1 and isinstance(a.left, ast.BinOp) and isinstance(a.left.op, ast.Mult):
                out.append(Finding("flow", NOTE, rel, n.lineno,
                                   f"factorial2({ast.unparse(a)}) is factorial2(-1) when the index is 0; current SciPy"
                                   " returns 0 there (it was 1), so a normalisation divides by zero. Use"
                                   " exact=True, or define (-1)!! = 1", rule="PV805"))
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "int" and len(n.args) == 1:
            a = n.args[0]
            if isinstance(a, ast.BinOp) and isinstance(a.op, ast.Div) and _T_END.match(_last(a.left)) \
                    and re.fullmatch(r"d_?t|delta_?t|h|step", _last(a.right), re.I):
                out.append(Finding("flow", NOTE, rel, n.lineno,
                                   f"int({ast.unparse(a)}) truncates (int(1.0 / 0.1) == 9), so the run can stop one"
                                   " step before the end time; use round(), or check the final time", rule="PV806"))
    return out
