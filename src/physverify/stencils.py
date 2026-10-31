"""Finite-difference stencils: consistency and order from the weights alone (no grid, no solver).

A stencil for the d-th derivative, sum_k w_k f(x + k h) / h^d, has Taylor moments m_n = sum_k w_k k^n / n!.
It is consistent when m_n = 0 for n < d and m_d = 1, and its order of accuracy is p when the first nonzero
moment after m_d is m_{d+p} (LeVeque, Finite Difference Methods for ODEs and PDEs, sec. 1.5; Fornberg 1988).
In the 2026-10 corpus sessions four repositories had FD tables to check this way, and one "8th-order" table
had order 6.
"""

from __future__ import annotations

from fractions import Fraction
from math import factorial

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
