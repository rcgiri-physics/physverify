"""Probe `known`: a cumulative integral, running mean or autocorrelation against its slow definition (PV907)."""

from __future__ import annotations

import re

from ..probing.common import _finite
from ..stages.common import NOTE, WARN, Finding

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
                           f"{f.name}: on random data the result matches none of {what}; check its definition", rule="PV907"))
