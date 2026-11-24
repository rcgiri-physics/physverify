"""Probe `siblings`: two versions of one computation, or two options of one function, agree (PV905, PV906)."""

from __future__ import annotations

import ast
import math
import re

from ..probing.common import _CALL_LIMIT, _guesses, _short
from ..stages.common import NOTE, WARN, Finding

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
                                   " their names say they are two versions of one computation", rule="PV905"))


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
                                   " other arguments; check whether the options are meant to give the same answer", rule="PV906"))
