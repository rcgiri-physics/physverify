"""Checks that need no exact solution: round trips, derivatives, sibling agreement and identities.

These are the checks that found most of the bugs in the batch-8 corpus study (popular libraries):
two functions that should agree but do not (an air-absorption term with the opposite sign in one
of two reverberation formulas), an operation that should be undone by its inverse but is not
(a zero-time rotation that shifts an image by half a pixel), an analytic derivative compared with
finite differences, and textbook identities (Poisson's equation, unitarity, conservation).

Each function returns a `Result` (PASS or FAIL with the worst case in the message); wrap it in a
`Check("limit", label, lambda: ...)` to run it with the others. Values may be real or complex scalars
or arrays. The reference side must come from the physics, not from the code under test: a round trip
or a sibling comparison can pass when both sides share the same mistake.
"""

from __future__ import annotations

from typing import Callable, Iterable

import numpy as np

from .checks import FAIL, PASS, Result


def _worst(got, ref, rtol: float, atol: float):
    """Largest violation of |got - ref| <= atol + rtol |ref|, as (excess, abs error, where, got there, ref there).

    `where` indexes the broadcast shape, so the values there are returned too: indexing the original
    `got` with it fails when a scalar was compared with an array.
    """
    g = np.asarray(got)
    r = np.asarray(ref)
    if g.shape != r.shape:
        try:
            g, r = np.broadcast_arrays(g, r)
        except ValueError:
            raise ValueError(f"shapes differ: got {np.shape(got)}, reference {np.shape(ref)}") from None
    err = np.abs(g - r)
    tol = atol + rtol * np.abs(r)
    excess = err - tol
    if excess.size == 0:
        return -np.inf, 0.0, (), got, ref
    if not np.all(np.isfinite(err)):
        i = np.unravel_index(int(np.argmax(~np.isfinite(err))), err.shape)
        return np.inf, np.inf, i, (g[i] if i else got), (r[i] if i else ref)
    i = np.unravel_index(int(np.argmax(excess)), excess.shape)
    return float(excess[i]), float(err[i]), i, (g[i] if i else got), (r[i] if i else ref)


def _verdict(what: str, cases, rtol: float, atol: float) -> Result:
    """cases: iterable of (label, got, ref). PASS when every case is within tolerance."""
    worst = None
    n = 0
    for label, got, ref in cases:
        n += 1
        excess, err, where, g, r = _worst(got, ref, rtol, atol)
        if worst is None or excess > worst[0]:
            worst = (excess, err, label, where, g, r)
    if worst is None:
        raise ValueError(f"{what}: no inputs given")
    excess, err, label, where, g, r = worst
    at = f" at index {tuple(int(k) for k in where)}" if where else ""
    detail = f"worst case {label}{at}: |difference| = {err:.3g} (rtol {rtol:g}, atol {atol:g})"
    if excess <= 0:
        return Result(PASS, f"{what}: {n} case{'s' if n != 1 else ''} within tolerance; {detail}")
    return Result(FAIL, f"{what}: {detail}; got {g!r}, expected {r!r}")


def check_roundtrip(forward: Callable, inverse: Callable, inputs: Iterable, *, rtol: float = 1e-9, atol: float = 0.0) -> Result:
    """inverse(forward(x)) == x for every x in `inputs`.

    Catches conversions that disagree with their own inverse: a reference pixel off by half a pixel,
    a dewpoint formula that does not invert the saturation formula, a unit conversion with the wrong
    constant on one side. Both functions come from the code under test, so a PASS says only that
    they are consistent, not that either is right.
    """
    cases = []
    for x in inputs:
        cases.append((repr(x) if np.ndim(x) == 0 else f"input of shape {np.shape(x)}", inverse(forward(x)), x))
    return _verdict("round trip inverse(forward(x)) = x", cases, rtol, atol)


def check_agree(a: Callable, b: Callable, inputs: Iterable, *, rtol: float = 1e-9, atol: float = 0.0,
                names: tuple[str, str] = ("a", "b")) -> Result:
    """Two implementations that must give the same answer do: a(*x) == b(*x) for each x in `inputs`.

    Use it for sibling code paths (a 2D and a 3D version, a fast path and a slow path, the `min` and
    `max` variants, two formulas that coincide in a limit). Each element of `inputs` is a tuple of
    arguments, or a single argument.
    """
    cases = []
    for x in inputs:
        args = x if isinstance(x, tuple) else (x,)
        cases.append((repr(x), a(*args), b(*args)))
    return _verdict(f"{names[0]} agrees with {names[1]}", cases, rtol, atol)


def fd_derivative(f: Callable, x, *, h: float | None = None, order: int = 1):
    """Central finite-difference derivative of f at x (scalar x), with one Richardson step.

    `order` is 1 or 2 (first or second derivative). The default step is cbrt(machine epsilon) times
    max(1, |x|) for the first derivative and its square root for the second; the Richardson step
    combines h and h/2 to cancel the leading error term.
    """
    x = float(x)
    if order == 1:
        h = h or np.cbrt(np.finfo(float).eps) * max(1.0, abs(x))
        d = lambda s: (np.asarray(f(x + s)) - np.asarray(f(x - s))) / (2 * s)  # noqa: E731
    elif order == 2:
        h = h or np.finfo(float).eps ** 0.25 * max(1.0, abs(x))
        d = lambda s: (np.asarray(f(x + s)) - 2 * np.asarray(f(x)) + np.asarray(f(x - s))) / (s * s)  # noqa: E731
    else:
        raise ValueError("order must be 1 or 2")
    return (4 * d(h / 2) - d(h)) / 3


def check_derivative(f: Callable, df: Callable, points: Iterable, *, order: int = 1, h: float | None = None,
                     rtol: float = 1e-6, atol: float = 1e-10) -> Result:
    """An analytic derivative `df` agrees with a finite-difference derivative of `f` at each point.

    This is how a thermodynamic-consistency claim is settled cheaply: a reader's derivation said an
    activity-coefficient derivative dropped a term, and comparing it with finite differences of the
    activity coefficients themselves showed agreement to 1e-10, so the claim was wrong. The default
    tolerance allows for the finite-difference error; tighten it only with a well-scaled `h`.
    """
    cases = [(f"x = {p!r}", df(p), fd_derivative(f, p, h=h, order=order)) for p in points]
    return _verdict(f"{'first' if order == 1 else 'second'} derivative agrees with finite differences", cases, rtol, atol)


def check_identity(cases: Iterable, *, rtol: float = 1e-9, atol: float = 0.0, what: str = "identity") -> Result:
    """Each (label, lhs, rhs) in `cases` satisfies lhs == rhs.

    For identities written from the physics: Poisson's equation (Laplacian of the potential equals
    4 pi G rho), unitarity of a lossless scattering matrix (S^H S = I), E^2 = p^2 + m^2, a limit that
    must reproduce a simpler formula. Compute the right-hand side yourself, not with the code under test.
    """
    return _verdict(what, list(cases), rtol, atol)


def laplacian_fd(f: Callable, point, *, h: float = 1e-3):
    """Cartesian Laplacian of a scalar field f(x) (x a 1D array) by second-order central differences."""
    x = np.asarray(point, dtype=float)
    f0 = f(x)
    total = 0.0
    for k in range(x.size):
        e = np.zeros_like(x)
        e[k] = h
        total = total + (f(x + e) - 2 * f0 + f(x - e)) / (h * h)
    return total


def check_unitary(matrix, *, atol: float = 1e-10) -> Result:
    """A matrix (or a stack of matrices, last two axes) is unitary: M^H M = I.

    A lossless network's scattering matrix, a time-evolution operator, a rotation.
    """
    m = np.asarray(matrix)
    eye = np.eye(m.shape[-1])
    prod = np.einsum("...ji,...jk->...ik", m.conj(), m)
    return _verdict("unitarity M^H M = I", [("matrix", prod, np.broadcast_to(eye, prod.shape))], 0.0, atol)


def _passes(outcome, rtol: float, atol: float) -> tuple[bool, str]:
    """A test outcome as (passed, detail): a Result, a bool, or a (got, ref) pair compared within tolerance."""
    if isinstance(outcome, Result):
        return outcome.ok, outcome.message
    if isinstance(outcome, tuple) and len(outcome) == 2:
        excess, err, _where, _g, _r = _worst(outcome[0], outcome[1], rtol, atol)
        return excess <= 0, f"|difference| = {err:.3g}"
    return bool(outcome), ""


def vary_one(test: Callable, defaults: dict, changes: dict, *, rtol: float = 1e-9, atol: float = 0.0) -> Result:
    """Re-run a test that passes at the default parameters with one parameter changed at a time.

    `test(**params)` returns a Result, a bool, or a (got, ref) pair with the reference from the physics.
    `defaults` are the usual values (often symmetric ones: Lx = Ly, nx = ny, zero boundary data, s polarisation,
    vacuum); `changes` maps a parameter to a value, or a list of values, to try instead while the others keep
    their defaults. FAIL names each change that breaks the test.

    In the 2026-10 corpus sessions 7 of the confirmed bugs passed every check at the example values and
    appeared only when one parameter left them: a y-derivative scaled with Lx (only when Lx != Ly), a
    Neumann row that dropped the boundary value (only when g != 0), the p-polarisation path of a grating
    solver, an inertia formula right for rectangles only, a factor that cancels for low-loss media.
    """
    ok, detail = _passes(test(**defaults), rtol, atol)
    if not ok:
        return Result(FAIL, f"fails already at the defaults {defaults}" + (f": {detail}" if detail else ""))
    broken, tried = [], 0
    for name, values in changes.items():
        if name not in defaults:
            raise ValueError(f"{name} is not one of the default parameters")
        for v in values if isinstance(values, (list, tuple)) else [values]:
            tried += 1
            try:
                ok, detail = _passes(test(**{**defaults, name: v}), rtol, atol)
            except Exception as exc:  # noqa: BLE001 - an exception fails that change, not the helper
                ok, detail = False, f"{type(exc).__name__}: {exc}"
            if not ok:
                broken.append(f"{name} = {v!r}" + (f" ({detail})" if detail else ""))
    if broken:
        return Result(FAIL, f"passes at the defaults but fails when one parameter changes: {'; '.join(broken)}")
    return Result(PASS, f"passes at the defaults and with each of {tried} one-parameter changes ({', '.join(changes)})")


_FACTORS = {"2": 2.0, "1/2": 0.5, "pi": np.pi, "1/pi": 1 / np.pi, "2 pi": 2 * np.pi, "1/(2 pi)": 1 / (2 * np.pi),
            "sqrt(2)": np.sqrt(2), "1/sqrt(2)": 1 / np.sqrt(2), "4 pi": 4 * np.pi, "1/(4 pi)": 1 / (4 * np.pi),
            "-1": -1.0, "4": 4.0, "1/4": 0.25, "3": 3.0, "1/3": 1 / 3}


def check_scale(got, ref, *, rtol: float = 1e-6, min_correlation: float = 0.999) -> Result:
    """The output has the right size, not only the right shape: got = k * ref with k = 1.

    Fits the single factor k (least squares) and the correlation of got with ref. A correlation near 1
    with k != 1 is a scale or units error (a missing 1/(2 dx), a missing time step, a factor 1/2); the
    message names a nearby simple factor (2, pi, sqrt 2, ...) or gives k to match against a grid spacing
    or a sampling rate. In the 2026-10 corpus sessions the ratio alone pointed to the bug in four
    repositories. A low correlation means the shape itself is wrong, and a plain comparison says more.
    """
    g = np.ravel(np.asarray(got, dtype=complex))
    r = np.ravel(np.asarray(ref, dtype=complex))
    if g.shape != r.shape:
        raise ValueError(f"shapes differ: got {np.shape(got)}, reference {np.shape(ref)}")
    rr = np.vdot(r, r).real
    if rr == 0:
        raise ValueError("the reference is zero everywhere, so no scale can be fitted")
    k = np.vdot(r, g) / rr
    gg = np.vdot(g, g).real
    corr = abs(np.vdot(r, g)) / np.sqrt(rr * gg) if gg > 0 else 0.0
    kshow = f"{k.real:.6g}" if abs(k.imag) <= 1e-12 * abs(k) else f"{k:.6g}"
    if corr < min_correlation:
        return Result(FAIL, f"output and reference differ in shape, not only in scale (correlation {corr:.4f},"
                            f" best factor {kshow}); compare them directly")
    if abs(k - 1) <= rtol:
        return Result(PASS, f"output = {kshow} x reference (correlation {corr:.6f})")
    near = [n for n, v in _FACTORS.items() if abs(k - v) <= 1e-3 * abs(v)]
    hint = f", which is {near[0]}" if near else ""
    return Result(FAIL, f"output = {kshow} x reference{hint} (correlation {corr:.6f}): the shape is right but the scale"
                        " is not; look for a missing factor (grid spacing, time step, sampling rate, 2, pi) or a units slip")


def check_vec_convention(superop, f: Callable, x, *, expected: str | None = None, atol: float = 1e-10) -> Result:
    """Which vectorisation a superoperator follows: superop @ vec(X) == vec(f(X)), with vec in C (row-major)
    or F (column-major) order.

    Kronecker constructions of Liouvillians and other superoperators depend on the convention
    (vec(A X B) = (B^T kron A) vec(X) holds for column stacking); code that builds S for one and reshapes
    with the other gives a wrong but well-formed answer (corpus repo L204). With `expected` ('C' or 'F'),
    FAIL unless S follows it; without, PASS when S follows either, and say which.
    """
    S = np.asarray(superop)
    X = np.asarray(x)
    want = np.asarray(f(X))
    match = [o for o in ("C", "F") if np.allclose(S @ X.ravel(order=o), want.ravel(order=o), atol=atol, rtol=0)]
    if not match:
        return Result(FAIL, "the superoperator matches f(X) in neither C (row-major) nor F (column-major) vectorisation")
    which = " and ".join(match)
    if expected is not None and expected.upper() not in match:
        return Result(FAIL, f"the superoperator follows {which}-order vectorisation, not the expected {expected.upper()}")
    return Result(PASS, f"the superoperator follows {which}-order vectorisation (row-major is C, column-major is F)")
