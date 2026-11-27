"""Long-time behaviour of a conserved quantity in one run: bounded, or drifting?

A symplectic integrator (leapfrog, Stormer-Verlet, Gauss) keeps the energy error of a Hamiltonian system bounded
for exponentially long times (Hairer, Lubich & Wanner, Geometric Numerical Integration, ch. IX), so |E(t) - E0|
oscillates without growing. A non-symplectic one (RK4, explicit Euler) has an error that grows like t (or faster).
`check_energy_drift` fits the growth exponent k of the error envelope, |E(t) - E0| ~ t^k, over geometrically spaced
windows: k near 0 is bounded, k near 1 is secular drift, k near 1/2 is a random walk of round-off.

The order checks cannot see this: RK4 and leapfrog both converge at their order on a short interval; only a long
run separates them.
"""

from __future__ import annotations

import numpy as np

from .checks import FAIL, INCONCLUSIVE, PASS, Result


def drift_exponent(t, q, *, windows: int = 8, floor: float = 0.0) -> tuple[float, np.ndarray, np.ndarray]:
    """(k, window ends, envelope): the slope of log max|q - q0| against log t over `windows` geometric windows.

    Window i covers (t_end * 2^(i - windows), t_end * 2^(i + 1 - windows)]; the envelope is the largest error in it,
    raised to `floor` so that an error at round-off does not look like growth."""
    t = np.asarray(t, dtype=float)
    q = np.asarray(q, dtype=float)
    err = np.maximum(np.abs(q - q[0]), floor)
    t = t - t[0]
    tend = t[-1]
    ends, env = [], []
    for i in range(windows):
        lo, hi = tend * 2.0 ** (i - windows), tend * 2.0 ** (i + 1 - windows)
        m = (t > lo) & (t <= hi)
        if m.any() and err[m].max() > 0:
            ends.append(hi)
            env.append(err[m].max())
    ends, env = np.array(ends), np.array(env)
    if len(env) < 3:
        return float("nan"), ends, env
    return float(np.polyfit(np.log(ends), np.log(env), 1)[0]), ends, env


def check_energy_drift(t, q, *, expect: str = "bounded", max_bounded: float = 0.2, min_secular: float = 0.8,
                       max_rel: float = 0.1, qscale: float | None = None, windows: int = 10, min_samples: int = 200,
                       rtol_floor: float = 1e-13, label: str = "") -> Result:
    """Is the error of a conserved quantity `q` sampled at times `t` (one long run) bounded or drifting?

    expect="bounded" (a symplectic or time-reversible method on a Hamiltonian problem): PASS if the growth exponent
    k <= `max_bounded` and the largest error is at most `max_rel` relative, FAIL if k >= `min_secular` or the error
    exceeds `max_rel` (an energy that decays and levels off has k near 0 but has lost the energy). expect="drift"
    (a dissipative method, to confirm a test can tell): PASS if k >= `min_secular`. Between the thresholds is
    INCONCLUSIVE (k near 1/2 is often round-off random walk; run longer). The error is relative to `qscale`, by
    default |q0|; pass the size of the terms for a quantity that is zero (a total momentum). Errors below
    `rtol_floor * qscale` count as round-off. A non-finite value is a FAIL. Fewer than `min_samples` samples is
    INCONCLUSIVE. Use at least a few hundred periods, sampled evenly or densely: the shortest window is
    t_end / 2^windows and should cover at least one period, or a bounded error reads as growth.

    False alarms, measured: on 1000 pure random walks (200001 samples, the shape of accumulated round-off) neither
    verdict was given with the defaults; with thresholds 0.3/0.7 and 8 windows, 5% were called secular. Leapfrog and
    explicit RK2 on the pendulum (h = 0.1, 300 periods) gave k = 0.01 and 1.01."""
    if expect not in ("bounded", "drift"):
        raise ValueError("expect must be 'bounded' or 'drift'")
    prefix = f"{label}: " if label else ""
    t = np.asarray(t, dtype=float)
    q = np.asarray(q, dtype=float)
    if t.shape != q.shape or q.size < 2:
        raise ValueError("t and q must be 1-D arrays of the same length (at least 2)")
    bad = ~np.isfinite(q)
    if bad.any():
        i = int(np.argmax(bad))
        return Result(FAIL, prefix + f"the quantity is not finite from t = {t[i]:.6g} on (sample {i} of {q.size}):"
                                     " the run blew up or produced NaN")
    if q.size < min_samples:
        return Result(INCONCLUSIVE, prefix + f"only {q.size} samples; the growth of the error needs a long, densely"
                                             f" sampled run (at least {min_samples} samples, a few hundred periods)")
    scale = float(qscale) if qscale is not None else abs(float(q[0]))
    if scale == 0:
        return Result(INCONCLUSIVE, prefix + "q0 is 0, so a relative error means nothing; pass qscale, the size of the"
                                             " terms of the quantity (for a total momentum, max |p_i|)")
    floor = rtol_floor * scale
    k, ends, env = drift_exponent(t, q, windows=windows, floor=floor)
    if not np.isfinite(k):
        return Result(INCONCLUSIVE, prefix + "too few samples in the time windows to fit the growth of the error")
    rel = float(np.max(np.abs(q - q[0]))) / scale
    shown = (f"error envelope |q - q0| ~ t^{k:.2f} over the last {len(env)} doublings of time"
             f" (largest relative error {rel:.1e})")
    if env.max() <= floor * 1.0000001:
        return Result(PASS if expect == "bounded" else INCONCLUSIVE,
                      prefix + f"the quantity is conserved to round-off ({rtol_floor:g} relative) for the whole run")
    if k < min_secular and expect == "bounded" and rel > max_rel:
        return Result(FAIL, prefix + f"{shown}: the error stopped growing but exceeds {max_rel:g} of the quantity, so it"
                                     " is not conserved (a decay that levels off also has k near 0)")
    if k <= max_bounded:
        verdict = PASS if expect == "bounded" else FAIL
        what = "bounded, as for a symplectic or time-reversible method"
    elif k >= min_secular:
        verdict = FAIL if expect == "bounded" else PASS
        what = "growing with time (secular drift), as for a non-symplectic or dissipative method"
    else:
        return Result(INCONCLUSIVE, prefix + f"{shown}; between bounded and secular, run longer or check for round-off")
    return Result(verdict, prefix + f"{shown}: {what}")
