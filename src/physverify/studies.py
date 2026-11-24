"""Order studies other than MMS, and a helper that bundles them for an ODE code."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from .checks import FAIL, PASS, Check, OrderResult, Result, within_budget
from .mms import (
    ManufacturedODE,
    max_abs_error,
    mms_order_study,
    mms_trajectory_study,
    zero_source,
)
from .order import check_exact, check_order
from .steppers import integrate_fixed, rk4


def reference_study(integrate, rhs_ref, y0, t_end, ns, expected_order, ref_factor=16, **kw) -> OrderResult:
    """Compare with a reference solution from an independent right-hand side.

    The reference is RK4 on `rhs_ref` with ref_factor times the finest step
    count, so its own error is negligible next to the code under test.
    """
    y_ref = integrate_fixed(rhs_ref, y0, 0.0, t_end, ref_factor * max(ns), rk4)
    kw.setdefault("scale", float(np.max(np.abs(y_ref))))
    hs, errs = [], []
    for n in within_budget(ns):
        hs.append(t_end / n)
        errs.append(max_abs_error(integrate(zero_source, y0, t_end, n), y_ref))
    return check_order(hs, errs, expected_order, **kw)


def invariant_study(integrate, quantity, y0, t_end, ns, expected_order, *, qscale=None, **kw) -> OrderResult:
    """Relative drift of a conserved quantity at t_end as the step shrinks.

    Drift is only required to shrink at least as fast as the scheme's order.
    RK4 on a pendulum, for example, drifts in energy at about order 5, so a
    drift that converges faster than expected is not a failure here.

    The drift is divided by `qscale`, by default |q0| (1 if q0 is exactly 0), so an
    invariant in SI units (an energy of 1e-21 J) is judged on its own size. For a
    quantity that is zero up to round-off, such as a total momentum of 1e-17,
    pass the size of its terms, for example qscale=max(abs(p_i)).
    """
    kw.setdefault("tol_high", float("inf"))
    q0 = float(quantity(np.asarray(y0, dtype=float)))
    # relative drift; the earlier max(|q0|, 1) hid any drift of a small invariant (an energy of 1e-21 J was EXACT)
    scale = float(qscale) if qscale is not None else (abs(q0) if q0 != 0 else 1.0)
    hs, errs = [], []
    for n in within_budget(ns):
        with np.errstate(all="ignore"):
            y_end = np.asarray(integrate(zero_source, y0, t_end, n), dtype=float)
            drift = abs(float(quantity(y_end)) - q0) / scale
        hs.append(t_end / n)
        errs.append(drift)
    result = check_order(hs, errs, expected_order, **kw)
    if qscale is None and q0 != 0 and not result.ok and max(errs, default=0) * abs(q0) < 1e-12:
        result.message += (f"; the invariant is small (q0 = {q0:.3g}) and the drift is relative to it: if it is zero up"
                           " to round-off (a total momentum, say), pass qscale with the size of its terms")
    return result


def linear_manufactured(rhs_ref: Callable, y0, slope) -> ManufacturedODE:
    """u(t) = y0 + slope * t, with its forcing taken from the reference operator."""
    y0 = np.asarray(y0, dtype=float)
    slope = np.asarray(slope, dtype=float)
    return ManufacturedODE(lambda t: y0 + slope * t, rhs_ref, du=lambda t: slope)


def patch_study(integrate, rhs_ref, y0, slope, t_end, ns, *, floor=1e-11) -> OrderResult:
    """Exactness test for an ODE code: a manufactured solution linear in t.

    Every consistent explicit Runge-Kutta method (Euler, midpoint, RK4, ...)
    reproduces u(t) = y0 + slope * t exactly, whatever the step: each stage
    lands on u at its own stage time, so each stage derivative is exactly
    `slope`, and weights that sum to one return y0 + slope * (t + h). So any
    error above round-off is a bug, including bugs whose error shrinks at the
    scheme's own order (an extra step for Euler, a wrong stage time) that every
    order-of-convergence check accepts. See docs/patch.md.

    It does not see a wrong but consistent stepper (Euler in place of RK4 is
    still exact here): the order studies cover that.
    """
    mms = linear_manufactured(rhs_ref, y0, slope)
    exact = mms.value(t_end)
    hs, errs = [], []
    for n in within_budget(ns):
        y_end = integrate(mms.forcing, mms.value(0.0), t_end, n)
        hs.append(t_end / n)
        errs.append(max_abs_error(y_end, exact))
    return check_exact(hs, errs, floor=floor, scale=float(np.max(np.abs(exact))))


def smoke_check(label, integrate, rhs_ref, y0, t_end, n, *, rtol=1e-3) -> Check:
    """What an ordinary unit test would do: one run, compared with a reference within a tolerance.

    Not one of the verification families. It is here so that the benchmark can
    report what a plain test would have caught (see the benchmark comparison, pvbench.compare).
    """

    def run():
        y_ref = integrate_fixed(rhs_ref, y0, 0.0, t_end, 16 * n, rk4)
        y = np.asarray(integrate(zero_source, y0, t_end, n), dtype=float)
        return close_result(y, y_ref, rtol)

    return Check("smoke", label, run)


def close_result(value, expected, rtol) -> Result:
    value = np.asarray(value, dtype=float)
    expected = np.asarray(expected, dtype=float)
    with np.errstate(all="ignore"):
        err = float(np.max(np.abs(value - expected)) / max(float(np.max(np.abs(expected))), 1e-300))
    if np.isfinite(err) and err <= rtol:
        return Result(PASS, f"relative difference {err:.2g} within {rtol:g}")
    return Result(FAIL, f"relative difference {err:.3g} exceeds {rtol:g}")


def ode_checks(
    label: str,
    integrate: Callable,
    *,
    rhs_ref: Callable,
    mms: ManufacturedODE,
    y0_free,
    t_end: float,
    ns,
    order: float,
    quantity: Callable | None = None,
    floor: float = 1e-12,
    patch: tuple | None = None,
    integrate_trajectory: Callable | None = None,
) -> list[Check]:
    """The standard bundle for an ODE code: MMS, reference solution, invariant.

    patch                 (y0, slope) of a linear manufactured solution; adds the exactness check
    integrate_trajectory  same contract as `integrate` but returning every state; adds an MMS
                          check on the largest error over the whole run
    """
    checks = [
        Check("mms", label, lambda: mms_order_study(integrate, mms, t_end, ns, order, floor=floor)),
        Check("reference", label, lambda: reference_study(integrate, rhs_ref, y0_free, t_end, ns, order, floor=floor)),
    ]
    if integrate_trajectory is not None:
        checks.append(
            Check(
                "mms",
                f"{label} (whole trajectory)",
                lambda: mms_trajectory_study(integrate_trajectory, mms, t_end, ns, order, floor=floor),
            )
        )
    if quantity is not None:
        checks.append(
            Check("invariant", label, lambda: invariant_study(integrate, quantity, y0_free, t_end, ns, order, floor=floor))
        )
    if patch is not None:
        p_y0, p_slope = patch
        checks.append(Check("patch", label, lambda: patch_study(integrate, rhs_ref, p_y0, p_slope, t_end, ns)))
    return checks


def time_grid_check(times_of_run: Callable, t_start: float, t_stop: float, ns, *, tol: float = 1e-9) -> Result:
    """The run stops at t_stop after exactly n steps, for step sizes that divide the interval.

    `times_of_run(n)` runs the code with step (t_stop - t_start) / n and returns
    the times it reports. A loop such as `while t <= t_end: t += h` takes one step
    too many whenever t lands exactly on t_end in floating point (h = 0.5, 0.25)
    and the right number otherwise (h = 0.1), so include step sizes that are
    exact in binary. An order study that compares at the time nearest t_stop
    cannot see this; this check can.
    """
    bad = []
    for n in ns:
        t = np.asarray(times_of_run(n), dtype=float)
        if t.ndim == 2 and t.shape[1] == 1:
            t = t[:, 0]  # a column of times is still one time per step
        h = abs(t_stop - t_start) / n
        if t.size == 0:
            bad.append(f"h={h:g}: no times returned (expected {n + 1})")
        elif t.ndim != 1 or not np.all(np.isfinite(t)):
            bad.append(f"h={h:g}: expected a one-dimensional time grid with no non-finite values")
        elif len(t) != n + 1 or not abs(t[-1] - t_stop) <= tol * max(1.0, abs(t_stop)):
            bad.append(f"h={h:g}: {len(t) - 1} steps ending at t={t[-1]:.6g} (expected {n} ending at {t_stop:g})")
    if bad:
        return Result(FAIL, "; ".join(bad))
    return Result(PASS, f"ends at t={t_stop:g} with the expected number of steps for every h tested")


def backward_mms_study(integrate_back: Callable, mms: ManufacturedODE, t_end: float, ns, expected_order, **kw) -> OrderResult:
    """MMS order study integrating from t_end back to 0.

    `integrate_back(source, y_end, t_end, n)` integrates y' = f(t, y) + source(t)
    from t_end down to 0 in n steps and returns y(0). Use a manufactured solution
    whose forcing depends on t: a code that evaluates its stages at t + h/2 while
    stepping backwards still passes on autonomous problems but drops to first
    order here.
    """
    y_end = mms.value(t_end)
    y_0 = mms.value(0.0)
    kw.setdefault("scale", float(np.max(np.abs(y_0))))
    hs, errs = [], []
    for n in within_budget(ns):
        hs.append(t_end / n)
        errs.append(max_abs_error(integrate_back(mms.forcing, y_end, t_end, n), y_0))
    return check_order(hs, errs, expected_order, **kw)


def balance_check(measure: Callable, expected: float, resolutions, *, tol: float = 1e-9, label: str = "") -> Result:
    """Check an exact discrete balance at every resolution: `measure(n)` must equal `expected` to `tol`.

    A conservative scheme keeps a budget exactly on every grid: the total heat with
    insulated walls, the heat gained from a known boundary flux or source over a run.
    Three real codes failed such a budget while still converging: a zero-flux wall
    made by copying the neighbour value lost 8.5% of the heat, a source added
    without the factor dt depended on the number of steps, and boundary nodes
    given full cells took in 7% too much heat. A convergence study alone can pass
    these, so the check reports whether the mismatch shrinks with resolution.
    """
    rows = []
    for n in resolutions:
        rows.append((n, float(measure(n))))
    bad = [(n, v) for n, v in rows if not abs(v - expected) <= tol]
    prefix = f"{label}: " if label else ""
    listing = ", ".join(f"n={n}: {v:.6g}" for n, v in rows)
    if not bad:
        return Result(PASS, f"{prefix}balance {expected:.6g} kept to {tol:g} at every resolution ({listing})")
    gaps = [abs(v - expected) for _, v in rows]
    shrinking = len(gaps) > 1 and all(b < a for a, b in zip(gaps, gaps[1:]))
    hint = ("; the mismatch shrinks with resolution, so the scheme converges but does not conserve"
            if shrinking else "")
    return Result(FAIL, f"{prefix}expected {expected:.6g}, got {listing}{hint}")


def size_sweep_check(run_at_size: Callable, sizes=(15, 16, 31, 32, 63, 64), *, label: str = "") -> Result:
    """Call `run_at_size(n)` for odd and even sizes; FAIL if it raises for some of them.

    Spectral and FFT-based codes often build their wavenumber arrays by splitting
    the grid in two halves, which only works for even n. A real code raised a
    ValueError for every odd grid size while being exact for even ones; an order
    study on 16, 32, 64, 128 points cannot see that. `run_at_size` may also
    return False to mark a wrong result at that size.
    """
    bad = []
    for n in sizes:
        try:
            ok = run_at_size(n)
        except Exception as exc:  # the code under test may crash; that is the finding
            bad.append(f"n={n}: {type(exc).__name__}: {exc}")
            continue
        if ok is False:
            bad.append(f"n={n}: wrong result")
    prefix = f"{label}: " if label else ""
    if bad:
        return Result(FAIL, prefix + "; ".join(bad))
    return Result(PASS, f"{prefix}runs for every size tested ({', '.join(map(str, sizes))})")


def damped_sinusoid_fit(t, y, t_start: float, t_stop: float) -> complex:
    """Complex frequency omega_R - i gamma of y ~ A exp(-gamma t) cos(omega_R t + phi) on [t_start, t_stop].

    Two-pole Prony fit (linear prediction y_n = a1 y_{n-1} + a2 y_{n-2} by least squares on a uniform grid), so no
    starting guess is needed. Start the window after the direct pulse has passed the observer and stop before the
    late-time tail or reflections dominate; a window that includes the pulse gave a wrong frequency for a real
    ringdown code (J216). Returns omega_R - i gamma with omega_R >= 0, to compare with tabulated quasinormal modes
    (references.schwarzschild_qnm) or any damped oscillator.
    """
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    m = (t >= t_start) & (t <= t_stop)
    tt, yy = t[m], y[m]
    if len(yy) < 8:
        raise ValueError("need at least 8 samples in the window")
    dt = np.diff(tt)
    if np.max(np.abs(dt - dt.mean())) > 1e-6 * dt.mean():
        raise ValueError("the samples in the window must be uniformly spaced")
    M = np.column_stack([yy[1:-1], yy[:-2]])
    a1, a2 = np.linalg.lstsq(M, yy[2:], rcond=None)[0]
    z = np.roots([1.0, -a1, -a2]).astype(complex)
    s = np.log(z[np.argmax(z.imag)]) / dt.mean()  # s = -gamma + i omega_R
    return complex(abs(s.imag), s.real)


def trajectory_order_study(runs, exact: Callable, t_compare: float, expected_order, *, period: float | None = None,
                           time_tol: float = 1e-9, **kw) -> OrderResult:
    """Order study from whole trajectories, compared at one fixed time, guarding against the usual study-design
    pitfalls (batch 7 of the corpus study).

    `runs` is a list of (t, y) pairs, one per step size, as the code under test returns them; `exact(t)` is the
    solution. Each run is compared at `t_compare`, found on its own time grid; the step size is the run's mean step.

    Pitfalls it catches:
    * A run whose grid does not contain `t_compare`: a loop over `int(t_end / h)` steps stops one step early
      (int(2 pi / (2 pi / 200)) = 199), which made an order-4 method look first order (J348). FAIL, naming the run
      and where it ended; it is the study, or the code's step count, that is wrong.
    * Comparing arrays index by index, or a maximum over the last N samples, moves the comparison time with h
      (J155). Comparing at one time on every grid avoids both.
    * `t_compare` a whole number of periods: errors in the phase can cancel there, and a symplectic Euler showed
      order 2 (J155). Noted in the message, with the advice to also compare at a time that is not a multiple.
    """
    hs, errs, problems = [], [], []
    for k, (t, y) in enumerate(runs):
        t = np.asarray(t, dtype=float)
        y = np.asarray(y, dtype=float)
        if len(t) < 2:
            problems.append(f"run {k} has fewer than two samples")
            continue
        h = float(np.mean(np.diff(t)))
        i = int(np.argmin(np.abs(t - t_compare)))
        if abs(t[i] - t_compare) > time_tol * max(1.0, abs(t_compare)) + 1e-9 * abs(h):
            problems.append(f"run {k} (h = {h:.3g}) has no sample at t = {t_compare:g}; it ends at t = {t[-1]:.9g}"
                            + (f", {round((t_compare - t[-1]) / h)} step(s) short (a loop over int(t_end / h) steps?)"
                               if t[-1] < t_compare else ""))
            continue
        hs.append(abs(h))
        errs.append(max_abs_error(y[i], exact(float(t[i]))))
    if problems:
        return OrderResult(FAIL, "the comparison time is not on every grid: " + "; ".join(problems),
                           expected=expected_order, hs=tuple(hs), errors=tuple(errs))
    result = check_order(hs, errs, expected_order, **kw)
    if period:
        cycles = t_compare / period
        if abs(cycles - round(cycles)) < 1e-6 and round(cycles) != 0:
            result.message += (f"; t = {t_compare:g} is {round(cycles)} whole period(s), where phase errors can cancel"
                                " and show a higher order than the method has: compare at a time that is not a multiple too")
    return result


def _binom_two_sided_p(k: int, n: int, p: float) -> float:
    """Exact two-sided binomial p-value (sum of outcomes no more likely than k)."""
    from math import exp, lgamma, log

    def logpmf(j):
        return lgamma(n + 1) - lgamma(j + 1) - lgamma(n - j + 1) + j * log(p) + (n - j) * log(1 - p)

    ref = logpmf(k) + 1e-9
    return min(1.0, sum(exp(logpmf(j)) for j in range(n + 1) if logpmf(j) <= ref))


def coverage_check(simulate: Callable, interval: Callable, prior_sampler: Callable, *, level: float = 0.68,
                   trials: int = 400, seed: int = 0, alpha: float = 1e-3, label: str = "") -> Result:
    """Frequentist coverage of an inference code: the stated `level` interval should contain the truth in that
    fraction of repeated experiments.

    Each trial draws the truth from `prior_sampler(rng)`, simulates data with `simulate(theta, rng)` and asks
    `interval(data, level)` for (low, high). The truth must come from the same prior the analysis assumes:
    drawing it from a narrower range gave a spurious coverage of 0.865 for a nominal 0.68 interval (J399), which
    is why the prior sampler is a required argument and not a fixed truth. For a frequentist (not Bayesian)
    interval any fixed truth works; pass a sampler that returns it.

    FAIL when an exact binomial test rejects the stated level at `alpha` (two-sided; the false-alarm rate of
    a correct code is at most `alpha`). Scalar parameters; for vectors, check each component separately.
    """
    rng = np.random.default_rng(seed)
    hits = 0
    for _ in range(trials):
        theta = prior_sampler(rng)
        lo, hi = interval(simulate(theta, rng), level)
        hits += bool(lo <= theta <= hi)
    p = _binom_two_sided_p(hits, trials, level)
    prefix = f"{label}: " if label else ""
    msg = (f"{prefix}{hits} of {trials} intervals contain the truth ({hits / trials:.3f}, stated {level}); "
           f"binomial p = {p:.1e}, false-alarm rate {alpha:g}")
    return Result(FAIL if p < alpha else PASS, msg)


def decay_rate(t, y, *, t_skip: float | None = None, windows: int = 8, steady_tol: float = 0.05) -> tuple[float, float]:
    """Exponential decay rate gamma of |y| ~ A exp(-gamma t), and the time the fit starts.

    A run started from a state that is not a single decaying mode has a start-up transient (a shear wave
    started from equilibrium, a heat profile with higher harmonics); fitting from t = 0 gives the wrong
    rate (batch 7). With `t_skip` the fit uses t >= t_skip. Without it, the record is cut into `windows`
    pieces, the local rate is fitted on each, and the fit starts at the first piece after which every
    local rate stays within `steady_tol` (relative) of the last one. Returns (gamma, t_start). What is left of
    the transient after the start biases the rate by up to about `steady_tol`; lower it (and use more
    windows) for a tighter fit, or pass `t_skip`.

    `y` should be a positive amplitude (an energy, a mode amplitude, an envelope); for an oscillating
    signal use `damped_sinusoid_fit`. Raises ValueError when no steady stretch is found.
    """
    t = np.asarray(t, dtype=float)
    y = np.abs(np.asarray(y, dtype=float))
    ok = np.isfinite(y) & (y > 0)
    t, y = t[ok], y[ok]
    if t.size < 2 * windows:
        raise ValueError(f"need at least {2 * windows} positive samples")
    ly = np.log(y)
    if t_skip is None:
        edges = np.linspace(t[0], t[-1], windows + 1)
        window_rates = []
        for a, b in zip(edges[:-1], edges[1:]):
            m = (t >= a) & (t <= b)
            window_rates.append(-np.polyfit(t[m], ly[m], 1)[0] if m.sum() >= 2 else np.nan)
        rates = np.array(window_rates)
        last = rates[-1]
        steady = np.abs(rates - last) <= steady_tol * abs(last)
        start = None
        for i in range(windows):
            if np.all(steady[i:]):
                start = i
                break
        if start is None or start == windows - 1:
            raise ValueError("the local decay rate does not settle; pass t_skip, or use a longer record")
        t_skip = float(edges[start])
    m = t >= t_skip
    if m.sum() < 2:
        raise ValueError("fewer than two samples after t_skip")
    return float(-np.polyfit(t[m], ly[m], 1)[0]), float(t_skip)


def residual_check(solve: Callable, residual: Callable, tols=(1e-4, 1e-6, 1e-8), *, slack: float = 10.0,
                   label: str = "") -> Result:
    """An iterative solver that is asked for tolerance tol returns an answer whose residual is about tol.

    `solve(tol)` returns the solution, `residual(x)` its residual computed independently (for example the
    norm of b - A x). PASS when residual <= slack * tol for every tol. A residual that does not follow the
    requested tolerance is the sign of a solver that does almost no work: a real pressure solver did one
    Jacobi sweep whatever the tolerance, and its answers looked plausible.
    """
    rows = []
    for tol in tols:
        r = float(residual(solve(tol)))
        rows.append((tol, r))
    prefix = f"{label}: " if label else ""
    table = ", ".join(f"tol {tol:g} -> residual {r:.3g}" for tol, r in rows)
    bad = [(tol, r) for tol, r in rows if not (np.isfinite(r) and r <= slack * tol)]
    if not bad:
        return Result(PASS, f"{prefix}residual follows the requested tolerance ({table})")
    rs = np.array([r for _, r in rows])
    msg = f"{prefix}residual above {slack:g} x tolerance ({table})"
    if len(rows) >= 2 and np.all(np.isfinite(rs)) and rs.max() <= 1.5 * rs.min():
        msg += ("; it hardly changes with the tolerance, so the solver may stop after a fixed number of iterations"
                " or not iterate at all")
    return Result(FAIL, msg)
