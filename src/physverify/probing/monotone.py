"""Probe `monotone`: a result moves in the direction a named law or the docstring fixes (PV908)."""

from __future__ import annotations

import ast
import re

from ..probing.common import _finite
from ..stages.common import NOTE, WARN, Finding

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
                               f" {xs[-1]:.3g} it goes {', '.join(f'{t:.4g}' for t in ys[:4])}, ...", rule="PV908"))
