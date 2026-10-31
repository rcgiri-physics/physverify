"""Observed order of accuracy from errors at several resolutions."""

from __future__ import annotations

import numpy as np

from .checks import EXACT, FAIL, INCONCLUSIVE, PASS, OrderResult


def pairwise_orders(hs, errors) -> np.ndarray:
    """p_i = log(e_i / e_{i+1}) / log(h_i / h_{i+1}) for consecutive resolutions."""
    hs = np.asarray(hs, dtype=float)
    errs = np.asarray(errors, dtype=float)
    return np.log(errs[:-1] / errs[1:]) / np.log(hs[:-1] / hs[1:])


def fit_order(hs, errors) -> float:
    """Least-squares slope of log(error) against log(h)."""
    return float(np.polyfit(np.log(hs), np.log(errors), 1)[0])


def fit_order_error(hs, errors) -> tuple[float, float]:
    """(order, standard error): the least-squares slope of log(error) against log(h) and its standard error
    from the scatter about the line (needs at least three points; two give an error of nan). A fitted 3.9 with
    standard error 0.05 supports order 4; 3.9 with 0.6 supports nothing yet."""
    x, y = np.log(np.asarray(hs, float)), np.log(np.asarray(errors, float))
    if x.size < 3:
        return fit_order(hs, errors), float("nan")
    (slope, icpt), = [np.polyfit(x, y, 1)]
    resid = y - (slope * x + icpt)
    se = float(np.sqrt(np.sum(resid ** 2) / (x.size - 2) / np.sum((x - x.mean()) ** 2)))
    return float(slope), se


def gci(f_fine: float, f_medium: float, f_coarse: float, r: float, *, safety: float = 1.25) -> dict:
    """Grid convergence index of three solutions on grids refined by the constant ratio r (Roache 1994;
    Celik et al., J. Fluids Eng. 130, 078001, 2008): the observed order p = ln(e32/e21) / ln r, the Richardson
    extrapolate, and GCI_fine = safety |e21 / f_fine| / (r^p - 1), a relative error band on the fine solution.
    Oscillatory convergence (e21 and e32 of opposite sign) is reported, and then p is nan."""
    e21, e32 = f_medium - f_fine, f_coarse - f_medium
    if e21 == 0 or e32 == 0 or e21 * e32 < 0:
        return {"order": float("nan"), "extrapolated": float("nan"), "gci_fine": float("nan"),
                "oscillatory": e21 * e32 < 0, "converged": e21 == 0}
    p = np.log(abs(e32 / e21)) / np.log(r)
    ext = f_fine + (f_fine - f_medium) / (r ** p - 1)
    g = safety * abs(e21 / f_fine) / (r ** p - 1) if f_fine != 0 else float("nan")
    return {"order": float(p), "extrapolated": float(ext), "gci_fine": float(g), "oscillatory": False, "converged": False}


def effective_floor(floor: float, scale: float, rel: float = 1e-13) -> float:
    """Round-off grows with the size of the solution, so the noise floor does too.

    The floor is the larger of the absolute `floor` (right for solutions of size
    up to about 10) and `rel` times the solution's size (about 500 machine
    epsilons, room for round-off accumulated over a few hundred steps). A
    non-finite scale (a diverged run) leaves the floor unchanged so that the
    non-finite error is still reported.
    """
    scale = abs(float(scale))
    if not np.isfinite(scale):
        return floor
    return max(floor, rel * scale)


def check_exact(hs, errors, *, floor: float = 1e-12, scale: float = 1.0) -> OrderResult:
    """Require the error to be at round-off level at every resolution.

    For a manufactured solution that lies inside the scheme's discrete solution
    space (a "patch test": for example, polynomials a finite-difference stencil
    differentiates exactly), a correct code reproduces it to round-off whatever
    the step sizes. Order of convergence cannot see an error that is as small
    as the scheme's own truncation error and shrinks at the same rate; this
    can, because the expected error is zero rather than small.

    EXACT  every error is at most `floor`
    FAIL   some error is larger, or non-finite

    `scale` is the size of the solution; see `effective_floor`.
    """
    floor = effective_floor(floor, scale)
    hs = np.asarray(hs, dtype=float)
    errs = np.asarray(errors, dtype=float)
    order = np.argsort(-hs)
    hs, errs = hs[order], errs[order]
    base = dict(expected=float("inf"), hs=tuple(hs), errors=tuple(errs),
                acceptance=f"every error at most {floor:.2g} (round-off)")
    if not np.all(np.isfinite(errs)):
        return OrderResult(FAIL, "non-finite error: the solution diverged or produced NaN", **base)
    worst = float(errs.max())
    if worst <= floor:
        return OrderResult(EXACT, f"reproduced to round-off (largest error {worst:.2g}), as designed", **base)
    msg = f"expected an exact solution to round-off, but the error reaches {worst:.3g}"
    measurable = errs > floor
    fitted = float("nan")
    if measurable.sum() >= 3:
        fitted = fit_order(hs[measurable], errs[measurable])
        msg += f" and shrinks at about order {fitted:.2f}"
    return OrderResult(FAIL, msg, fitted=fitted, **base)


def check_order(
    hs,
    errors,
    expected: float,
    *,
    tol_low: float = 0.3,
    tol_high: float = 1.0,
    floor: float = 1e-12,
    fit_points: int = 4,
    scale: float = 1.0,
    tol: float | None = None,
    atol: float | None = None,
) -> OrderResult:
    """Compare the observed order of convergence with the order the code claims.

    PASS      fitted order lies in [expected - tol_low, expected + tol_high]
    EXACT     every error is below `floor`, so the order cannot be measured
    FAIL      order too low or too high, error plateau, or non-finite error
    INCONCLUSIVE  fewer than two resolutions are above the noise floor

    `floor` is the error level below which round-off dominates, for a solution
    of size about 1. Pass `scale` (the size of the solution, for example the
    largest absolute value of the exact answer) and the floor grows with it.

    `tol` sets tol_low and tol_high to the same value (a common way to write it; without the alias an
    adapter that wrote `tol=` failed with a TypeError after its whole run).

    `atol` adds an accuracy requirement on the finest resolution. It is reported separately: when the order
    is as claimed and only `atol` is missed, the message says so, because that is a question of how fine the
    grid must be, not a convergence bug (batch 7 had an adapter whose absolute tolerance failed while the
    observed order was exactly as claimed).
    """
    if tol is not None:
        tol_low = tol_high = float(tol)
    floor = effective_floor(floor, scale)
    hs = np.asarray(hs, dtype=float)
    errs = np.asarray(errors, dtype=float)
    if hs.shape != errs.shape:
        return OrderResult(INCONCLUSIVE, f"{hs.size} step sizes but {errs.size} errors; they must match",
                           expected=float(expected), hs=tuple(hs), errors=tuple(errs))
    order = np.argsort(-hs)  # coarse to fine
    hs, errs = hs[order], errs[order]
    base = dict(expected=float(expected), hs=tuple(hs), errors=tuple(errs),
                acceptance=f"fitted order within [{expected - tol_low:g}, {expected + tol_high:g}] on errors above {floor:.2g}")

    if not np.all(np.isfinite(hs) & (hs > 0)):
        return OrderResult(INCONCLUSIVE, "step sizes must be positive and finite; check how h is computed", **base)
    if len(np.unique(hs)) < 2:
        return OrderResult(INCONCLUSIVE, "all step sizes are the same, so no order can be measured; use at least two"
                           " different resolutions", **base)

    if not np.all(np.isfinite(errs)):
        return OrderResult(FAIL, "non-finite error: the solution diverged or produced NaN", **base)

    measurable = errs > floor
    if not measurable.any():
        return OrderResult(EXACT, f"error below {floor:g} at every resolution; order not measurable", **base)

    h_m, e_m = hs[measurable], errs[measurable]
    if len(e_m) < 2:
        return OrderResult(INCONCLUSIVE, f"fewer than 2 resolutions above the noise floor ({floor:.2g}); the errors are"
                           f" near round-off already (largest {errs.max():.2g}), so use coarser resolutions", **base)

    if e_m[-2] / e_m[-1] < 1.2:
        msg = f"error does not decrease with resolution (about {e_m[-1]:.3g} at the finest level)"
        if e_m[0] < 1e3 * floor:
            msg += ("; even the coarsest error is within a factor 1000 of the noise floor, so round-off may already"
                    " dominate: use coarser resolutions")
        if len(e_m) >= 3 and e_m.max() / e_m.min() < 1.1:
            # seen in a real MD code: one pair crossing an unshifted cutoff adds V(rc) to the energy, whatever dt is
            msg += ("; the error is the same at every resolution, which points to something independent of the step"
                    " (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a"
                    " different problem) rather than to the integrator")
        return OrderResult(FAIL, msg, fitted=0.0, **base)

    h_f, e_f = h_m[-fit_points:], e_m[-fit_points:]
    p = fit_order(h_f, e_f)
    if p < expected - tol_low:
        msg = f"observed order {p:.2f} is below the expected {expected:g}"
        pairs = pairwise_orders(h_f, e_f)
        if len(pairs) >= 2 and np.all(np.diff(pairs) > 0) and pairs[-1] >= expected - tol_low:
            msg += (f"; the pairwise orders ({', '.join(f'{q:.2f}' for q in pairs)}) are still rising and the last one"
                    " reaches it, so the steps may be too coarse (pre-asymptotic): repeat with finer steps before"
                    " calling this a bug")
        status = FAIL
        if np.any(np.diff(e_f) >= 0):
            msg += ("; the errors are not monotone over the fitted resolutions, which happens when the leading error"
                    " term changes sign or round-off is reached: try another test problem before calling this a bug")
    elif p > expected + tol_high:
        msg = f"observed order {p:.2f} is above the expected {expected:g}; check the expected order"
        status = FAIL
    else:
        msg = f"observed order {p:.2f} (expected {expected:g})"
        status = PASS
    if atol is not None:
        base["acceptance"] += f", and finest error at most {atol:g}"
        finest = float(errs[-1])
        if finest > atol:
            if status == PASS:
                msg = (f"observed order {p:.2f} is as claimed ({expected:g}), but the finest error {finest:.3g} is above"
                       f" the absolute tolerance {atol:g}: only the accuracy requirement fails, not the convergence; at"
                       f" this order it needs about {(finest / atol) ** (1 / p):.2g} times smaller steps")
            else:
                msg += f"; the finest error {finest:.3g} is also above the absolute tolerance {atol:g}"
            status = FAIL
    return OrderResult(status, msg, fitted=p, **base)
