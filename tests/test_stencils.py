"""Finite-difference stencil checks."""

from fractions import Fraction

import numpy as np

from physverify.checks import FAIL
from physverify.stencils import check_stencil, stencil_order


def test_check_stencil_rejects_nonfinite_weights():
    result = check_stencil([-1, 0, 1], [-0.5, np.nan, 0.5], 1, claimed=2)
    assert result.status == FAIL and "finite" in result.message


def test_check_stencil_accepts_exact_weights_too_large_for_a_float():
    big = 10**400
    assert check_stencil([-1, 0, 1], [-big, 0, big], 1, claimed=2, divisor=2 * big).ok


def _dy_buggy(Lx, Ly, n):
    """d/dy of sin(2 pi y / Ly) on an n x n periodic grid, with the spacing taken from Lx (the L174 pattern)."""
    y = np.arange(n) * Ly / n
    f = np.sin(2 * np.pi * y / Ly)
    dy = Lx / n
    return (np.roll(f, -1) - np.roll(f, 1)) / (2 * dy), 2 * np.pi / Ly * np.cos(2 * np.pi * y / Ly)


G = 1.4


def _euler(W):
    rho, u, p = W
    E = p / (G - 1) + 0.5 * rho * u * u
    return np.array([rho * u, rho * u * u + p, u * (E + p)])


def _rusanov(WL, WR):
    sL = abs(WL[1]) + np.sqrt(G * WL[2] / WL[0])
    sR = abs(WR[1]) + np.sqrt(G * WR[2] / WR[0])
    s = max(sL, sR)
    cons = lambda W: np.array([W[0], W[0] * W[1], W[2] / (G - 1) + 0.5 * W[0] * W[1] ** 2])  # noqa: E731
    return 0.5 * (_euler(WL) + _euler(WR)) - 0.5 * s * (cons(WR) - cons(WL))


def _hll(WL, WR):
    cL, cR = np.sqrt(G * WL[2] / WL[0]), np.sqrt(G * WR[2] / WR[0])
    sL, sR = min(WL[1] - cL, WR[1] - cR), max(WL[1] + cL, WR[1] + cR)
    cons = lambda W: np.array([W[0], W[0] * W[1], W[2] / (G - 1) + 0.5 * W[0] * W[1] ** 2])  # noqa: E731
    if sL >= 0:
        return _euler(WL)
    if sR <= 0:
        return _euler(WR)
    return (sR * _euler(WL) - sL * _euler(WR) + sL * sR * (cons(WR) - cons(WL))) / (sR - sL)


STATES = [np.array([1.0, 0.3, 1.0]), np.array([0.5, -0.2, 0.4]), np.array([2.0, 0.0, 3.0])]


UP = [(np.array([1.0, 5.0, 1.0]), np.array([1.3, 4.0, 0.8]))]


MIRROR = (lambda W: np.array([W[0], -W[1], W[2]]), (-1, 1, -1))


def test_standard_stencils_and_a_wrong_order_claim():
    assert check_stencil([-1, 0, 1], [1, -2, 1], 2, claimed=2).ok
    assert check_stencil([-2, -1, 0, 1, 2], [1, -8, 0, 8, -1], 1, divisor=12, claimed=4).ok
    # the L220 pattern: a table called 8th order whose moments give order 6
    w6 = [Fraction(1, 90), Fraction(-3, 20), Fraction(3, 2), Fraction(-49, 18), Fraction(3, 2), Fraction(-3, 20), Fraction(1, 90)]
    assert stencil_order(range(-3, 4), w6, 2) == (1.0, 6)
    r = check_stencil(range(-3, 4), w6, 2, claimed=8)
    assert not r.ok and "order 6" in r.message


def test_stencil_missing_factor_and_wrong_derivative():
    r = check_stencil([-1, 1], [-1, 1], 1)  # forgot the 1/2 of a central difference (the L177 pattern)
    assert not r.ok and "2 times" in r.message
    assert "does not approximate" in check_stencil([-1, 0, 1], [1, 1, 1], 1).message
    assert check_stencil([-1.0, 0.0, 1.0], [0.5, -1.0, 0.5], 2, divisor=0.5).ok
