"""Order of a Runge-Kutta method from its Butcher table, by the order conditions.

A Runge-Kutta method (A, b, c) has order p exactly when b . Phi(t) = 1 / gamma(t) for every rooted
tree t with at most p vertices (Butcher). This is algebra on the coefficients: it needs no test
problem, cannot be fooled by a lucky cancellation or a superconvergent test equation, and works the
same for explicit and implicit methods.

Lessons from testing other people's code: one package's `order` labels were wrong for 3 of its
tables (one claimed 4 where the table satisfies only the order-3 conditions), and another's embedded
weights for Tsitouras 5(4) did not even sum to 1. Order studies on test equations found both, but
were slower to adjudicate than this check.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from .checks import FAIL, PASS, Result


@lru_cache(maxsize=None)
def trees(order: int) -> tuple:
    """All rooted trees with `order` vertices, each a sorted tuple of child subtrees."""
    if order == 1:
        return ((),)
    out = set()

    def forests(n, max_child):
        # multisets of trees with n vertices in total, children in non-increasing canonical order
        if n == 0:
            yield ()
            return
        for k in range(n, 0, -1):
            for t in trees(k):
                if max_child is not None and (k, t) > max_child:
                    continue
                for rest in forests(n - k, (k, t)):
                    yield ((k, t),) + rest

    for forest in forests(order - 1, None):
        out.add(tuple(sorted((t for _, t in forest), key=repr)))
    return tuple(sorted(out, key=repr))


def _size(t) -> int:
    return 1 + sum(_size(s) for s in t)


def _gamma(t) -> int:
    g = _size(t)
    for s in t:
        g *= _gamma(s)
    return g


def _phi(t, A, e):
    v = e.copy()
    for s in t:
        v = v * (A @ _phi(s, A, e))
    return v


def order_residuals(A, b, max_order: int = 6) -> dict:
    """{order: largest |b . Phi(t) - 1/gamma(t)| over the trees of that order}."""
    A = np.asarray(A, dtype=float)
    b = np.asarray(b, dtype=float)
    e = np.ones(len(b))
    return {p: max(abs(float(b @ _phi(t, A, e)) - 1.0 / _gamma(t)) for t in trees(p)) for p in range(1, max_order + 1)}


def tableau_order(A, b, *, max_order: int = 6, tol: float = 1e-8) -> int:
    """Highest p <= max_order such that every condition up to order p holds within tol."""
    p = 0
    for q, r in order_residuals(A, b, max_order).items():
        if r > tol:
            break
        p = q
    return p


def linear_residuals(A, b, max_order: int = 8) -> dict:
    """{k: |b . A^(k-1) 1 - 1/k!|}: how far the stability function R(z) is from e^z at each power of z."""
    A = np.asarray(A, dtype=float)
    v = np.ones(len(b))
    b = np.asarray(b, dtype=float)
    out, fact = {}, 1.0
    for k in range(1, max_order + 1):
        fact *= k
        out[k] = abs(float(b @ v) - 1.0 / fact)
        v = A @ v
    return out


def linear_order(A, b, *, max_order: int = 8, tol: float = 1e-8) -> int:
    """Order on linear constant-coefficient problems (y' = λy): highest p with R(z) = e^z + O(z^(p+1)).

    It is at least the classical order and can be higher; a convergence test on y' = λy measures this
    number, not the classical one (Hairer & Wanner, Solving ODEs II, section IV.3).
    """
    p = 0
    for q, r in linear_residuals(A, b, max_order).items():
        if r > tol:
            break
        p = q
    return p


def stage_order(A, c=None, b=None, *, max_order: int = 8, tol: float = 1e-8) -> int:
    """Highest q with A c^(k-1) = c^k / k for k = 1..q (simplifying assumption C(q)).

    With `b` given, b . c^(k-1) = 1/k (assumption B(q)) is required as well, the usual definition of
    stage order. A low stage order is what causes order reduction on stiff problems.
    """
    A = np.asarray(A, dtype=float)
    c = A.sum(axis=1) if c is None else np.asarray(c, dtype=float)
    q = 0
    for k in range(1, max_order + 1):
        r = float(np.max(np.abs(A @ c ** (k - 1) - c**k / k)))
        if b is not None:
            r = max(r, abs(float(np.asarray(b, float) @ c ** (k - 1)) - 1.0 / k))
        if r > tol:
            break
        q = k
    return q


def stability_polynomials(A, b):
    """(P, Q) coefficient arrays, lowest power first, with R(z) = P(z) / Q(z).

    P(z) = det(I - zA + z 1 b^T) and Q(z) = det(I - zA) have degree at most s; they are recovered
    from their values on the unit circle, which is well conditioned.
    """
    A = np.asarray(A, dtype=float)
    b = np.asarray(b, dtype=float)
    s = len(b)
    n = s + 1
    z = np.exp(2j * np.pi * np.arange(n) / n)
    eb = np.outer(np.ones(s), b)
    I = np.eye(s)
    Pv = np.array([np.linalg.det(I - zz * A + zz * eb) for zz in z])
    Qv = np.array([np.linalg.det(I - zz * A) for zz in z])
    P = np.real(np.fft.fft(Pv) / n)
    Q = np.real(np.fft.fft(Qv) / n)
    return P, Q


def _trim(p, tol=1e-12):
    p = np.array(p, dtype=float)
    p[np.abs(p) < tol] = 0.0
    nz = np.nonzero(p)[0]
    return p[: nz[-1] + 1] if len(nz) else np.zeros(1)


def stability_function(A, b):
    """R(z) = 1 + z b^T (I - zA)^(-1) 1, as a function of a complex z."""
    A = np.asarray(A, dtype=float)
    b = np.asarray(b, dtype=float)
    e = np.ones(len(b))
    return lambda z: 1 + z * (b @ np.linalg.solve(np.eye(len(b)) - z * A, e))


def r_infinity(A, b) -> float:
    """lim R(z) as |z| -> infinity: 0 for an L-stable method, inf when R is a polynomial (explicit)."""
    P, Q = (_trim(x) for x in stability_polynomials(A, b))
    if len(P) > len(Q):
        return float("inf")
    if len(P) < len(Q):
        return 0.0
    return float(P[-1] / Q[-1])


def a_stability_margin(A, b) -> float:
    """min over real y of |Q(iy)|^2 - |P(iy)|^2, scaled by the largest coefficient; >= 0 on the imaginary axis
    means |R(iy)| <= 1. Returns -inf when R has a pole in the closed left half-plane or grows at infinity.

    A method is A-stable exactly when the margin is >= 0 (up to round-off) and every pole of R lies in
    Re z > 0 (Hairer & Wanner II, section IV.3, the E-polynomial).
    """
    P, Q = (_trim(x) for x in stability_polynomials(A, b))
    if len(P) > len(Q):
        return float("-inf")
    if len(Q) > 1 and np.any(np.roots(Q[::-1]).real <= 1e-12):
        return float("-inf")
    iy = np.polynomial.Polynomial([0, 1j])
    Pi = np.polynomial.Polynomial(P.astype(complex))(iy)
    Qi = np.polynomial.Polynomial(Q.astype(complex))(iy)

    def sq(p):  # |p(iy)|^2 for real y, as a polynomial in y
        return p * np.polynomial.Polynomial(np.conj(p.coef))

    E = np.polynomial.Polynomial(np.real((sq(Qi) - sq(Pi)).coef))
    scale = max(1.0, float(np.max(np.abs(E.coef))))
    pts = [0.0, 1.0, -1.0]
    if E.degree() >= 2:
        pts += [float(r.real) for r in E.deriv().roots() if abs(r.imag) < 1e-7 * max(1.0, abs(r))]
    lead = E.coef[-1] if E.degree() >= 1 else 0.0
    if E.degree() >= 1 and lead < -1e-12 * scale:
        return float("-inf")
    return float(min(E(y) for y in pts)) / scale


def is_stiffly_accurate(A, b, *, tol: float = 1e-12) -> bool:
    """b equals the last row of A, so the step result is the last stage (Hairer & Wanner II, IV.6)."""
    return bool(np.max(np.abs(np.asarray(A, float)[-1] - np.asarray(b, float))) <= tol)


def square_tableau(A, b, c=None):
    """(A, b, c) with A made square: a table stored as s x (s - 1) (the last column of an explicit table is
    zero and is often left out) or with an extra FSAL stage that has weight 0 in b is padded with zeros.
    Explicit FSAL tables (Dormand-Prince, Bogacki-Shampine) then check like any other."""
    A = np.atleast_2d(np.asarray(A, dtype=float))
    b = np.asarray(b, dtype=float)
    n = max(A.shape[0], A.shape[1], b.size)
    full = np.zeros((n, n))
    full[:A.shape[0], :A.shape[1]] = A
    bb = np.zeros(n)
    bb[:b.size] = b
    if c is not None:
        cc = np.zeros(n)
        cc[:np.size(c)] = np.asarray(c, dtype=float)
        if np.size(c) < n:
            cc[np.size(c):] = full[np.size(c):].sum(axis=1)
        c = cc
    return full, bb, c


def symplectic_residual(A, b) -> float:
    """max |b_i a_ij + b_j a_ji - b_i b_j|: zero exactly for a symplectic Runge-Kutta method (Sanz-Serna 1988;
    Hairer, Lubich and Wanner, Geometric Numerical Integration, Thm. VI.4.3). Gauss methods are symplectic;
    no explicit Runge-Kutta method is."""
    A, b, _ = square_tableau(A, b)
    M = b[:, None] * A + (b[:, None] * A).T - np.outer(b, b)
    return float(np.max(np.abs(M)))


def check_tableau(A, b, c=None, *, claimed: int, label: str = "", tol: float = 1e-8, max_order: int | None = None,
                  claimed_linear: int | None = None, claimed_stage: int | None = None, a_stable: bool | None = None,
                  l_stable: bool | None = None, stiffly_accurate: bool | None = None, embedded=None,
                  claimed_embedded: int | None = None, symplectic: bool | None = None) -> Result:
    """PASS when the table has at least the claimed order and every other stated property; FAIL otherwise.

    The default tolerance 1e-8 accepts coefficients typed with 9 or 10 digits (a real package had
    residuals of 2e-10 for that reason), while a missing order shows residuals of 1e-4 or more.
    The message gives the residuals, so a table whose conditions hold only to about 1e-10 is visible, and a claim that is lower than the true
    order is noted rather than failed. If `c` is given, the row sums of A must equal it (the order
    conditions assume they do, so a mismatch fails).

    Optional claims, each checked only when given:
    claimed_linear  order on y' = λy (the order a Dahlquist convergence test measures); see `linear_order`
    claimed_stage   stage order, C(q) and B(q); see `stage_order`
    a_stable        |R(z)| <= 1 on Re z <= 0; see `a_stability_margin`
    l_stable        A-stable and R(inf) = 0
    stiffly_accurate  b equals the last row of A
    symplectic      b_i a_ij + b_j a_ji = b_i b_j; see `symplectic_residual`
    True means "the method has it" and False means "the method does not"; a mismatch either way fails.
    embedded        the weights of the embedded (error-estimate) method; with `claimed_embedded`, its order
                    is checked too, and the error weights b - embedded must sum to 0.
    A table stored as s x (s - 1), or with an FSAL stage of weight 0, is padded first (`square_tableau`).
    """
    A, b, c = square_tableau(A, b, c)
    top = max_order or claimed + 1
    res = order_residuals(A, b, top)
    p = tableau_order(A, b, max_order=top, tol=tol)
    shown = ", ".join(f"{q}: {r:.1e}" for q, r in res.items())
    prefix = f"{label}: " if label else ""
    notes, fails = [], []
    if c is not None:
        rs = float(np.max(np.abs(np.asarray(A, float).sum(axis=1) - np.asarray(c, float))))
        if rs > tol:
            fails.append(f"row sums of A differ from c by {rs:.1e}")
    worst_kept = max((r for q, r in res.items() if q <= max(p, 1)), default=0.0)
    if p >= 1 and worst_kept > 1e-13:
        notes.append(f"conditions hold only to {worst_kept:.0e} (coefficients with limited digits?)")
    if p < claimed:
        missing = max(r for q, r in res.items() if p < q <= claimed)
        msg = f"claims order {claimed} but satisfies the order conditions only up to {p} (largest residual per order: {shown})"
        if missing < 1e-5:
            msg += (f"; the conditions for order {claimed} hold to {missing:.1e}, which looks like coefficients typed"
                    f" with too few digits rather than a wrong method: retry with tol={10 * missing:.0e} and compare"
                    " with the published table")
        fails.insert(0, msg)
    elif p > claimed:
        notes.insert(0, f"claims order {claimed}; the conditions hold up to at least {p}, so the claim is conservative ({shown})")
    else:
        notes.insert(0, f"order {claimed} confirmed by the order conditions ({shown})")

    if claimed_linear is not None:
        pl = linear_order(A, b, max_order=max(claimed_linear + 1, 2), tol=tol)
        if pl < claimed_linear:
            fails.append(f"claims linear order {claimed_linear} but R(z) matches e^z only up to z^{pl}")
        elif pl > claimed_linear:
            notes.append(f"linear order is at least {pl} (claimed {claimed_linear})")
        else:
            notes.append(f"linear order {pl} confirmed")
    elif (pl := linear_order(A, b, max_order=max(p, claimed) + 2, tol=tol)) > p:
        notes.append(f"linear order {pl} is higher than the order {p}:"
                     " a convergence test on y' = lambda*y alone would overstate the order")
    if claimed_stage is not None:
        q = stage_order(A, c, b, max_order=claimed_stage + 1, tol=tol)
        if q < claimed_stage:
            fails.append(f"claims stage order {claimed_stage} but C(q) and B(q) hold only up to q = {q}")
        else:
            notes.append(f"stage order {q}" + (f" (claimed {claimed_stage})" if q > claimed_stage else " confirmed"))
    want_a = a_stable if a_stable is not None else (True if l_stable else None)
    if want_a is not None:
        m = a_stability_margin(A, b)
        has = m >= -1e-10
        if has != want_a:
            fails.append(f"stated {'' if want_a else 'not '}A-stable but it is {'' if has else 'not '}"
                         f"(min |Q(iy)|^2 - |P(iy)|^2 = {m:.1e})")
        else:
            notes.append(f"{'' if has else 'not '}A-stable as stated")
    if l_stable is not None:
        ri = r_infinity(A, b)
        has = abs(ri) < 1e-8 and a_stability_margin(A, b) >= -1e-10
        if has != l_stable:
            fails.append(f"stated {'' if l_stable else 'not '}L-stable but it is {'' if has else 'not '}(R(inf) = {ri:.1e})")
        else:
            notes.append(f"{'' if has else 'not '}L-stable as stated")
    if stiffly_accurate is not None:
        has = is_stiffly_accurate(A, b, tol=tol)
        if has != stiffly_accurate:
            fails.append(f"stated {'' if stiffly_accurate else 'not '}stiffly accurate, but b "
                         f"{'equals' if has else 'differs from'} the last row of A")
        else:
            notes.append(f"{'' if has else 'not '}stiffly accurate as stated")

    if embedded is not None:
        Ae = A
        if np.size(embedded) > A.shape[0]:
            # error weights over one more stage (SciPy's E): the FSAL stage, evaluated at y_{n+1}, has row b
            Ae = np.vstack([np.hstack([A, np.zeros((A.shape[0], 1))]), np.append(b, 0.0)])
        Ae, be, _ = square_tableau(Ae, embedded)
        if abs(be.sum() - 1) > tol:
            fails.append(f"embedded weights sum to {be.sum():.10g}, not 1 (so b - embedded does not sum to 0)")
        if claimed_embedded is not None:
            pe = tableau_order(Ae, be, max_order=claimed_embedded + 1, tol=tol)
            if pe < claimed_embedded:
                fails.append(f"claims embedded order {claimed_embedded} but the embedded weights satisfy the order"
                             f" conditions only up to {pe}")
            else:
                notes.append(f"embedded order {pe}" + (f" (claimed {claimed_embedded})" if pe > claimed_embedded else " confirmed"))
    if symplectic is not None:
        r = symplectic_residual(A, b)
        has = r <= tol
        if has != symplectic:
            fails.append(f"stated {'' if symplectic else 'not '}symplectic, but max |b_i a_ij + b_j a_ji - b_i b_j| = {r:.1e}")
        else:
            notes.append(f"{'' if has else 'not '}symplectic as stated")

    if fails:
        return Result(FAIL, prefix + "; ".join(fails + notes))
    return Result(PASS, prefix + "; ".join(notes))


# Published tables, for comparing a code's copy against them (exact rationals as floats).
_S3 = np.sqrt(3.0)
TABLES = {
    "rk4": dict(A=[[0, 0, 0, 0], [0.5, 0, 0, 0], [0, 0.5, 0, 0], [0, 0, 1, 0]], b=[1 / 6, 1 / 3, 1 / 3, 1 / 6],
                c=[0, 0.5, 0.5, 1], order=4),
    # Bogacki and Shampine 1989; SciPy's RK23 (embedded order 2, FSAL)
    "bogacki_shampine_3_2": dict(A=[[0, 0, 0, 0], [1 / 2, 0, 0, 0], [0, 3 / 4, 0, 0], [2 / 9, 1 / 3, 4 / 9, 0]],
                                 b=[2 / 9, 1 / 3, 4 / 9, 0], c=[0, 1 / 2, 3 / 4, 1], order=3,
                                 embedded=[7 / 24, 1 / 4, 1 / 3, 1 / 8], embedded_order=2),
    # Dormand and Prince 1980; SciPy's RK45 and MATLAB's ode45 (embedded order 4, FSAL)
    "dormand_prince_5_4": dict(
        A=[[0, 0, 0, 0, 0, 0, 0],
           [1 / 5, 0, 0, 0, 0, 0, 0],
           [3 / 40, 9 / 40, 0, 0, 0, 0, 0],
           [44 / 45, -56 / 15, 32 / 9, 0, 0, 0, 0],
           [19372 / 6561, -25360 / 2187, 64448 / 6561, -212 / 729, 0, 0, 0],
           [9017 / 3168, -355 / 33, 46732 / 5247, 49 / 176, -5103 / 18656, 0, 0],
           [35 / 384, 0, 500 / 1113, 125 / 192, -2187 / 6784, 11 / 84, 0]],
        b=[35 / 384, 0, 500 / 1113, 125 / 192, -2187 / 6784, 11 / 84, 0], c=[0, 1 / 5, 3 / 10, 4 / 5, 8 / 9, 1, 1],
        order=5, embedded=[5179 / 57600, 0, 7571 / 16695, 393 / 640, -92097 / 339200, 187 / 2100, 1 / 40],
        embedded_order=4),
    "implicit_midpoint": dict(A=[[0.5]], b=[1.0], c=[0.5], order=2),
    "gauss_legendre_4": dict(A=[[1 / 4, 1 / 4 - _S3 / 6], [1 / 4 + _S3 / 6, 1 / 4]], b=[0.5, 0.5],
                             c=[0.5 - _S3 / 6, 0.5 + _S3 / 6], order=4),
}


def _drop_fsal(A, b, tol: float = 1e-14):
    """Without a last FSAL stage (row equal to b, weight 0 in b): codes store such tables with or without it."""
    if A.shape[0] > 1 and abs(b[-1]) <= tol and np.allclose(A[-1, :-1], b[:-1], atol=tol, rtol=0):
        return A[:-1, :-1], b[:-1]
    return A, b


def compare_tableau(A, b, name: str, *, tol: float = 1e-10) -> Result:
    """A code's copy of a published table (one of `TABLES`) has the published coefficients."""
    ref = TABLES[name]
    A1, b1 = _drop_fsal(*square_tableau(A, b)[:2])
    A2, b2 = _drop_fsal(*square_tableau(ref["A"], ref["b"])[:2])
    if A1.shape != A2.shape:
        return Result(FAIL, f"{name}: {A1.shape[0]} stages, the published table has {A2.shape[0]}")
    dA, db = np.abs(A1 - A2), np.abs(b1 - b2)
    if max(dA.max(), db.max()) <= tol:
        return Result(PASS, f"{name}: coefficients match the published table to {tol:g}")
    i, j = np.unravel_index(int(np.argmax(dA)), dA.shape)
    where = f"A[{i}][{j}] off by {dA[i, j]:.3g}" if dA.max() >= db.max() else f"b[{int(np.argmax(db))}] off by {db.max():.3g}"
    return Result(FAIL, f"{name}: coefficients differ from the published table, largest at {where}")
