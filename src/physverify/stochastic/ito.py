"""Exact properties of iterated Ito integrals, for codes that generate them for Milstein or order 1.5 schemes.

From Ito calculus (Kloeden and Platen, Numerical Solution of SDEs, ch. 5), on a step h with W = W(h):
I_ii = (W_i^2 - h)/2; I_ij + I_ji = W_i W_j for i != j; I_iii = (W_i^3 - 3 h W_i)/6; and by the Ito isometry
E[I_ij^2] = h^2/2, E[I_ijk^2] = h^3/6 for every index choice.

Generators with several noises use a truncated series, so an identity may hold only as the series grows: a truncation
error falls with the series length and a wrong formula does not. In the corpus session of 2026-11-06 one generator had
an I_111 residual of 0.079 and 0.081 RMS at series lengths 10 and 20, and E[I_ijk^2] from 0.116 to 0.206 instead of 1/6.
False alarms on correct integrals are measured in tests/test_ito.py and stated in docs/checks/numerical-controls.md.
"""

from __future__ import annotations

from itertools import product

import numpy as np

from ..checks import FAIL, PASS, Result


def _rms(a):
    return float(np.sqrt(np.mean(np.square(a))))


def _residuals(w, i2, i3, h):
    """Name -> RMS residual of each identity that may hold only up to truncation."""
    m = w.shape[1]
    out = {}
    if i2 is not None:
        for a in range(m):
            out[f"I_{a}{a} = (W_{a}^2 - h)/2"] = _rms(i2[:, a, a] - (w[:, a] ** 2 - h) / 2)
            for b in range(a + 1, m):
                out[f"I_{a}{b} + I_{b}{a} = W_{a} W_{b}"] = _rms(i2[:, a, b] + i2[:, b, a] - w[:, a] * w[:, b])
    if i3 is not None:
        for a in range(m):
            out[f"I_{a}{a}{a} = (W_{a}^3 - 3 h W_{a})/6"] = _rms(i3[:, a, a, a] - (w[:, a] ** 3 - 3 * h * w[:, a]) / 6)
    return out


def _isometry(arr, ref, name, m, order, margin, z):
    bad = []
    n = arr.shape[0]
    for idx in product(range(m), repeat=order):
        s = arr[(slice(None), *idx)] ** 2
        got = float(s.mean())
        if abs(got - ref) > margin * ref + z * float(s.std()) / np.sqrt(n):
            bad.append(f"{name}{''.join(map(str, idx))}: {got:.4g}")
    return bad


def check_ito_integrals(generate, ps=(None,), *, h: float = 1.0, rtol: float = 0.02, margin: float = 0.05, z: float = 5.0) -> Result:
    """`generate(p)` returns (W, I2, I3): samples of shape (n, m), (n, m, m), (n, m, m, m); I2 or I3 may be None.

    `ps` are series lengths in increasing order. With one entry, every identity must hold within `rtol` h^k RMS. With
    two or more, an identity above `rtol` at the longest series must have fallen by at least 25% from the shortest
    (the error of a truncated Levy-area series goes as 1/sqrt(p) or faster, so use lengths a factor of 4 or more apart).
    The isometry at the longest series allows `margin` relative plus `z` standard errors.
    """
    results = []
    for p in ps:
        w, i2, i3 = generate(p)
        w = np.asarray(w, dtype=float)
        i2 = None if i2 is None else np.asarray(i2, dtype=float)
        i3 = None if i3 is None else np.asarray(i3, dtype=float)
        for name, samples in (("W", w), ("I2", i2), ("I3", i3)):
            if samples is not None and not np.all(np.isfinite(samples)):
                return Result(FAIL, f"Ito integral generator returned non-finite {name} samples at p={p}")
        results.append(_residuals(w, i2, i3, h))
    m = w.shape[1]
    last, first = results[-1], results[0]
    bad = []
    for name, r in last.items():
        order = 2 if name.startswith("I_") and "W_" in name and "^3" not in name else 3
        tol = rtol * h ** (order / 2)
        if r > tol and (len(ps) == 1 or r > 0.75 * first[name]):
            trend = "" if len(ps) == 1 else f" (was {first[name]:.3g} at p={ps[0]}, so not a truncation error)"
            bad.append(f"{name}: RMS residual {r:.3g} at p={ps[-1]}{trend}")
    bad_m = []
    if i2 is not None:
        bad_m += _isometry(i2, h ** 2 / 2, "E[I^2] ", m, 2, margin, z)
    if i3 is not None:
        bad_m += _isometry(i3, h ** 3 / 6, "E[I^2] ", m, 3, margin, z)
    if bad_m:
        bad.append(f"Ito isometry wants E[I_ij^2] = {h**2/2:.4g}, E[I_ijk^2] = {h**3/6:.4g}; " + ", ".join(bad_m))
    if bad:
        return Result(FAIL, "the iterated integrals break exact Ito identities: " + "; ".join(bad))
    worst = max(last.values(), default=0.0)
    return Result(PASS, f"the iterated integrals satisfy the Ito identities and isometry for {m} noise term(s), {w.shape[0]}"
                        f" samples (largest RMS residual {worst:.3g} at the longest series)")
