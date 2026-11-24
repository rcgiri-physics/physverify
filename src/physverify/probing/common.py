"""Shared pieces of the `scan --run` probes: calling a function, guessing its inputs, importing a file."""

from __future__ import annotations

import ast
import contextlib
import io
import re
import sys
import time
import warnings
from pathlib import Path

_INT_NAME = re.compile(r"^(n|N|n_?\w+|N_?\w+|num\w*|\w*_?steps?|size|dim|order|l|m|nx|ny|nz|nt|iters?|max_?iter\w*|"
                       r"\w*points|\w*_count|count|degree|deg|levels?)$")
_ARRAY_NAME = re.compile(r"^(x|y|z|r|t|q|p|v|u|xs|ys|ts|rs|state|psi|phi|y0|x0|pos\w*|vel\w*|coords?|points?|grid|"
                         r"\w+_list|\w*_?(array|arr|values|samples|series|history|trace)s?)$")  # J260 energy_list
_STATE_NAME = re.compile(r"^(x|y|z|dx|dy|dz|xs|ys|zs|pos\w*|coords?|r_?vec|v|vx|vy|vz|vel\w*|u|w|omega|q|p|"
                         r"theta\w*|th\d?|phi\w*|psi|angle\w*|\w*anomaly|lat\w*|lon\w*|incidence\w*|state|y0|x0)$", re.I)
_CALL_LIMIT = 2.0  # seconds a baseline call may take before the function's other probes are skipped


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


def _names_in(node) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


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
