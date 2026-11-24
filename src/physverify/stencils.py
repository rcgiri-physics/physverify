"""Finite-difference stencils: consistency and order from the weights alone (no grid, no solver).

A stencil for the d-th derivative, sum_k w_k f(x + k h) / h^d, has Taylor moments m_n = sum_k w_k k^n / n!.
It is consistent when m_n = 0 for n < d and m_d = 1, and its order of accuracy is p when the first nonzero
moment after m_d is m_{d+p} (LeVeque, Finite Difference Methods for ODEs and PDEs, sec. 1.5; Fornberg 1988).
In the 2026-10 corpus sessions four repositories had FD tables to check this way, and one "8th-order" table
had order 6.
"""

from __future__ import annotations

from fractions import Fraction
from math import factorial, isfinite

import numpy as np

from .checks import FAIL, PASS, Result


def _exact(x) -> bool:
    return isinstance(x, (int, Fraction)) and not isinstance(x, bool)


def stencil_moments(offsets, weights, upto: int) -> list:
    """Taylor moments m_0..m_upto of a stencil; exact when offsets and weights are integers or Fractions."""
    exact = all(map(_exact, weights)) and all(map(_exact, offsets))
    out = []
    for n in range(upto + 1):
        s = sum(w * (Fraction(k) ** n if exact else float(k) ** n) for k, w in zip(offsets, weights))
        out.append(s / factorial(n))
    return out


def stencil_order(offsets, weights, deriv: int, *, tol: float = 1e-10, max_order: int = 20):
    """(scale, order): m_deriv (1 for a consistent stencil) and the order of accuracy, or (m_deriv, None)
    when a lower moment is nonzero (the stencil does not approximate this derivative)."""
    if len(offsets) != len(weights):
        raise ValueError("offsets and weights differ in length")
    m = stencil_moments(offsets, weights, deriv + max_order)
    norm = max(1.0, max(abs(float(w)) for w in weights))
    if any(abs(float(x)) > tol * norm for x in m[:deriv]):
        return float(m[deriv]), None
    for n in range(deriv + 1, len(m)):
        if abs(float(m[n])) > tol * norm:
            return float(m[deriv]), n - deriv
    return float(m[deriv]), max_order


def check_stencil(offsets, weights, deriv: int, *, claimed: int | None = None, divisor=1, tol: float = 1e-10) -> Result:
    """A stencil approximates the `deriv`-th derivative, with the right scale, to the claimed order.

    `offsets` are grid offsets such as [-1, 0, 1]; `weights` as written in the code, before division by
    `divisor` (pass 12 for weights written as integers over 12). Integer and Fraction weights are checked
    exactly. FAIL for a lower moment that is not zero, a scale other than 1 (a missing factor such as 1/2),
    or an order below `claimed`.
    """
    # integers and Fractions are always finite, and may be too large for a float
    if not all(_exact(x) or isfinite(float(x)) for values in ((divisor,), offsets, weights) for x in values):
        return Result(FAIL, "the stencil offsets, weights and divisor must be finite")
    if _exact(divisor) and all(map(_exact, weights)):
        w = [Fraction(x, divisor) for x in weights]
    else:
        w = [float(x) / float(divisor) for x in weights]
    scale, order = stencil_order(offsets, w, deriv, tol=tol)
    name = {1: "first", 2: "second", 3: "third", 4: "fourth"}.get(deriv, f"{deriv}th")
    if order is None:
        return Result(FAIL, f"the stencil does not approximate the {name} derivative: a lower Taylor moment is not zero")
    if abs(scale - 1) > tol:
        return Result(FAIL, f"the stencil gives {scale:.6g} times the {name} derivative (order {order});"
                            " a factor is missing from the weights or the divisor")
    if claimed is not None and order < claimed:
        return Result(FAIL, f"the {name}-derivative stencil has order {order}, below the claimed {claimed}")
    more = f" (claimed {claimed})" if claimed is not None else ""
    return Result(PASS, f"consistent {name}-derivative stencil of order {order}{more}")


def jacobi_moment(k: int, alpha: float = 0.0, beta: float = 0.0) -> float:
    """Exact integral of x^k (1-x)^alpha (1+x)^beta over [-1, 1], alpha, beta > -1.

    m_0 = 2^(alpha+beta+1) B(alpha+1, beta+1); integrating d/dx [x^k (1-x)^(alpha+1) (1+x)^(beta+1)] = 0
    gives (k + alpha + beta + 2) m_(k+1) = k m_(k-1) + (beta - alpha) m_k, free of the cancellation of
    the binomial expansion.
    """
    from math import exp, lgamma

    prev, m = 0.0, 2.0 ** (alpha + beta + 1) * exp(lgamma(alpha + 1) + lgamma(beta + 1) - lgamma(alpha + beta + 2))
    for n in range(k):
        prev, m = m, (n * prev + (beta - alpha) * m) / (n + alpha + beta + 2)
    return m


def check_quadrature(nodes, weights, *, claimed: int, interval=(-1.0, 1.0), alpha: float = 0.0, beta: float = 0.0,
                     moments=None, rtol: float = 1e-10) -> Result:
    """A quadrature rule integrates every polynomial up to degree `claimed` exactly.

    An n-point Gauss rule is exact to degree 2n-1, Gauss-Radau to 2n-2, Gauss-Lobatto to 2n-3
    (Abramowitz and Stegun 25.4; Hildebrand, Introduction to Numerical Analysis, ch. 8). The weight
    function is the Jacobi weight (1-x)^alpha (1+x)^beta on [-1, 1]; nodes on another `interval` are
    mapped there (alpha = beta = 0 only). For another weight pass `moments(k)`, the exact integral
    of x^k on `interval`. Monomials are taken about the centre of the interval to keep the sums well
    conditioned. In the 2026-11 corpus session this found Radau weights that were wrong for alpha != beta.
    """
    x = np.asarray(nodes, dtype=float)
    w = np.asarray(weights, dtype=float)
    if x.shape != w.shape or x.ndim != 1:
        raise ValueError(f"nodes and weights must be 1-D of the same length, got {x.shape} and {w.shape}")
    a, b = map(float, interval)
    if moments is None:
        if (alpha or beta) and (a, b) != (-1.0, 1.0):
            raise ValueError("a Jacobi weight needs interval=(-1, 1); pass moments= for another weight")
        c, half = (a + b) / 2, (b - a) / 2
        t = (x - c) / half

        def exact(k):
            return jacobi_moment(k, alpha, beta) * half
    else:
        t = x

        def exact(k):
            return float(moments(k))
    if not np.all(np.isfinite(w)) or not np.all(np.isfinite(x)):
        return Result(FAIL, "the quadrature nodes or weights are not finite")
    scale = abs(exact(0)) or 1.0
    reached = -1
    first_bad = None
    for k in range(max(claimed, 2 * len(x)) + 1):
        e, g = exact(k), float(np.sum(w * t ** k))
        if abs(g - e) > rtol * max(abs(e), scale):
            first_bad = (k, g, e)
            break
        reached = k
    wt = "" if not (alpha or beta) else f" with weight (1-x)^{alpha:g} (1+x)^{beta:g}"
    if reached < claimed:
        k, g, e = first_bad
        return Result(FAIL, f"the {len(x)}-point rule{wt} is exact only to degree {reached} (claimed {claimed}):"
                            f" the integral of x^{k} is {g:.12g}, exact {e:.12g}")
    return Result(PASS, f"the {len(x)}-point rule{wt} integrates polynomials exactly to degree {reached} (claimed {claimed})")
