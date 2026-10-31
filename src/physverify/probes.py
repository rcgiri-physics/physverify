"""`physverify scan PATH --run`: probes that call the code with small inputs (Phase 2 of the scan plan, ROADMAP.md).

Unlike the static scan, these probes **run the code**: use them only on code you trust, or inside the sandbox
(sandbox/). Each probe needs no reference, only a rule that must hold, and each comes from defects in the corpus study:

- smoke      every script runs to the end; the project's own tests can be collected (J253, J264, J265, J147, J157)
- edges      zero, negative and odd-size inputs give no silent NaN (I12 negative anomaly, J409 NaN at rest, G10 odd N)
- deadargs   changing an argument changes the result (J019 gamma ignored, K21 P_delta ignored, K16 mode not passed on)
- branches   a result does not jump where the code switches formula at `if x < a` (J400 jump at rho = d/2, J133)
- roundtrip  `y_to_x(x_to_y(x)) == x` for the inverse pairs the static scan lists
- siblings   two versions of one computation agree: `f` and `f_py`, `_slow` and `_fast`, `_dense` and `_sparse`
             (K18: the C and the Python STA/LTA), and one function under each value of a `method=` option
- known      a cumulative trapezoid integral, running mean or autocorrelation, found by its name, against a slow
             direct loop in any of the usual conventions (K17-style binned and windowed quantities)
- monotone   the direction a named law fixes (reverberation time falls with absorption: K16 rt60_eyring), or one
             the docstring states for an argument ("decreases with temperature")

Only module-level functions are probed, and only in files whose top level defines things and runs nothing else
(scripts are covered by the smoke probe). Inputs are the function's own numeric defaults, then guesses from the
parameter names. Each file runs in its own process with a time limit; a file or function that runs out of time,
or that the probes cannot call, is reported as SKIP, never as passed.
"""

from __future__ import annotations

import ast
import contextlib
import io
import json
import math
import os
import re
import subprocess
import sys
import time
import warnings
from pathlib import Path

from .scan import _PAIR, NOTE, WARN, Finding, python_files

SKIP = "SKIP"
PROBES = ("smoke", "edges", "deadargs", "branches", "roundtrip", "siblings", "known", "monotone")
# what `scan --run` runs without --only: the probes that found real defects in the 626-repository sweep (2026-10-26).
# The others found none there and are kept as opt-in experiments (results/corpus/FEATURES.md).
DEFAULT_PROBES = ("smoke", "branches")

# functions that write, plot, fetch or start things are not called
_SIDE_EFFECT = re.compile(r"(^|_)(main|run|save|write|plot|show|draw|load|read|download|fetch|open|print|export|"
                          r"animate|gui|app|cli|parse|setup|install|test|clean|delete|remove|mkdir|serve)(_|$)", re.I)
_INT_NAME = re.compile(r"^(n|N|n_?\w+|N_?\w+|num\w*|\w*_?steps?|size|dim|order|l|m|nx|ny|nz|nt|iters?|max_?iter\w*|"
                       r"\w*points|\w*_count|count|degree|deg|levels?)$")
_ARRAY_NAME = re.compile(r"^(x|y|z|r|t|q|p|v|u|xs|ys|ts|rs|state|psi|phi|y0|x0|pos\w*|vel\w*|coords?|points?|grid|"
                         r"\w+_list|\w*_?(array|arr|values|samples|series|history|trace)s?)$")  # J260 energy_list
_STATE_NAME = re.compile(r"^(x|y|z|dx|dy|dz|xs|ys|zs|pos\w*|coords?|r_?vec|v|vx|vy|vz|vel\w*|u|w|omega|q|p|"
                         r"theta\w*|th\d?|phi\w*|psi|angle\w*|\w*anomaly|lat\w*|lon\w*|incidence\w*|state|y0|x0)$", re.I)
_CALL_LIMIT = 2.0  # seconds a baseline call may take before the function's other probes are skipped


def _safe_module(tree) -> bool:
    """True when importing the file only defines things: no top-level calls, loops or `with` blocks."""
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                             ast.Assign, ast.AnnAssign, ast.Try, ast.Pass)):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue  # docstring
        if isinstance(node, ast.If):
            continue  # `if __name__ == "__main__":` and version switches
        return False
    return True


def _runs_something(tree) -> bool:
    """True for scripts: a `__main__` block or top-level statements beyond definitions."""
    for node in tree.body:
        if isinstance(node, ast.If) and "__main__" in ast.unparse(node.test):
            return True
    return not _safe_module(tree)


# --- the worker, run in a separate process per file ------------------------------------------------

def _as_array(y):
    import numpy as np

    if isinstance(y, (bool, int, float, complex)) or (isinstance(y, np.generic) and np.issubdtype(type(y), np.number)):
        return np.asarray(y, dtype=complex if isinstance(y, complex) else float).reshape(1)
    if isinstance(y, np.ndarray) and y.dtype.kind in "biufc" and y.size:
        return y.astype(complex if y.dtype.kind == "c" else float).ravel()
    if isinstance(y, (tuple, list)) and y and len(y) <= 64:
        parts = [_as_array(e) for e in y]
        if all(p is not None for p in parts):
            return np.concatenate([p.astype(complex) if any(q.dtype.kind == "c" for q in parts) else p for p in parts])
    return None


def _discrete(y) -> bool:
    """A yes/no answer (`is_bonded`, `approximately_equal`): a small change of one input rarely flips it."""
    import numpy as np

    return bool(np.all(np.isin(y, (0.0, 1.0))))


def _same(a, b) -> bool:
    import numpy as np

    return a.shape == b.shape and bool(np.array_equal(a, b, equal_nan=True))


def _finite(a) -> bool:
    import numpy as np

    return bool(np.all(np.isfinite(a)))


class _Fn:
    def __init__(self, name, fn, node, module):
        self.name, self.fn, self.node, self.module = name, fn, node, module
        self.params = [a.arg for a in node.args.posonlyargs + node.args.args]
        defaults = node.args.defaults
        self.has_default = set(self.params[len(self.params) - len(defaults):]) if defaults else set()

    def call(self, args):
        t0 = time.perf_counter()
        with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            warnings.simplefilter("ignore")
            import numpy as np
            # many solvers update their arrays in place; each call gets its own copies, so one probe cannot
            # change the inputs of the next, and a returned input array is not changed by a later call
            args = {k: v.copy() if isinstance(v, np.ndarray) else v for k, v in args.items()}
            with np.errstate(all="ignore"):
                y = self.fn(**args)
            y = _as_array(y)
        return (y.copy() if isinstance(y, np.ndarray) else y), time.perf_counter() - t0


def _guesses(f: _Fn):
    """Argument sets to try for a function, from its defaults and then from the parameter names."""
    import inspect

    import numpy as np

    sig = inspect.signature(f.fn)
    base = {}
    missing = []
    for p in f.params:
        d = sig.parameters[p].default
        if d is not inspect.Parameter.empty:
            if isinstance(d, bool) or not isinstance(d, (int, float, np.ndarray)):
                continue  # strings, None and flags keep their defaults
            base[p] = d
        else:
            missing.append(p)
    for style in ("scalar", "named", "array"):
        args = dict(base)
        for k, p in enumerate(missing):
            # distinct values: with th1 == th2 a pendulum's sin(th1 - th2) hides the angular velocities
            if style != "array" and _INT_NAME.match(p):
                args[p] = 4 + k % 3
            elif style == "array" or (style == "named" and _ARRAY_NAME.match(p)):
                args[p] = np.linspace(0.1, 1.0, 8) * (1 + 0.13 * k)
            else:
                args[p] = _SCALARS[k % len(_SCALARS)]
        yield args, missing


_SCALARS = (0.7, 0.83, 1.17, 0.61, 1.31, 0.92, 1.53, 0.77)


def _moved(args, rng):
    """The same arguments with every float scaled by a random factor, to leave a regime where one has no effect."""
    import numpy as np

    out = {}
    for p, v in args.items():
        if isinstance(v, (float, np.floating)) and v == 0:
            out[p] = rng.uniform(0.2, 1.0)  # with v = D = 0 by default, t has no effect on a carried Gaussian
        elif isinstance(v, (float, np.floating)) or (isinstance(v, np.ndarray) and v.dtype.kind == "f"):
            out[p] = v * rng.uniform(0.5, 2.0)
        else:
            out[p] = v
    return out


def _perturb(v, big=False):
    import numpy as np

    if isinstance(v, (int, np.integer)) and not isinstance(v, bool):
        return int(v) + (3 if big else 1)
    if isinstance(v, np.ndarray):
        return v * (2.0 if big else 1.1) + (1.0 if big else 0.05)
    return float(v) * (2.0 if big else 1.1) + (1.0 if big else 0.05)


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
                               f" {side}, so it may matter only for other inputs"))
        elif _reads(f.node, p) and not _in_clamp(f.node, p) and not isinstance(args[p], (int, np.integer)):
            out.append(Finding("deadargs", WARN, rel, line,
                               f"{f.name}: changing {p} (from {_short(args[p])}) leaves the result unchanged, although"
                               f" the function reads it and other arguments ({', '.join(changed[:3])}) do change it"))
        elif _reads(f.node, p) and isinstance(args[p], (int, np.integer)):
            out.append(Finding("deadargs", NOTE, rel, line,
                               f"{f.name}: changing the integer {p} (from {args[p]}) leaves the result unchanged at the"
                               " inputs tried; it may matter only for larger inputs"))
        elif _reads(f.node, p):
            out.append(Finding("deadargs", NOTE, rel, line,
                               f"{f.name}: changing {p} leaves the result unchanged at the inputs tried; it enters a"
                               " max, min or clip, so it may matter only beyond a threshold"))
        else:
            out.append(Finding("deadargs", NOTE, rel, line,
                               f"{f.name}: argument {p} is never used in the function body"))


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


_TURBULENT = re.compile(r"^(rough\w*|e_?D|eps_?D|epsilon_?D|rel_?rough\w*)$", re.I)  # K36 fluids: 30 friction correlations


def _si_constants(f) -> str:
    """A module-level constant the function reads whose size says SI units (hbar, k_B, c), or ""."""
    g = getattr(f.fn, "__globals__", {})
    for n in ast.walk(f.node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in f.params:
            v = g.get(n.id)
            if isinstance(v, float) and v != 0 and not 1e-6 < abs(v) < 1e6:
                return n.id
    return ""


def _gated(node, name, unset) -> bool:
    """Every read of `name` sits under an `if` on an option left at its default (`if site is not None:`, H62)."""
    reads = {id(n) for n in ast.walk(node) if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load)}
    if not reads:
        return False
    guarded = set()
    for n in ast.walk(node):
        if isinstance(n, (ast.If, ast.IfExp)) and _names_in(n.test) & unset:
            for b in (n.body if isinstance(n.body, list) else [n.body]):
                guarded |= {id(e) for e in ast.walk(b) if isinstance(e, ast.Name)}
    return reads <= guarded


def _probe_edges(f, args, y0, out, rel):
    import numpy as np

    if not _finite(y0):
        return
    divisors = _divisors(f.node)
    for p, v in args.items():
        if isinstance(v, bool) or not isinstance(v, (int, float, np.ndarray, np.integer, np.floating)):
            continue
        if isinstance(v, (int, np.integer)):
            tries = [("an odd value", int(v) + 1 if int(v) % 2 == 0 else int(v) + 2),
                     ("an even value", int(v) + 1 if int(v) % 2 else int(v) + 2)]
        elif _STATE_NAME.match(p):
            # coordinates, velocities and angles may be zero or negative whatever the documentation says
            tries = [] if p in divisors else [("zero", np.zeros_like(v) if isinstance(v, np.ndarray) else 0.0)]
            tries.append(("a negative value", -np.abs(v) if isinstance(v, np.ndarray) else -abs(float(v)) or -0.7))
        elif not isinstance(v, np.ndarray) and p not in divisors:
            tries = [("zero", 0.0)]
        else:
            continue
        for what, x in tries:
            try:
                y, _ = f.call({**args, p: x})
            except Exception:  # noqa: BLE001 - refusing an input is allowed; a silent NaN is the concern
                continue
            if y is not None and not _finite(y):
                out.append(Finding("edges", NOTE, rel, f.node.lineno,
                                   f"{f.name}: with {p} = {what} ({_short(x)}) and the other inputs unchanged, the result"
                                   " has NaN or infinite values without an error; check that the documentation excludes this input"))
                break


def _divisors(node) -> set[str]:
    """Parameters the code divides by or takes the log of directly (`/ m`, `/ W**2`, `log(err)`): zero is plainly excluded."""
    out = set()
    for n in ast.walk(node):
        tops = []
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            tops.append(n.right)
        elif isinstance(n, ast.Call) and re.search(r"(^|\.)log(10|2|1p)?$", ast.unparse(n.func)) and n.args:
            tops.append(n.args[0])
        for t in tops:
            while isinstance(t, ast.BinOp) and isinstance(t.op, (ast.Pow, ast.Mult)):
                out |= {e.id for e in (t.left, t.right) if isinstance(e, ast.Name)}
                t = t.left if isinstance(t.left, ast.BinOp) else t.right
            if isinstance(t, ast.Name):
                out.add(t.id)
    return out


def _short(v) -> str:
    import numpy as np

    if isinstance(v, np.ndarray):
        return f"array of {v.size}"
    return f"{v:.4g}" if isinstance(v, float) else str(v)


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


def _names_in(node) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


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
                               " should be continuous there unless the model has a real step"))


def _probe_roundtrips(fns, out, rel):
    import numpy as np

    for name, f in fns.items():
        m = _PAIR.match(name)
        if not m or m["x"].lower() == m["y"].lower():
            continue
        other = f"{m['pre']}{m['y']}{m['sep']}{m['x']}{m['post']}"
        g = fns.get(other)
        if g is None or name > other or len(f.params) - len(f.has_default) != 1 or len(g.params) - len(g.has_default) != 1:
            continue
        p = f.params[0]
        bad = None
        for x in (0.7, np.linspace(0.1, 1.0, 8)):
            try:
                y = f.fn(x)
                z = g.fn(y)
            except Exception:  # noqa: BLE001 - inputs outside the domain are not probed
                continue
            za, xa = _as_array(z), _as_array(x)
            if za is None or za.shape != xa.shape or not _finite(za):
                continue
            err = float(np.max(np.abs(za - xa)) / np.max(np.abs(xa)))
            if err > 1e-6:
                bad = (x, err)
                break
        if bad:
            out.append(Finding("roundtrip", WARN, rel, f.node.lineno,
                               f"{other}({name}({p})) differs from {p} by {bad[1]:.2g} (relative) for {p} = {_short(bad[0])};"
                               " the two names say they are inverses"))


def _import(path: Path, root: Path):
    import importlib
    import importlib.util

    parts, d = [path.stem], path.parent
    while (d / "__init__.py").exists() and d != d.parent:
        parts.insert(0, d.name)
        d = d.parent
    for extra in (d, root, root / "src"):
        if str(extra) not in sys.path:
            sys.path.insert(0, str(extra))
    for _ in range(5):
        try:
            if len(parts) > 1:
                return importlib.import_module(".".join(parts))
            spec = importlib.util.spec_from_file_location(path.stem, path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[path.stem] = mod
            spec.loader.exec_module(mod)
            return mod
        except ModuleNotFoundError as exc:
            # the project's own module in another folder (scripts/ importing from lib/): add that folder and retry
            where = _own_module(root, (exc.name or "").split(".")[0])
            if where is None or str(where) in sys.path:
                raise
            sys.path.insert(0, str(where))
            # forget the half-imported package, and only it: a bare prefix test would also drop `numpy` for a package `num`
            for k in [k for k in sys.modules if k in (path.stem, parts[0]) or k.startswith(parts[0] + ".")]:
                del sys.modules[k]
    raise ImportError("gave up after five folders")


def _own_module(root: Path, name: str):
    """The folder that holds `name/__init__.py`, `name/` or `name.py` inside the repository, nearest the top."""
    if not name:
        return None
    hits = [p.parent for p in root.rglob(name) if p.is_dir() and not {".git", "site-packages"} & set(p.parts)]
    hits += [p.parent for p in root.rglob(f"{name}.py") if not {".git", "site-packages"} & set(p.parts)]
    return min(hits, key=lambda d: len(d.parts)) if hits else None


# words that name a version of one computation, not a different quantity (from the pairs read in the corpus)
_VARIANT = {"py", "python", "pure", "slow", "fast", "numba", "numpy", "np", "jit", "jax", "torch", "serial", "parallel",
            "dense", "sparse", "reference", "ref", "naive", "brute", "direct", "loop", "loops", "vectorized", "vectorised",
            "vec", "c", "cy", "cython", "cpu", "simple", "old", "new", "v1", "v2", "impl", "optimized", "optimised"}
_OPTION = re.compile(r"^(method|algorithm|algo|backend|impl|implementation|engine|how)$")
_AGREE = 1e-6  # relative: round-off of a reordered sum, not a different formula


def _base_name(name: str):
    """`classic_sta_lta_py` -> ("classic_sta_lta", {"py"}); `classic_sta_lta` -> ("classic_sta_lta", {})."""
    words = name.strip("_").split("_")
    variants = {w.lower() for w in words if w.lower() in _VARIANT}
    if len(variants) == len(words):
        return None
    return "_".join(w for w in words if w.lower() not in _VARIANT).lower(), frozenset(variants)


def _disagree(a, b):
    """Relative difference of two results, or None when they cannot be compared (shapes differ, nothing finite)."""
    import numpy as np

    if a is None or b is None or a.shape != b.shape:
        return None
    if a.ndim == 1 and a.size <= 4 and np.iscomplexobj(a) | np.iscomplexobj(b):
        a, b = np.sort_complex(a), np.sort_complex(b)  # the roots of a cubic, in any order (K30 volume_solutions)
    if not np.array_equal(np.isfinite(a), np.isfinite(b)):
        return math.inf
    m = np.isfinite(a)
    if not m.any():
        return None
    scale = max(float(np.max(np.abs(a[m]))), float(np.max(np.abs(b[m]))), 1e-300)
    return float(np.max(np.abs(a[m] - b[m]))) / scale


def _baseline(f):
    """The first guessed arguments the function accepts, its result and the time one call took."""
    for args, _missing in _guesses(f):
        try:
            y, dt = f.call(args)
        except Exception:  # noqa: BLE001
            continue
        if y is not None:
            return args, y, dt
    return None


def _probe_siblings(allfns, out, rel):
    groups = {}
    for name, f in allfns.items():
        b = _base_name(name)
        if b:
            groups.setdefault(b[0], []).append((b[1], f))
    for members in groups.values():
        if not any(v for v, _f in members):
            continue  # no variant word at all: one function, not a pair
        members.sort(key=lambda m: len(m[0]))  # the plain name first, as the reference
        ref_variants, ref = members[0]
        for variants, g in members[1:]:
            if variants == ref_variants or ref.params != g.params:
                continue  # the same arguments in the same order, or the two are not meant to be called alike
            start = _baseline(ref)
            if start is None or start[2] > _CALL_LIMIT:
                continue
            args, y0, _ = start
            try:
                y1, _ = g.call(args)
            except Exception:  # noqa: BLE001 - one version refusing the input says nothing about agreement
                continue
            d = _disagree(y0, y1)
            if d is not None and d > _AGREE:
                given = ", ".join(f"{k}={_short(v)}" for k, v in args.items())
                out.append(Finding("siblings", WARN, rel, g.node.lineno,
                                   f"{ref.name} and {g.name} differ by {d:.2g} (relative) for the same arguments ({given});"
                                   " their names say they are two versions of one computation"))


def _string_options(f):
    """`{param: [values]}` for an option compared with two or more strings in the body (`method == "fft"`)."""
    found = {}
    for n in ast.walk(f.node):
        if isinstance(n, ast.Compare) and isinstance(n.left, ast.Name) and _OPTION.match(n.left.id) and n.left.id in f.params:
            for c in n.comparators:
                for v in [c] if isinstance(c, ast.Constant) else list(getattr(c, "elts", [])):
                    if isinstance(v, ast.Constant) and isinstance(v.value, str):
                        found.setdefault(n.left.id, []).append(v.value)
    return {k: list(dict.fromkeys(v)) for k, v in found.items() if len(set(v)) >= 2}


def _probe_options(f, args, y0, out, rel):
    """One function, each value of its `method=` option: the same answer (K16 autocorr: fft, time, numpy)."""
    for p, values in _string_options(f).items():
        results = {}
        for v in values:
            try:
                y, _ = f.call({**args, p: v})
            except Exception:  # noqa: BLE001 - an option that refuses these inputs is left out
                continue
            if y is not None:
                results[v] = y
        names = list(results)
        for v in names[1:]:
            d = _disagree(results[names[0]], results[v])
            if d is not None and d > _AGREE:
                out.append(Finding("siblings", NOTE, rel, f.node.lineno,
                                   f"{f.name}: {p}={names[0]!r} and {p}={v!r} differ by {d:.2g} (relative) for the same"
                                   " other arguments; check whether the options are meant to give the same answer"))


# --- known answers: a fast operation against its slow definition ----------------------------------

_CUMTRAPZ = re.compile(r"cum\w*trap|cumulative_(trapezoid|integral)|^_?cum$|cumint", re.I)
_RUNMEAN = re.compile(r"(running|moving|rolling|sliding)_?(mean|average|avg|ave)", re.I)
_AUTOCORR = re.compile(r"auto_?corr|^_?acf$|^_?vacf", re.I)
_WINDOW = re.compile(r"^(n|w|k|m|win\w*|window\w*|width|size|radius|half\w*|span|nwin|npts|n_?avg|length|lag\w*|n_?lags?|max_?lag|nlags|p)$", re.I)


def _cumtrapz_refs(x, y):
    import numpy as np

    c = np.concatenate([[0.0], np.cumsum(0.5 * (y[1:] + y[:-1]) * np.diff(x))])
    return [c, c[1:]]  # with or without the leading 0


def _runmean_refs(y, w):
    import numpy as np

    n = len(y)
    out = []
    for width in {w, 2 * w + 1}:  # a window of w points, or a radius w
        if 1 <= width <= n:
            valid = np.array([y[i:i + width].mean() for i in range(n - width + 1)])
            h = width // 2
            shrink = np.array([y[max(0, i - h):i + h + 1].mean() for i in range(n)])
            trailing = np.array([y[max(0, i - width + 1):i + 1].mean() for i in range(n)])
            out += [valid, shrink, trailing]
            padded = np.convolve(y, np.ones(width) / width, mode="same")
            out.append(padded)
    out.append(np.cumsum(y) / np.arange(1, n + 1))
    return out


def _autocorr_refs(x, lags):
    import numpy as np

    n, out = len(x), []
    for centred in (False, True):
        z = x - x.mean() if centred else x
        raw = np.array([np.dot(z[:n - k], z[k:]) for k in range(lags)])
        out += [raw, raw / raw[0], raw / n, raw / (n - 1), raw / (n - np.arange(lags)),
                raw / (n - np.arange(lags)) / (raw[0] / n)]
    return out


def _matches(y, refs, *, prefix=False) -> bool:
    """`y` equals one of `refs` to round-off; with `prefix`, its first lags may be compared with a longer reference."""
    import numpy as np

    for r in refs:
        k = min(len(y), len(r))
        if k >= 3 and (len(y) == len(r) or (prefix and len(y) != len(r))):
            a, b = y[:k], r[:k]
            if np.allclose(a, b, rtol=1e-6, atol=1e-9 * max(1.0, float(np.max(np.abs(b))))):
                return True
    return False


def _probe_known(f, out, rel):
    """One fast operation, called on random data, against every usual definition of it."""
    import numpy as np

    rng = np.random.default_rng(1)
    params = [p for p in f.params if p not in f.has_default]
    kind = ("cumtrapz" if _CUMTRAPZ.search(f.name) else "runmean" if _RUNMEAN.search(f.name)
            else "autocorr" if _AUTOCORR.search(f.name) else None)
    if kind is None or not 1 <= len(params) <= 2:
        return
    n = 40
    x = np.sort(rng.uniform(0.0, 4.0, n))
    y = rng.normal(size=n) + 1.0
    if kind == "cumtrapz":
        if len(params) != 2:
            return
        xi = [i for i, q in enumerate(params) if q.lower() in ("x", "t", "xs", "ts", "grid", "r", "z")]
        if len(xi) != 1:
            return
        args = {params[xi[0]]: x, params[1 - xi[0]]: y}
        refs, what = _cumtrapz_refs(x, y), "the cumulative trapezoid sum, with or without a leading 0"
    elif kind == "runmean":
        if len(params) == 2 and _WINDOW.match(params[1]):
            w = 5
            args, refs = {params[0]: y, params[1]: w}, _runmean_refs(y, w)
        elif len(params) == 2 and params[1].lower() in ("x", "t"):
            args = {params[0]: y, params[1]: x}
            c = _cumtrapz_refs(x, y)[0]
            refs = [c[1:] / (x[1:] - x[0]), np.concatenate([[y[0]], c[1:] / (x[1:] - x[0])])]
        else:
            return
        what = "a direct window loop (valid, centred with shrinking edges, trailing, zero-padded or cumulative)"
    else:
        lags = 6
        if len(params) == 1:
            args = {params[0]: y}
        elif _WINDOW.match(params[1]):
            args = {params[0]: y, params[1]: lags}
        else:
            return
        refs = _autocorr_refs(y, lags)
        what = "a direct lag sum (raw or mean-removed; divided by nothing, r0, N, N-1 or N-m)"
    try:
        got, _ = f.call(args)
    except Exception:  # noqa: BLE001 - another calling convention; not probed
        return
    if got is None or got.size < 3 or not _finite(got):
        return
    # an autocorrelation may return any number of lags: compare the first ones
    if not _matches(got.real if np.iscomplexobj(got) else got, refs, prefix=kind == "autocorr"):
        out.append(Finding("known", WARN if kind == "cumtrapz" else NOTE, rel, f.node.lineno,
                           f"{f.name}: on random data the result matches none of {what}; check its definition"))


# --- monotone: a direction fixed by a law or stated in the docstring -------------------------------

# (function name, argument name, direction): reverberation time falls with absorption and rises with volume
# (Sabine, Eyring); vapour pressure rises with temperature (Clausius-Clapeyron); skin depth falls with conductivity
# and frequency.
_LAWS = [
    (r"rt60|reverb", r"^(a|alpha|absorption\w*|abs_?coef\w*)$", -1),
    (r"rt60|reverb", r"^(v|vol|volume)$", +1),
    (r"vapou?r_?pressure|p_?sat|saturation_?pressure|p_?ice|psat", r"^(t|temp\w*|t_?k|tk|tp_?k|t_?c)$", +1),
    (r"skin_?depth", r"^(sigma|conductivity|f|freq\w*|omega|w)$", -1),
]
_SAYS = [
    (re.compile(r"\b(increases?|grows?|rises?)\s+(with|as)\s+(the\s+)?(?P<p>\w+)(\s+(?P<how>increases|grows|rises|decreases|falls))?", re.I), +1),
    (re.compile(r"\b(decreases?|falls?|drops?|shrinks?)\s+(with|as)\s+(the\s+)?(?P<p>\w+)(\s+(?P<how>increases|grows|rises|decreases|falls))?", re.I), -1),
    (re.compile(r"\binversely\s+proportional\s+to\s+(the\s+)?(?P<p>\w+)", re.I), -1),
]


def _directions(f):
    """`[(param, +1 or -1, why, level)]` from the table of laws and from the docstring."""
    out = []
    for fname, pname, sign in _LAWS:
        if re.search(fname, f.name, re.I):
            out += [(p, sign, "the law the name refers to", WARN) for p in f.params if re.match(pname, p, re.I)]
    doc = ast.get_docstring(f.node) or ""
    for rx, sign in _SAYS:
        for m in rx.finditer(doc):
            p = m["p"]
            if p not in f.params:
                continue
            how = (m.groupdict().get("how") or "").lower()
            s = sign * (-1 if how in ("decreases", "falls") else 1)
            out.append((p, s, f'the docstring ("{m.group(0).strip()}")', NOTE))
    seen, uniq = set(), []
    for d in out:
        if d[0] not in seen:
            seen.add(d[0])
            uniq.append(d)
    return uniq


def _probe_monotone(f, args, y0, out, rel):
    import numpy as np

    for p, sign, why, level in _directions(f):
        v = args.get(p)
        # the guessed point itself may be outside the domain (an absorption of 1.17): only the sweep has to be finite
        if not isinstance(v, (int, float)) or isinstance(v, bool) or y0.size != 1:
            continue
        v = float(v)
        lo, hi = (0.05, 0.6) if level == WARN and sign < 0 and p.lower().startswith(("a", "abs")) else (0.6 * v, 1.6 * v)
        if level == WARN and re.search(r"^d\d*\w*_d[a-z]+\d*$", f.name, re.I):
            continue  # a derivative (d2Yaws_Psat_dT2, K52) need not follow the law's direction
        if level == WARN and re.match(r"^(t|temp\w*|t_?k|tk|tp_?k|t_?c)$", p, re.I):
            if set(f.params) - f.has_default - {p}:
                continue  # fitted coefficients guessed at random (Yaws_Psat(T, A, B, C, D, E), K52) make any curve
            lo, hi = 280.0, 600.0  # a temperature in kelvin, inside the range of the usual correlations
        xs = np.linspace(lo, hi, 7)
        ys = []
        for x in xs:
            try:
                y, _ = f.call({**args, p: float(x)})
            except Exception:  # noqa: BLE001
                ys = None
                break
            if y is None or y.size != 1 or not _finite(y):
                ys = None
                break
            ys.append(float(y[0].real))
        if not ys:
            continue
        d = np.diff(ys)
        if np.all(d == 0):
            continue  # the dead-argument probe reports that
        if np.any(sign * d < -1e-12 * max(1.0, max(abs(t) for t in ys))):
            word = "rise" if sign > 0 else "fall"
            out.append(Finding("monotone", level, rel, f.node.lineno,
                               f"{f.name}: the result should {word} as {p} rises ({why}), but from {p} = {xs[0]:.3g} to"
                               f" {xs[-1]:.3g} it goes {', '.join(f'{t:.4g}' for t in ys[:4])}, ..."))


def worker(path: str, root: str, rel: str, probes) -> list[Finding]:
    """Probe the module-level functions of one file (runs in its own process)."""
    import numpy as np  # noqa: F401 - fail early when NumPy is missing

    os.environ.setdefault("MPLBACKEND", "Agg")
    p, out = Path(path), []
    tree = ast.parse(p.read_text(encoding="utf-8-sig", errors="replace"))
    try:
        with contextlib.redirect_stdout(io.StringIO()), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mod = _import(p, Path(root))
    except BaseException as exc:  # noqa: BLE001 - SystemExit too
        return [Finding("run", SKIP, rel, 1, f"not probed: the module does not import ({type(exc).__name__}: {str(exc)[:200]})")]
    allfns = {}  # private ones too: `_trace_dense` and `_trace_sparse` are siblings worth comparing
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or _SIDE_EFFECT.search(node.name):
            continue
        fn = getattr(mod, node.name, None)
        if callable(fn) and not node.args.kwonlyargs and getattr(fn, "__module__", None) == mod.__name__:
            allfns[node.name] = _Fn(node.name, fn, node, mod)
    fns = {k: v for k, v in allfns.items() if not k.startswith("_")}
    if "roundtrip" in probes:
        _probe_roundtrips(fns, out, rel)
    if "siblings" in probes:
        try:
            _probe_siblings(allfns, out, rel)
        except Exception as exc:  # noqa: BLE001
            out.append(Finding("run", SKIP, rel, 1, f"siblings probe stopped ({type(exc).__name__})"))
    for f in fns.values():
        if not f.params:
            continue
        if "known" in probes:
            try:
                _probe_known(f, out, rel)
            except Exception as exc:  # noqa: BLE001
                out.append(Finding("run", SKIP, rel, f.node.lineno, f"{f.name}: known probe stopped ({type(exc).__name__})"))
        start = _baseline(f)
        if start is None:
            continue  # functions taking objects, strings or callables are not probed (not a SKIP: nothing applies)
        base, y0, dt = start
        if dt > _CALL_LIMIT:
            out.append(Finding("run", SKIP, rel, f.node.lineno, f"{f.name}: one call took {dt:.1f} s; its probes were skipped"))
            continue
        for name, run in (("deadargs", _probe_dead), ("edges", _probe_edges), ("branches", _probe_branches),
                          ("siblings", _probe_options), ("monotone", _probe_monotone)):
            if name in probes:
                try:
                    run(f, base, y0, out, rel)
                except Exception as exc:  # noqa: BLE001
                    out.append(Finding("run", SKIP, rel, f.node.lineno, f"{f.name}: {name} probe stopped ({type(exc).__name__})"))
    return out


# --- driver ---------------------------------------------------------------------------------------

def _collect_tests(root: Path, timeout: float) -> list[Finding]:
    if not any((root / d).is_dir() for d in ("tests", "test")) and not list(root.glob("test_*.py")):
        return []
    try:
        p = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"], cwd=root,
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout,
                           env=dict(os.environ, MPLBACKEND="Agg"))
    except subprocess.TimeoutExpired:
        return [Finding("smoke", SKIP, "tests", 1, f"collecting the project's tests took longer than {timeout:g} s")]
    errors = [ln for ln in p.stdout.splitlines() if ln.startswith("ERROR ")]
    if "No module named pytest" in p.stderr:
        return [Finding("smoke", SKIP, "tests", 1, "pytest is not installed, so the project's tests were not collected")]
    return [Finding("smoke", NOTE, ln.split()[1].split("::")[0], 1,
                    f"the project's own test file does not import under pytest: {ln[6:][:200]}") for ln in errors[:20]]


_CODE_ERRORS = ("NameError", "TypeError", "AttributeError", "IndexError", "ZeroDivisionError", "UnboundLocalError",
                "SyntaxError", "KeyError")


def _code_error(detail: str, src: str) -> bool:
    """True when the script's last error points at the code rather than at what it was given or what is installed."""
    kind = detail.split(":")[0].strip()
    if kind not in _CODE_ERRORS:
        return False
    if kind in ("IndexError", "KeyError") and re.search(r"\bargv\b|os\.environ|getenv", src):
        return False  # run without the command-line arguments or environment variables it expects (J265 from sys import argv)
    if kind == "IndexError" and re.search(r"\.glob\(|iterdir\(|listdir\(|read_csv\(|loadtxt\(", src):
        return False  # a list of data files or rows that is empty in a bare clone (F04 summarize, J099)
    m = re.match(r"NameError: name '(\w+)'", detail)
    if m and re.search(r"\bargv\b", src) and re.search(rf"^\s+{m.group(1)}\s*=", src, re.M):
        return False  # set only on the command-line branch the probe did not take (K15 ROOT = sys.argv[2])
    if kind == "TypeError" and re.search(r"not NoneType|'NoneType' object is not (iterable|subscriptable)", detail) \
            and re.search(r"argparse|sys\.argv|os\.environ|getenv|input\(", src):
        return False  # a path or option that would come from the command line was None
    if kind == "AttributeError" and "'NoneType' object has no attribute" in detail and re.search(r"=\s*None|\bcp\b|cupy|cuda|torch|jax", src):
        return False  # an optional package set to None when it is not installed (torch = None)
    m = re.search(r"module '([\w.]+)' has no attribute", detail)
    if m and m.group(1).split(".")[0] not in ("numpy", "scipy", "matplotlib"):
        return False  # a platform module (ctypes.windll) or a stub of a package that is not installed
    return True


def probe(path, *, probes=PROBES, timeout: float = 60.0) -> list[Finding]:
    """Run the probes on every Python file under `path`. Runs the code: trusted code or the sandbox only."""
    from .smoke import OK, TIMEOUT, smoke_script

    root = Path(path)
    out = []
    for f in python_files(root):
        rel = str(f.relative_to(root)) if root.is_dir() else f.name
        try:
            tree = ast.parse(f.read_text(encoding="utf-8-sig", errors="replace"))
        except (SyntaxError, ValueError):
            continue  # the static scan reports files that do not parse
        if f.name.startswith("test_") or "tests" in Path(rel).parts or f.name in ("setup.py", "conftest.py"):
            continue
        # a module inside a package is written to be imported (top-level calls there are registrations, not runs),
        # and run by path it fails on its relative imports; loose files are scripts unless they only define things
        in_package = (f.parent / "__init__.py").exists() and f.name != "__main__.py"
        if not in_package and _runs_something(tree):
            if "smoke" in probes:
                r = smoke_script(f, timeout=timeout)
                if r.outcome == TIMEOUT:
                    out.append(Finding("smoke", SKIP, rel, 1, f"the script was still running after {timeout:g} s"))
                elif r.outcome != OK:
                    level = WARN if _code_error(r.detail, f.read_text(encoding="utf-8", errors="replace")) else NOTE
                    out.append(Finding("smoke", level, rel, 1, f"the script stops with an error: {r.detail}"))
            if not _safe_module(tree):
                continue
        func_probes = [p for p in probes if p != "smoke"]
        if not func_probes or not any(isinstance(n, ast.FunctionDef) for n in tree.body):
            continue
        out += _run_worker(f, root if root.is_dir() else f.parent, rel, func_probes, timeout)
    if "smoke" in probes and root.is_dir():
        out += _collect_tests(root, timeout)
    return out


def _run_worker(f: Path, root: Path, rel: str, probes, timeout: float) -> list[Finding]:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        res = Path(tmp) / "out.json"
        cmd = [sys.executable, "-m", "physverify.probes", str(f.resolve()), str(root.resolve()), rel, ",".join(probes), str(res)]
        # the worker must import this copy of physverify, installed or not
        here = str(Path(__file__).resolve().parents[1])
        env = dict(os.environ, MPLBACKEND="Agg", PYTHONPATH=os.pathsep.join(filter(None, [here, os.environ.get("PYTHONPATH")])))
        try:
            r = subprocess.run(cmd, cwd=tmp, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout, env=env)
        except subprocess.TimeoutExpired:
            return [Finding("run", SKIP, rel, 1, f"probing this file took longer than {timeout:g} s; its functions were not probed")]
        if not res.exists():
            last = [ln for ln in (r.stderr or "").strip().splitlines() if ln.strip()][-1:] or [f"exit code {r.returncode}"]
            return [Finding("run", SKIP, rel, 1, f"the probe process stopped before reporting: {last[0][:200]}")]
        return [Finding(**d) for d in json.loads(res.read_text(encoding="utf-8"))]


def _main(argv) -> int:
    from dataclasses import asdict

    path, root, rel, probes, res = argv
    found = worker(path, root, rel, probes.split(","))
    Path(res).write_text(json.dumps([asdict(f) for f in found]), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
