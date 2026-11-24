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

from functools import cache

import numpy as np

from .checks import FAIL, PASS, Result


def _nonfinite(prefix: str, **arrays) -> Result | None:
    """FAIL naming the inputs that hold NaN or inf, else None. A NaN coefficient makes every comparison with
    tol False, so without this check a NaN residual could pass as a satisfied condition (review of 0.9.0)."""
    bad = []
    for name, x in arrays.items():
        if x is None or callable(x):
            continue
        try:
            arr = np.asarray(x, dtype=float)
        except (TypeError, ValueError):
            continue  # ragged input is left to the shape checks
        if not np.all(np.isfinite(arr)):
            bad.append(name)
    if bad:
        return Result(FAIL, prefix + f"non-finite coefficients (NaN or inf) in {', '.join(bad)}: invalid input,"
                                     " no order conditions were checked")
    return None


def _residuals_finite(prefix: str, values) -> Result | None:
    vals = np.asarray(list(values), dtype=float)
    if not np.all(np.isfinite(vals)):
        return Result(FAIL, prefix + "a residual of the order conditions is NaN or inf, so the conditions cannot be"
                                     " said to hold: check the coefficients for NaN or overflow")
    return None


@cache
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


def _max_children(t) -> int:
    return max([len(t)] + [_max_children(u) for u in t])


def quadratic_order(A, b, *, max_order: int = 6, tol: float = 1e-8) -> int:
    """Order on ODEs whose right side is at most quadratic in y (third derivative of f zero): only the trees
    in which every vertex has at most 2 children carry a nonzero elementary differential, so only their
    conditions count. SIR54 (Kovalnogov, Simos and Tsitouras 2021) is order 5 for quadratic ODEs only."""
    A = np.asarray(A, float)
    b = np.asarray(b, float)
    e = np.ones(len(b))
    p = 0
    for q in range(1, max_order + 1):
        ts = [t for t in trees(q) if _max_children(t) <= 2]
        if max(abs(float(b @ _phi(t, A, e)) - 1.0 / _gamma(t)) for t in ts) > tol:
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
        pts += [float(r.real) for r in E.deriv().roots() if abs(r.imag) < 1e-7 * max(1.0, float(abs(r)))]
    lead = E.coef[-1] if E.degree() >= 1 else 0.0
    if E.degree() >= 1 and lead < -1e-12 * scale:
        return float("-inf")
    m = float(min(E(y) for y in pts)) / scale
    if m < 0:
        # Gauss methods have |R(iy)| = 1 exactly, so E is zero and its computed coefficients are round-off,
        # which grows like y^(2s) at the critical points (Irksome GaussLegendre(5) gave -9e-10). Judge the sign
        # by 1 - |R(iy)|^2 evaluated directly from R = 1 + z b^T (I - zA)^-1 1, which is scale-free; round-off
        # there is about 1e-12 for 6 stages, while theta = 1/2 - 1e-9 gives -8e-9.
        R = stability_function(A, b)
        ys = [y for y in pts if np.isfinite(y)] + list(np.logspace(-2, 4, 61)) + list(-np.logspace(-2, 4, 61))
        rel = min(1 - abs(R(1j * y)) ** 2 for y in ys)
        if rel > -1e-10:
            return 0.0
    return m


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
                  claimed_embedded: int | None = None, symplectic: bool | None = None, error_weights=None) -> Result:
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
    error_weights   the weights e of the error estimate itself (local error = h * sum e_i k_i), for a library
                    that stores b - embedded rather than the embedded weights; they must sum to 0, else the
                    "error" is a whole step (probjax heun_euler and bogacki_shampine, 2026). Then checked as
                    embedded = b - e.
    A table stored as s x (s - 1), or with an FSAL stage of weight 0, is padded first (`square_tableau`).
    """
    prefix = f"{label}: " if label else ""
    bad = _nonfinite(prefix, A=A, b=b, c=c, embedded=embedded, error_weights=error_weights)
    if bad:
        return bad
    A, b, c = square_tableau(A, b, c)
    top = max(max_order or claimed + 1, claimed)
    res = order_residuals(A, b, top)
    bad = _residuals_finite(prefix, res.values())
    if bad:
        return bad
    p = tableau_order(A, b, max_order=top, tol=tol)
    shown = ", ".join(f"{q}: {r:.1e}" for q, r in res.items())
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
        pq = quadratic_order(A, b, max_order=claimed, tol=tol)
        if pq > p:
            msg += (f"; on ODEs with f at most quadratic in y (only trees with at most 2 children per vertex) it has"
                    f" order {pq}, so a claim meant for quadratic problems only should say so")
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

    if error_weights is not None:
        ew = np.asarray(error_weights, dtype=float)
        if abs(ew.sum()) > tol:
            fails.append(f"error weights sum to {ew.sum():.10g}, not 0: the error estimate h*sum(e_i k_i) is then"
                         " a whole step (about h*f), not a difference of two formulas; were the embedded weights"
                         " stored in place of b - embedded?")
        elif embedded is not None:
            emb = np.asarray(embedded, dtype=float)
            n = max(b.size, ew.size, emb.size)
            bb, ee, mm = (np.pad(x, (0, n - x.size)) for x in (b, ew, emb))
            d = min(np.max(np.abs(bb - mm - ee)), np.max(np.abs(bb - mm + ee)))
            if d > tol:
                fails.append(f"the error weights are not b - embedded (nor its negative); they differ by {d:.1e}")
        else:
            bb = np.zeros(max(b.size, ew.size))
            bb[:b.size] = b
            ee = np.zeros(bb.size)
            ee[:ew.size] = ew
            embedded = bb - ee
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


# --- dense output (continuous extensions) ---------------------------------------------------------------
# A dense output y(t0 + theta h) = y0 + h sum_i b_i(theta) k_i has uniform order q when, for every tree t with
# at most q vertices and every theta in [0, 1], sum_i b_i(theta) Phi_i(t) = theta^|t| / gamma(t)
# (Hairer, Norsett & Wanner I, sec. II.6, eq. (6.14)). One point value (a "midpoint" y_mid) is the same test
# at a single theta. A dense output of order q gives errors O(h^(q+1)) per step, so between steps the result is
# only as good as min(p, q): the torchdiffeq bosh3 midpoint (order 1) made outputs 4e4 x the tolerance.

# both endpoints: b(0) must reproduce y0 and b(1) the step (an interval from 0.1 missed a wrong b(0); review of 0.9.0)
DEFAULT_THETAS = np.linspace(0.0, 1.0, 11)


def _dense_table(A, n_weights, b=None):
    """A made square, and extended by the FSAL stage (row b) when the weights have one more entry than A has
    stages, as SciPy stores RK45.P. A table stored as s x (s - 1) is padded like `square_tableau`."""
    A = square_tableau(A, np.zeros(1))[0]
    s = A.shape[0]
    if n_weights == s + 1:
        if b is None:
            raise ValueError(f"the dense weights have {n_weights} entries for a {s}-stage table: an FSAL stage;"
                             " pass b= (the step's weights, which are that stage's row of A)")
        A = np.vstack([np.hstack([A, np.zeros((s, 1))]), np.append(np.asarray(b, dtype=float), 0.0)])
    elif n_weights > s:
        raise ValueError(f"the dense weights have {n_weights} entries but the table has {s} stages")
    return A


def dense_residuals(A, b_of_theta, *, max_order: int = 5, thetas=None, b=None) -> dict:
    """{order: largest |b(theta) . Phi(t) - theta^|t|/gamma(t)|} over trees of that order and the thetas.
    `b_of_theta` is a callable theta -> weights, or a fixed weight vector (then `thetas` must hold its one theta).
    Weights with one entry more than A has stages belong to an FSAL stage; pass `b`, the step's weights."""
    if thetas is None:
        if not callable(b_of_theta):
            raise ValueError("a fixed weight vector is the output at one theta: pass thetas=[theta]")
        thetas = DEFAULT_THETAS
    get = b_of_theta if callable(b_of_theta) else (lambda th: b_of_theta)
    sizes = {np.asarray(get(th), dtype=float).size for th in thetas}
    A = _dense_table(A, max(sizes), b)
    n = A.shape[0]
    e = np.ones(n)
    out = {}
    for q in range(1, max_order + 1):
        r = 0.0
        for th in thetas:
            w = np.zeros(n)
            bw = np.asarray(get(th), dtype=float)
            w[:bw.size] = bw
            for t in trees(q):
                d = abs(float(w @ _phi(t, A, e)) - th ** q / _gamma(t))
                r = d if not np.isfinite(d) or not np.isfinite(r) else max(r, d)
        out[q] = r
    return out


def dense_order(A, b_of_theta, *, max_order: int = 5, thetas=None, tol: float = 1e-8, b=None) -> int:
    """Highest q <= max_order whose dense-output conditions hold within tol (0 if not even consistent)."""
    q = 0
    for p, r in dense_residuals(A, b_of_theta, max_order=max_order, thetas=thetas, b=b).items():
        if r > tol:
            break
        q = p
    return q


def check_dense_output(A, b_of_theta, *, claimed: int, label: str = "", thetas=None, tol: float = 1e-8,
                       b=None) -> Result:
    """PASS when the continuous extension (or one point value, with `thetas=[theta]`) has at least the claimed
    order on every theta given; FAIL with the residuals otherwise. A fixed weight vector needs `thetas=[theta]`
    (ValueError otherwise). Weights over an extra FSAL stage (SciPy's P) need `b`, the step's weights."""
    prefix = f"{label}: " if label else ""
    bad = _nonfinite(prefix, A=A, b=b, weights=b_of_theta)
    if bad:
        return bad
    res = dense_residuals(A, b_of_theta, max_order=claimed + 1, thetas=thetas, b=b)
    bad = _residuals_finite(prefix + "dense output: ", res.values())
    if bad:
        return bad
    tested = "theta = " + ", ".join(f"{float(t):g}" for t in (DEFAULT_THETAS if thetas is None else thetas))
    q = max((p for p in range(claimed + 2) if all(res[k] <= tol for k in range(1, p + 1))), default=0)
    shown = ", ".join(f"{p}: {r:.1e}" for p, r in res.items())
    where = "the point value" if thetas is not None and len(thetas) == 1 else "the dense output"
    if q < claimed:
        return Result(FAIL, prefix + f"{where} should have order {claimed} but its conditions hold only up to {q}"
                                     f" (largest residual per order: {shown}; tested at {tested})")
    return Result(PASS, prefix + f"{where} has order {q if q <= claimed else f'at least {q}'} at the sampled points"
                                 f" {tested} (claimed {claimed}; {shown})")


# --- additive (IMEX, ARK) methods -------------------------------------------------------------------
# y' = f1(y) + f2(y) + ..., each part with its own table (A^v, b^v) sharing the stages. The method has order
# p exactly when b^{v(root)} . Phi(t) = 1/gamma(t) for every rooted tree of at most p vertices with every
# colouring of its vertices by the parts; Phi uses A^{v(child root)} on each edge (Kennedy & Carpenter 2003,
# Appl. Numer. Math. 44, sec. 2; Hairer, Norsett & Wanner I, sec. II.15, P-series). Checking each part alone
# (one colour) misses the mixed conditions: a pair can have order 3 per part and order 2 together.

def _colourings(t, n):
    """All colourings of tree t by n colours, as (colour, (coloured children...))."""
    import itertools
    kids = [_colourings(s, n) for s in t]
    return [(v, combo) for v in range(n) for combo in itertools.product(*kids)]


def _phi_col(ct, As, e):
    v = e.copy()
    for s in ct[1]:
        v = v * (As[s[0]] @ _phi_col(s, As, e))
    return v


def additive_order_residuals(As, bs, max_order: int = 4) -> dict:
    """{order: (largest residual over all colourings, largest residual over single-colour trees)}."""
    sq = [square_tableau(A, b) for A, b in zip(As, bs)]
    n = max(A.shape[0] for A, _, _ in sq)
    As_ = [np.pad(A, ((0, n - A.shape[0]), (0, n - A.shape[0]))) for A, _, _ in sq]
    bs_ = [np.pad(b, (0, n - b.size)) for _, b, _ in sq]
    e = np.ones(n)
    out = {}
    for p in range(1, max_order + 1):
        allr = pure = 0.0
        for t in trees(p):
            g = 1.0 / _gamma(t)
            for ct in _colourings(t, len(As_)):
                r = abs(float(bs_[ct[0]] @ _phi_col(ct, As_, e)) - g)
                allr = max(allr, r)
                cols = set()
                stack = [ct]
                while stack:
                    x = stack.pop()
                    cols.add(x[0])
                    stack.extend(x[1])
                if len(cols) == 1:
                    pure = max(pure, r)
        out[p] = (allr, pure)
    return out


def check_additive(As, bs, cs=None, *, claimed: int, label: str = "", tol: float = 1e-8,
                   max_order: int | None = None) -> Result:
    """PASS when the additive (IMEX/ARK) method of the parts (A^v, b^v) has the claimed order as a pair,
    coupling conditions included; FAIL otherwise, saying whether the parts alone or only the coupling fail.

    If `cs` is given, each part's row sums must equal its c, and the parts' c must agree with each other
    (the usual assumption of the coupling conditions; a pair with different nodes needs more conditions
    than are checked here, so it is reported)."""
    prefix = f"{label}: " if label else ""
    if len(As) != len(bs) or (cs is not None and len(cs) != len(As)):
        counts = f"{len(As)} coefficient matrices and {len(bs)} weight vectors"
        if cs is not None:
            counts += f" and {len(cs)} node vectors"
        return Result(FAIL, prefix + f"{counts}: every part needs its own A and b (and c); invalid input, nothing checked")
    if len(As) < 1:
        return Result(FAIL, prefix + "no parts given; nothing checked")
    bad = _nonfinite(prefix, **{f"A{v + 1}": A for v, A in enumerate(As)}, **{f"b{v + 1}": b for v, b in enumerate(bs)},
                     **({f"c{v + 1}": c for v, c in enumerate(cs)} if cs is not None else {}))
    if bad:
        return bad
    top = max(max_order or claimed + 1, claimed)
    res = additive_order_residuals(As, bs, top)
    bad = _residuals_finite(prefix, [x for pair in res.values() for x in pair])
    if bad:
        return bad
    p_all = p_pure = 0
    for q, (ra, rp) in res.items():
        if rp <= tol and p_pure == q - 1:
            p_pure = q
        if ra <= tol and p_all == q - 1:
            p_all = q
    shown = ", ".join(f"{q}: {ra:.1e}" for q, (ra, _rp) in res.items())
    fails, notes = [], []
    rows = [square_tableau(A, b)[0].sum(axis=1) for A, b in zip(As, bs)]
    n = max(r.size for r in rows)
    rows = [np.pad(r, (0, n - r.size)) for r in rows]
    nodes_differ = any(np.max(np.abs(r - rows[0])) > tol for r in rows[1:])
    if cs is not None:
        cs = [np.asarray(c, dtype=float) for c in cs]
        for v, (A, c) in enumerate(zip(As, cs)):
            A = np.asarray(A, dtype=float)
            if np.max(np.abs(A.sum(axis=1)[: c.size] - c[: A.shape[0]])) > tol:
                fails.append(f"row sums of part {v + 1} differ from its c")
        nodes_differ = nodes_differ or any(c.size != cs[0].size or np.max(np.abs(c - cs[0])) > tol for c in cs[1:])
    if nodes_differ:
        notes.append("the parts have different nodes c: the conditions checked here are complete for an autonomous"
                     " problem, but when each part evaluates f at its own time t + c h, time is not one shared variable"
                     " and further conditions apply (not checked; to check them, write t as a state variable)")
    if p_all < claimed:
        if p_pure >= claimed:
            fails.insert(0, f"each part has order {claimed} alone, but the coupling conditions hold only up to order"
                            f" {p_all} (largest residual over all colourings: {shown})")
        else:
            fails.insert(0, f"claims order {claimed} but the parts alone satisfy the conditions only up to {p_pure}"
                            f" and together up to {p_all} ({shown})")
    else:
        notes.insert(0, f"order {claimed} confirmed as a pair, coupling conditions included ({shown})")
    return Result(FAIL if fails else PASS, prefix + "; ".join(fails + notes))


# Rosenbrock and W-methods: (I - h g_ii J) k_i = h f(y + sum_j a_ij k_j) + h J sum_{j<i} g_ij k_j, y1 = y + b . k.
# With the exact Jacobian, order p holds when b . Phi(t) = 1/gamma(t) for every tree of at most p vertices,
# where an edge from a vertex with exactly one child uses B = alpha + Gamma (diagonal included) and every other
# edge uses alpha (Hairer & Wanner II, sec. IV.7, Thm 7.2). The stability function is that of the RK method
# (B, b). A W-method (any matrix in place of J) needs each single-child edge split: all-alpha gives 1/gamma(t),
# any marking with a Gamma edge must give 0 (Steihaug & Wolfbrandt 1979; Hairer & Wanner IV.7, W-methods).

def _phi_ros(t, alpha, B, e):
    v = e.copy()
    M = B if len(t) == 1 else alpha
    for s in t:
        v = v * (M @ _phi_ros(s, alpha, B, e))
    return v


def _phi_w(t, alpha, G, e):
    """Phi for every alpha/Gamma marking of the single-child edges of t, as {key: (has_gamma, vector)}.

    Below a vertex with two or more children the edges use alpha, but each child subtree keeps all of its own
    markings, so the markings of a tree are the products of its children's (a marked chain below a branch is a
    condition too: b . ((alpha Gamma alpha e) * (alpha e)) = 0 at order 4). Keys are canonical, so markings that
    differ only by the order of identical children are one condition."""
    import itertools
    kids = [_phi_w(s, alpha, G, e) for s in t]
    if len(t) == 1:
        return {(mark, k): (g or mark == "G", M @ v) for k, (g, v) in kids[0].items()
                for mark, M in (("a", alpha), ("G", G))}
    out = {}
    for combo in itertools.product(*(list(k.items()) for k in kids)):
        key = ("*",) + tuple(sorted((kk for kk, _ in combo), key=repr))
        if key in out:
            continue
        v = e.copy()
        for _, (_, w) in combo:
            v = v * (alpha @ w)
        out[key] = (any(g for _, (g, _) in combo), v)
    return out


def w_condition_count(order: int) -> int:
    """Number of distinct W-method order conditions with exactly `order` vertices (1, 2, 5, 13, 37, ...)."""
    e = np.ones(1)
    return sum(len(_phi_w(t, np.ones((1, 1)), np.ones((1, 1)), e)) for t in trees(order))


def rosenbrock_residuals(alpha, gamma, b, max_order: int = 5, *, w_method: bool = False, theta: float = 1.0) -> dict:
    """{order: largest residual over the trees of that order}, exact-Jacobian or (w_method=True) W conditions.
    With theta, `b` are dense-output weights b(theta) and the targets are theta^|t|/gamma(t) (zero for marked W
    trees): the continuous extension y0 + sum_i b_i(theta) k_i (Hairer & Wanner II, sec. IV.7, dense output)."""
    alpha = np.asarray(alpha, dtype=float)
    G = np.asarray(gamma, dtype=float)
    b = np.asarray(b, dtype=float)
    e = np.ones(b.size)
    out = {}
    for p in range(1, max_order + 1):
        r = 0.0
        for t in trees(p):
            target = theta ** p / _gamma(t)
            if w_method:
                for g, v in _phi_w(t, alpha, G, e).values():
                    r = max(r, abs(float(b @ v) - (0.0 if g else target)))
            else:
                r = max(r, abs(float(b @ _phi_ros(t, alpha, alpha + G, e)) - target))
        out[p] = r
    return out


def rosenbrock_dense_residuals(alpha, gamma, b_of_theta, *, max_order: int = 5, thetas=None,
                               w_method: bool = False) -> dict:
    """{order: largest residual} of the dense output over the thetas (default 0.1, 0.2, ..., 1). `b_of_theta` is
    a callable theta -> weights, or a fixed vector with `thetas=[theta]` (one point value). Default thetas 0, 0.1, ..., 1."""
    if thetas is None:
        if not callable(b_of_theta):
            raise ValueError("a fixed weight vector is the output at one theta: pass thetas=[theta]")
        thetas = DEFAULT_THETAS
    get = b_of_theta if callable(b_of_theta) else (lambda th: b_of_theta)
    out = {p: 0.0 for p in range(1, max_order + 1)}
    for th in thetas:
        res = rosenbrock_residuals(alpha, gamma, get(th), max_order, w_method=w_method, theta=float(th))
        for p, r in res.items():
            out[p] = max(out[p], r)
    return out


def check_rosenbrock(alpha, gamma, b, *, claimed: int, label: str = "", w_method: bool = False,
                     claimed_embedded: int | None = None, embedded=None, tol: float = 1e-8,
                     max_order: int | None = None, c=None, d=None, dense=None, claimed_dense: int | None = None,
                     thetas=None) -> Result:
    """PASS when the Rosenbrock method (alpha, Gamma, b) has the claimed order; with w_method=True, the order
    for any Jacobian approximation (W-method). Gamma is the full lower-triangular matrix with gamma_ii on the
    diagonal. Also reports R(inf) and A-stability, from the RK method (alpha + Gamma, b).

    `c` and `d`, when a code stores them: the stage times c_i (f is evaluated at t + c_i h) must be the row sums of
    alpha, and the coefficients d_i of h df/dt (gamma_i in Hairer and Wanner) the row sums of Gamma. The order
    conditions above are for autonomous problems and cannot see these; a wrong d_i drops a non-autonomous problem
    to first order (Boost.odeint rosenbrock4 stores d4 = +0.0362 for RODAS's -0.0362, 2026).

    `dense` with `claimed_dense`: the dense-output weights b(theta) (a callable, or one vector with `thetas=[theta]`),
    checked for that order at every theta (default 0, 0.1, ..., 1). Codes that store the interpolant in transformed form
    (Rodas: y0 + theta (y1 - y0) + theta (theta - 1)(...)) must be converted to weights on the k_i first."""
    top = max(max_order or claimed + 1, claimed)
    kind = "W-method" if w_method else "Rosenbrock (exact Jacobian)"
    prefix = f"{label}: " if label else ""
    bad = _nonfinite(prefix, alpha=alpha, gamma=gamma, b=b, embedded=embedded, c=c, d=d, dense=dense)
    if bad:
        return bad
    if callable(dense):
        for th in (DEFAULT_THETAS if thetas is None else thetas):
            bad = _nonfinite(prefix, **{f"dense weights at theta={float(th):g}": dense(th)})
            if bad:
                return bad

    def order_of(bb):
        res = rosenbrock_residuals(alpha, gamma, bb, top, w_method=w_method)
        p = 0
        while p < top and res[p + 1] <= tol:
            p += 1
        return p, ", ".join(f"{q}: {r:.1e}" for q, r in res.items())

    if embedded is not None and claimed_embedded is None:
        raise ValueError("embedded weights given without claimed_embedded: say which order they should have")
    G = np.asarray(gamma, dtype=float)
    fails, notes = [], []
    # tables converted from Hairer's transformed form carry round-off above the diagonal
    upper = tol * max(1.0, float(np.max(np.abs(G))), float(np.max(np.abs(np.asarray(alpha, dtype=float)))))
    if np.any(np.abs(np.triu(G, 1)) > upper) or np.any(np.abs(np.triu(np.asarray(alpha, dtype=float))) > upper):
        fails.append("alpha must be strictly and Gamma lower triangular")
    for name, given, sums, what in (("c", c, np.asarray(alpha, dtype=float).sum(axis=1), "row sums of alpha"),
                                    ("d", d, G.sum(axis=1), "row sums of Gamma")):
        if given is None:
            continue
        given = np.asarray(given, dtype=float).ravel()
        n = min(given.size, sums.size)
        diff = np.abs(given[:n] - sums[:n])
        if given.size < sums.size and np.any(np.abs(sums[given.size:]) > tol):
            fails.append(f"{name} has {given.size} entries for {sums.size} stages")
        if n and diff.max() > tol:
            i = int(np.argmax(diff))
            fails.append(f"{name}[{i}] = {given[i]:.10g} but the {what} give {sums[i]:.10g}"
                         + (" (sign flipped)" if abs(given[i] + sums[i]) <= tol else "")
                         + ("; d multiplies h df/dt, so non-autonomous problems lose order" if name == "d" else
                            "; f is evaluated at the wrong times, so non-autonomous problems lose order"))
        elif n:
            notes.append(f"{name} agrees with the {what}")
    p, shown = order_of(b)
    if p < claimed:
        fails.insert(0, f"claims order {claimed} as a {kind} but satisfies the conditions only up to {p} ({shown})")
    else:
        notes.append(f"order {claimed} confirmed as a {kind} (largest residuals by order: {shown})")
    if embedded is not None and claimed_embedded is not None:
        pe, she = order_of(embedded)
        if pe < claimed_embedded:
            fails.append(f"embedded weights claim order {claimed_embedded}, conditions hold only up to {pe} ({she})")
        else:
            notes.append(f"embedded order {claimed_embedded} confirmed")
    if dense is not None:
        if claimed_dense is None:
            raise ValueError("dense weights given without claimed_dense: say which order they should have")
        res = rosenbrock_dense_residuals(alpha, gamma, dense, max_order=claimed_dense + 1, thetas=thetas,
                                         w_method=w_method)
        qd = 0
        while qd < claimed_dense + 1 and res[qd + 1] <= tol:
            qd += 1
        shd = ", ".join(f"{q}: {r:.1e}" for q, r in res.items())
        where = "the point value" if thetas is not None and len(thetas) == 1 else "the dense output"
        if qd < claimed_dense:
            fails.append(f"{where} should have order {claimed_dense} but its conditions hold only up to {qd} ({shd})")
        else:
            notes.append(f"{where} has order {qd if qd <= claimed_dense else f'at least {qd}'}"
                         f" (claimed {claimed_dense}; {shd})")
    elif claimed_dense is not None:
        raise ValueError("claimed_dense given without dense weights")
    B = np.asarray(alpha, dtype=float) + G
    notes.append(f"R(inf) = {r_infinity(B, b):.3g}, A-stability margin {a_stability_margin(B, b):.2g}"
                 " (stability of the linear test equation, same for W-methods)")
    return Result(FAIL if fails else PASS, prefix + "; ".join(fails + notes))


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
    A1, b1, _ = square_tableau(A, b)
    if not (np.all(np.isfinite(A1)) and np.all(np.isfinite(b1))):
        return Result(FAIL, f"{name}: the candidate table contains non-finite coefficients")
    A1, b1 = _drop_fsal(A1, b1)
    A2, b2 = _drop_fsal(*square_tableau(ref["A"], ref["b"])[:2])
    if A1.shape != A2.shape:
        return Result(FAIL, f"{name}: {A1.shape[0]} stages, the published table has {A2.shape[0]}")
    dA, db = np.abs(A1 - A2), np.abs(b1 - b2)
    if max(dA.max(), db.max()) <= tol:
        return Result(PASS, f"{name}: coefficients match the published table to {tol:g}")
    i, j = np.unravel_index(int(np.argmax(dA)), dA.shape)
    where = f"A[{i}][{j}] off by {dA[i, j]:.3g}" if dA.max() >= db.max() else f"b[{int(np.argmax(db))}] off by {db.max():.3g}"
    return Result(FAIL, f"{name}: coefficients differ from the published table, largest at {where}")
