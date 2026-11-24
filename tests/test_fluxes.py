"""Numerical flux properties: consistency, upwinding."""

import numpy as np

from physverify.fluxes import check_flux


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


def test_hll_passes_all_flux_properties():
    r = check_flux(_hll, _euler, STATES, upwind_pairs=UP, downwind_pairs=[(b * [1, -1, 1], a * [1, -1, 1]) for a, b in UP],
                   mirror=MIRROR)
    assert r.ok, r.message


def test_rusanov_is_consistent_but_not_upwind():
    r = check_flux(_rusanov, _euler, STATES, upwind_pairs=UP, mirror=MIRROR)
    assert not r.ok and "upwinding" in r.message and "consistency" not in r.message


def test_inconsistent_flux_fails():
    r = check_flux(lambda a, b: 1.01 * _hll(a, b), _euler, STATES)
    assert not r.ok and "consistency" in r.message
