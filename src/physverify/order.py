"""Observed order of accuracy from errors at several resolutions."""

from __future__ import annotations

from typing import Any

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
    slope, intercept = np.polyfit(x, y, 1)
    resid = y - (slope * x + intercept)
    se = float(np.sqrt(np.sum(resid ** 2) / (x.size - 2) / np.sum((x - x.mean()) ** 2)))
    return float(slope), se


def gci(f_fine: float, f_medium: float, f_coarse: float, r: float, *, safety: float = 1.25) -> dict:
    """Grid convergence index of three solutions on grids refined by the constant ratio r (Roache 1994;
    Celik et al., J. Fluids Eng. 130, 078001, 2008): the observed order p = ln(e32/e21) / ln r, the Richardson
    extrapolate, and GCI_fine = safety |e21 / f_fine| / (r^p - 1), a relative error band on the fine solution.
    Oscillatory convergence (e21 and e32 of opposite sign) is reported, and then p is nan. So is the case where
    the change between grids does not shrink on refinement (`not_converging`): the formula would give p <= 0 and
    a negative or huge error band, which means nothing."""
    e21, e32 = f_medium - f_fine, f_coarse - f_medium
    if e21 == 0 or e32 == 0 or e21 * e32 < 0:
        return {"order": float("nan"), "extrapolated": float("nan"), "gci_fine": float("nan"),
                "oscillatory": e21 * e32 < 0, "converged": e21 == 0, "not_converging": False}
    ratio = abs(e32 / e21)
    if ratio <= 1 or np.isclose(ratio, 1.0):
        return {"order": float("nan"), "extrapolated": float("nan"), "gci_fine": float("nan"),
                "oscillatory": False, "converged": False, "not_converging": True}
    p = np.log(ratio) / np.log(r)
    ext = f_fine + (f_fine - f_medium) / (r ** p - 1)
    g = safety * abs(e21 / f_fine) / (r ** p - 1) if f_fine != 0 else float("nan")
    return {"order": float(p), "extrapolated": float(ext), "gci_fine": float(g), "oscillatory": False, "converged": False,
            "not_converging": False}


def effective_floor(floor: float, scale: float, rel: float = 1e-13) -> float:
    """Round-off grows with the size of the solution, so the noise floor does too.

    For a solution smaller than 1 the floor shrinks in proportion. Otherwise it
    is the larger of the absolute `floor` (right for solutions of size up to about 10) and `rel` times the solution's size (about 500 machine
    epsilons, room for round-off accumulated over a few hundred steps). A
    non-finite scale (a diverged run) leaves the floor unchanged so that the
    non-finite error is still reported.
    """
    scale = abs(float(scale))
    if not np.isfinite(scale) or scale == 0:
        return floor
    if scale < 1:
        # round-off is relative: a solution of size 1e-21 has round-off near 1e-37, not 1e-12, so an absolute
        # floor would call any error on it EXACT (seen with an energy in SI units)
        return floor * scale
    return max(floor, rel * scale)


def _order_inputs(hs, errors, expected: float) -> tuple[np.ndarray, np.ndarray] | OrderResult:
    """Validate paired measurements before sorting them from coarse to fine."""
    hs = np.asarray(hs, dtype=float)
    errs = np.abs(np.asarray(errors, dtype=float))
    if hs.ndim != 1 or errs.ndim != 1:
        return OrderResult(INCONCLUSIVE, "step sizes and errors must be one-dimensional", expected=expected)
    if hs.shape != errs.shape:
        return OrderResult(INCONCLUSIVE, f"{hs.size} step sizes but {errs.size} errors; they must match",
                           expected=expected, hs=tuple(hs), errors=tuple(errs))
    if hs.size == 0:
        return OrderResult(INCONCLUSIVE, "no step sizes or errors were measured", expected=expected)
    order = np.argsort(-hs)
    return hs[order], errs[order]


def check_exact(hs, errors, *, floor: float = 1e-12, scale: float = 1.0) -> OrderResult:
    """Require the error to be at round-off level at every resolution.

    For a manufactured solution that lies inside the scheme's discrete solution
    space (a "patch test": for example, polynomials a finite-difference stencil
    differentiates exactly), a correct code reproduces it to round-off whatever
    the step sizes. Order of convergence cannot see an error that is as small
    as the scheme's own truncation error and shrinks at the same rate; this
    can, because the expected error is zero rather than small.

    EXACT  every error is at most `floor` in size
    FAIL   some error is larger, or non-finite
    INCONCLUSIVE  no paired measurements are available

    `scale` is the size of the solution; see `effective_floor`.
    """
    measurements = _order_inputs(hs, errors, float("inf"))
    if isinstance(measurements, OrderResult):
        return measurements
    hs, errs = measurements
    floor = effective_floor(floor, scale)
    base: dict[str, Any] = dict(expected=float("inf"), hs=tuple(hs), errors=tuple(errs),
                acceptance=f"every error at most {floor:.2g} (round-off)")
    if not np.all(np.isfinite(errs)):
        return OrderResult(FAIL, "non-finite error: the solution diverged or produced NaN", **base)
    worst = float(errs.max())
    if worst <= floor:
        return OrderResult(EXACT, f"reproduced to round-off (largest error {worst:.2g}), as designed", **base)
    msg = f"expected an exact solution to round-off, but the error reaches {worst:.3g}"
    measurable = errs > floor
    fitted = float("nan")
    if measurable.sum() >= 3 and len(np.unique(hs[measurable])) >= 2:
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
    INCONCLUSIVE  fewer than two distinct step sizes are available for the fit

    Errors may be signed (computed minus exact): their sizes are used, so a large negative error is not
    taken for round-off.

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
    measurements = _order_inputs(hs, errors, float(expected))
    if isinstance(measurements, OrderResult):
        return measurements
    hs, errs = measurements
    floor = effective_floor(floor, scale)
    base: dict[str, Any] = dict(expected=float(expected), hs=tuple(hs), errors=tuple(errs),
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
        if atol is not None:
            base["acceptance"] += f", and finest error at most {atol:g}"
            if errs[-1] > atol:
                # the floor decides whether a slope can be measured; atol is the caller's accuracy requirement
                return OrderResult(FAIL, f"error below the noise floor {floor:g} at every resolution, but the finest"
                                         f" error {errs[-1]:.3g} is above the absolute tolerance {atol:g}", **base)
        return OrderResult(EXACT, f"error below {floor:g} at every resolution; order not measurable (if the reference"
                                  " values were computed by the code under test, this shows nothing)", **base)

    h_m, e_m = hs[measurable], errs[measurable]
    if len(e_m) < 2:
        return OrderResult(INCONCLUSIVE, f"fewer than 2 resolutions above the noise floor ({floor:.2g}); the errors are"
                           f" near round-off already (largest {errs.max():.2g}), so use coarser resolutions", **base)

    # "No decrease" is a drop below 1.2 for halved steps (a local order of log2 1.2 = 0.26). With a smaller
    # refinement ratio even a correct code drops less, so the same local order sets the limit there.
    if e_m[-2] / e_m[-1] < min(1.2, (h_m[-2] / h_m[-1]) ** np.log2(1.2)):
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

    # errors within a factor 100 of the floor are partly round-off and pull the fitted order down; leave them out
    # of the fit when at least two cleaner points remain
    clean = e_m > 100 * floor
    near_floor = int(np.count_nonzero(~clean))
    if near_floor and np.count_nonzero(clean) >= 2:
        h_m, e_m = h_m[clean], e_m[clean]
    else:
        near_floor = 0
    h_f, e_f = h_m[-fit_points:], e_m[-fit_points:]
    distinct = len(np.unique(h_f))
    if distinct < 2:
        return OrderResult(INCONCLUSIVE, "the fit needs at least two distinct step sizes above the noise floor;"
                           " use different resolutions or increase fit_points", **base)
    p, se = fit_order_error(h_f, e_f)
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
        # a PASS is only as strong as the data behind it: say when it is thin
        if distinct < len(h_f):
            msg += (f"; the fit used {len(h_f)} points but only {distinct} distinct step sizes (repeated step sizes"
                    " are not independent evidence)")
        if distinct <= 2:
            msg += ("; with two step sizes the line passes through both points, so nothing checks that the error"
                    " follows a power law: add a third resolution")
        elif np.isfinite(se) and se > min(tol_low, tol_high):
            msg += (f"; the standard error of the fitted order ({se:.2f}) is larger than the tolerance, so the data"
                    " barely constrain it: add resolutions")
    if near_floor:
        msg += (f"; {near_floor} finest resolution(s) within a factor 100 of the noise floor ({floor:.2g}) were left"
                " out of the fit as round-off")
    if atol is not None:
        base["acceptance"] += f", and finest error at most {atol:g}"
        finest = float(errs[-1])
        if finest > atol:
            if status == PASS:
                msg = (f"observed order {p:.2f} is as claimed ({expected:g}), but the finest error {finest:.3g} is above"
                       f" the absolute tolerance {atol:g}: only the accuracy requirement fails, not the convergence")
                if atol > 0 and p > 0:
                    msg += f"; at this order it needs about {(finest / atol) ** (1 / p):.2g} times smaller steps"
            else:
                msg += f"; the finest error {finest:.3g} is also above the absolute tolerance {atol:g}"
            status = FAIL
    return OrderResult(status, msg, fitted=p, fitted_se=se, **base)


def _normal_quantile(p: float) -> float:
    """Inverse of the standard normal CDF (Acklam's rational approximation, relative error below 1.2e-9)."""
    a = (-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02, 1.383577518672690e02,
         -3.066479806614716e01, 2.506628277459239e00)
    b = (-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02, 6.680131188771972e01,
         -1.328068155288572e01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00, -2.549732539343734e00,
         4.374664141464968e00, 2.938163982698783e00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00, 3.754408661907416e00)
    if p < 0.02425:
        q = np.sqrt(-2 * np.log(p))
        return float((((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
                     / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1))
    if p > 1 - 0.02425:
        return -_normal_quantile(1 - p)
    q = p - 0.5
    r = q * q
    return float((((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
                 / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1))


def check_order_mc(hs, errors, stderr, expected: float, *, tol_low: float = 0.3, tol_high: float = 1.0,
                   tol: float | None = None, level: float = 0.99) -> OrderResult:
    """The order verdict for errors estimated by Monte Carlo, each with a standard error (strong order of an
    SDE scheme, a sampled error norm).

    Fits log(error) against log(h) by weighted least squares, with the standard error of each log(error) from
    the delta method, se/error. The slope's standard error is the larger of the one the supplied standard errors
    give and the one the scatter about the line gives (so errors that do not lie on a line are not hidden by
    small error bars). With the two-sided `level` confidence interval of the slope:

    PASS          the interval lies inside [expected - tol_low, expected + tol_high]
    FAIL          the interval lies wholly outside it
    INCONCLUSIVE  the interval overlaps the edge of the band: the error bars are too wide to tell, or the
                  input is unusable (fewer than three step sizes, non-positive errors or standard errors)

    Measured on synthetic data (2026-11-27; tests/test_order_mc.py repeats smaller runs), 20000 runs each, step
    sizes halving, Gaussian noise of 10% on each error with that standard error supplied, claim 1, default band:
    true order 1, 4 step sizes: no FAIL (1662 INCONCLUSIVE); true order 0.7, on the band's edge: 48 FAIL (0.24%,
    below the 0.5% the 99% interval allows); true order 0.5, 4 step sizes: 58% FAIL, the rest INCONCLUSIVE,
    no PASS; the same with 6 step sizes: 99.3% FAIL. These rates hold for this noise model, not in general."""
    if tol is not None:
        tol_low = tol_high = tol
    h = np.asarray(hs, dtype=float).ravel()
    e = np.asarray(errors, dtype=float).ravel()
    s = np.asarray(stderr, dtype=float).ravel()
    base: dict[str, Any] = dict(expected=expected, hs=tuple(h.tolist()), errors=tuple(e.tolist()))
    band = f"[{expected - tol_low:g}, {expected + tol_high:g}]"
    accept = f"the {level:.0%} confidence interval of the fitted order within {band}"
    if not (h.size == e.size == s.size):
        return OrderResult(INCONCLUSIVE, f"{h.size} step sizes, {e.size} errors and {s.size} standard errors: these"
                                         " must pair up", acceptance=accept, **base)
    if not (np.all(np.isfinite(h)) and np.all(np.isfinite(e)) and np.all(np.isfinite(s))):
        return OrderResult(FAIL, "a step size, error or standard error is NaN or inf", acceptance=accept, **base)
    if np.any(h <= 0) or np.any(e <= 0) or np.any(s <= 0):
        return OrderResult(INCONCLUSIVE, "step sizes, errors and standard errors must all be positive",
                           acceptance=accept, **base)
    if np.unique(h).size < 3:
        return OrderResult(INCONCLUSIVE, "fewer than three distinct step sizes: a slope and its uncertainty cannot"
                                         " both be estimated", acceptance=accept, **base)
    if not 0.5 < level < 1:
        raise ValueError(f"level must be between 0.5 and 1, not {level}")
    x, y, w = np.log(h), np.log(e), (e / s) ** 2  # weight 1 / var(log e)
    xm = float((w * x).sum() / w.sum())
    sxx = float((w * (x - xm) ** 2).sum())
    p = float((w * (x - xm) * (y - (w * y).sum() / w.sum())).sum() / sxx)
    resid = y - ((w * y).sum() / w.sum() + p * (x - xm))
    chi2_dof = float((w * resid**2).sum() / (x.size - 2))
    se = float(np.sqrt(max(1.0, chi2_dof) / sxx))
    z = _normal_quantile(0.5 + level / 2)
    lo, hi = p - z * se, p + z * se
    a, b = expected - tol_low, expected + tol_high
    scatter = f"; the scatter about the line is {np.sqrt(chi2_dof):.2g} times the error bars" if chi2_dof > 1 else ""
    msg = f"fitted order {p:.3g} +- {se:.2g}, {level:.0%} interval [{lo:.3g}, {hi:.3g}] (expected {expected:g}, band {band}){scatter}"
    if a <= lo and hi <= b:
        status = PASS
    elif hi < a or lo > b:
        status = FAIL
    else:
        status = INCONCLUSIVE
        msg += "; the interval overlaps the edge of the band, so more samples or more step sizes are needed"
    return OrderResult(status, msg, fitted=p, fitted_se=se, acceptance=accept, **base)
