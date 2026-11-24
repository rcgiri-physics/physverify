"""Probe `deadargs`: changing an argument changes the result (PV901)."""

from __future__ import annotations

import ast
import re

from ..probing.common import (
    _TURBULENT,
    _discrete,
    _finite,
    _gated,
    _moved,
    _names_in,
    _perturb,
    _same,
    _short,
    _si_constants,
)
from ..stages.common import NOTE, WARN, Finding


def _reads(node, name) -> bool:
    return any(isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load) for n in ast.walk(node))


def _no_effect(f, args, y0, p) -> bool:
    v = args[p]
    # the sign too: an argument that enters only through np.sign(delta_y) is moved only by a sign change (H24)
    flipped = None if isinstance(v, (int, bool)) or (hasattr(v, "dtype") and v.dtype.kind in "biu") else -v
    for x in (_perturb(v), _perturb(v, True), flipped):
        if x is None:
            continue
        try:
            y, _ = f.call({**args, p: x})
        except Exception:  # noqa: BLE001 - an error is an effect
            return False
        if y is None or not _same(y, y0):
            return False
    return True


# solver controls: once converged, the answer no longer depends on them (J034 tol, max_iterations, high_vol)
_CONTROL = re.compile(r"^(r|a)?tol\w*$|tolerance|^max_?it\w*|^n_?iter\w*|iterations|^max_?steps?$|guess|^(low|high|lower|upper)(_\w+)?$|"
                      r"bracket|^maxfev$|^verbose", re.I)
_FLAG = re.compile(r"^(is|has|use|do|with|return|show|plot|save|verbose|debug)_", re.I)


def _flag_like(node, name) -> bool:
    """Used as a yes/no switch or a mode name: `if p:`, `not p`, `p == "lin"`. A float like 0.7 is just "true"."""
    for n in ast.walk(node):
        tests = [n.test] if isinstance(n, (ast.If, ast.IfExp, ast.While)) else []
        if isinstance(n, ast.BoolOp):
            tests += n.values
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            tests.append(n.operand)
        if any(isinstance(t, ast.Name) and t.id == name for t in tests):
            return True
        if isinstance(n, ast.Compare) and any(isinstance(e, ast.Name) and e.id == name for e in [n.left, *n.comparators]) \
                and any(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in [n.left, *n.comparators]):
            return True
    return False


def _probe_dead(f, args, y0, out, rel):
    import numpy as np

    if _discrete(y0) or not _finite(y0):
        return  # yes/no answers rarely flip; NaN against NaN says nothing (J103: sqrt(R - 2M) at the guessed inputs)
    unset = set(f.params) - set(args)  # options the probe leaves at their default (None, a string)
    changed, dead = [], []
    for p, v in args.items():
        if (isinstance(v, bool) or _CONTROL.search(p) or _FLAG.match(p) or _flag_like(f.node, p)
                or _gated(f.node, p, unset) or _only_in_messages(f.node, p)):
            continue
        (dead if _no_effect(f, args, y0, p) else changed).append(p)
    # an argument can be idle at one point (an erf saturated, a term multiplied by sin(0)): try three more points
    rng = np.random.default_rng(0)
    for k in range(4):
        if not dead:
            break
        # the last point is far out: correlations in kelvin clamp T below 258 K (K30 Laliberte, K52 TRC Antoine)
        moved = _moved(args, rng) if k < 3 else {q: v * 300.0 if isinstance(v, (float, np.floating)) else v for q, v in args.items()}
        try:
            y1, _ = f.call(moved)
        except Exception:  # noqa: BLE001
            continue
        if y1 is not None:
            dead = [p for p in dead if _no_effect(f, moved, y1, p)]
    if not changed:
        return  # a constant function (or one the probe cannot move) says nothing about single arguments
    scale = _si_constants(f)
    for p in dead:
        line = f.node.lineno
        side = _side_read(f.node, p, set(f.params))
        if not side and _TURBULENT.match(p):
            side = "as a wall roughness, which matters only in turbulent flow; the guessed Reynolds numbers are laminar"
        if not side and scale:
            side = (f"next to {scale}, a constant in SI units: with inputs of order 1 its effect can fall below"
                    " round-off (J401 hbar*t/m)")
        if _reads(f.node, p) and side:
            out.append(Finding("deadargs", NOTE, rel, line,
                               f"{f.name}: changing {p} leaves the result unchanged at the inputs tried; it is read only"
                               f" {side}, so it may matter only for other inputs", rule="PV901"))
        elif _reads(f.node, p) and not _in_clamp(f.node, p) and not isinstance(args[p], (int, np.integer)):
            out.append(Finding("deadargs", WARN, rel, line,
                               f"{f.name}: changing {p} (from {_short(args[p])}) leaves the result unchanged, although"
                               f" the function reads it and other arguments ({', '.join(changed[:3])}) do change it", rule="PV901"))
        elif _reads(f.node, p) and isinstance(args[p], (int, np.integer)):
            out.append(Finding("deadargs", NOTE, rel, line,
                               f"{f.name}: changing the integer {p} (from {args[p]}) leaves the result unchanged at the"
                               " inputs tried; it may matter only for larger inputs", rule="PV901"))
        elif _reads(f.node, p):
            out.append(Finding("deadargs", NOTE, rel, line,
                               f"{f.name}: changing {p} leaves the result unchanged at the inputs tried; it enters a"
                               " max, min or clip, so it may matter only beyond a threshold", rule="PV901"))
        else:
            out.append(Finding("deadargs", NOTE, rel, line,
                               f"{f.name}: argument {p} is never used in the function body", rule="PV901"))


def _tainted(node, name) -> set[str]:
    """`name` and every local assigned from it, followed through the function (`vel_sq = u**2 + ...`)."""
    out, grew = {name}, True
    while grew:
        grew = False
        for n in ast.walk(node):
            if isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign)) and n.value is not None and _names_in(n.value) & out:
                for t in n.targets if isinstance(n, ast.Assign) else [n.target]:
                    new = {e.id for e in ast.walk(t) if isinstance(e, ast.Name)} - out
                    if new:
                        out |= new
                        grew = True
    return out


def _in_clamp(node, name) -> bool:
    """`name`, or a local computed from it, enters a max, min or clip (J078: velocities into np.clip)."""
    names = _tainted(node, name)
    # `if T < 258.15: T = 258.15` is a clamp too (K30 Laliberte)
    for n in ast.walk(node):
        if isinstance(n, ast.If) and isinstance(n.test, ast.Compare) and _names_in(n.test) & names and any(
                isinstance(b, ast.Assign) and {e.id for t in b.targets for e in ast.walk(t) if isinstance(e, ast.Name)} & names
                for b in n.body):
            return True
    return any(isinstance(n, ast.Call) and re.search(r"(^|\.)(max|min|maximum|minimum|clip|fmax|fmin)$", ast.unparse(n.func))
               and _names_in(n) & names for n in ast.walk(node))


def _load_ids(node, name) -> set[int]:
    return {id(n) for n in ast.walk(node) if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load)}


def _ids_under(nodes) -> set[int]:
    return {id(e) for b in nodes for e in ast.walk(b)}


_MESSAGE = re.compile(r"(^|\.)(warn\w*|print|debug|info|error|exception|critical|log)$")


def _only_in_messages(node, name) -> bool:
    """Every read of `name` builds an error or log message (K03 validate_float: property_name names the property)."""
    reads = _load_ids(node, name)
    inside = _ids_under([n for n in ast.walk(node) if isinstance(n, ast.Raise)
                         or (isinstance(n, ast.Call) and _MESSAGE.search(ast.unparse(n.func)))])
    return bool(reads) and reads <= inside


def _side_read(node, name, params) -> str:
    """Where `name` is read, when every read is in a place the guessed inputs may not reach; "" otherwise."""
    reads = _load_ids(node, name)
    if not reads:
        return ""
    bodies = []
    for n in ast.walk(node):
        if isinstance(n, (ast.If, ast.While)):
            bodies += n.body + n.orelse
        elif isinstance(n, ast.IfExp):
            bodies += [n.body, n.orelse]
        elif isinstance(n, (ast.For, ast.comprehension)):
            bodies += n.body + n.orelse if isinstance(n, ast.For) else n.ifs
            if isinstance(n, ast.comprehension):
                bodies.append(n.target)
    for n in ast.walk(node):
        if isinstance(n, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            bodies += [n.elt] if not isinstance(n, ast.DictComp) else [n.key, n.value]
    if reads <= _ids_under(bodies):
        return "inside a branch or a loop (skyfield-style parabolic case, a loop over *args)"
    # after `if Re < 2300: return 64 / Re` the rest of the body serves other inputs (J253 friction_factor)
    later = []
    for k, st in enumerate(node.body):
        if isinstance(st, ast.If) and any(isinstance(e, ast.Return) for e in ast.walk(st)):
            later = node.body[k + 1:]
            break
    if later and reads <= _ids_under(later):
        return "after an early return"
    # passed only to another argument that is called: with a number in its place (gamma(f), K40) it is ignored
    calls = [a for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in params
             for a in n.args + [k.value for k in n.keywords]]
    if reads <= _ids_under(calls):
        return "as an argument of another argument that is called"
    return ""
