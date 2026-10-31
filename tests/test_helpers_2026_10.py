"""Helpers added after the 2026-10 daily corpus sessions: each test repeats the bug pattern it came from."""

from fractions import Fraction

import numpy as np
import pytest

from physverify.fluxes import check_flux
from physverify.identities import check_scale, check_vec_convention, vary_one
from physverify.references import zernike_osa
from physverify.stencils import check_stencil, stencil_order


# --- vary_one: a bug hidden by symmetric defaults ---

def _dy_buggy(Lx, Ly, n):
    """d/dy of sin(2 pi y / Ly) on an n x n periodic grid, with the spacing taken from Lx (the L174 pattern)."""
    y = np.arange(n) * Ly / n
    f = np.sin(2 * np.pi * y / Ly)
    dy = Lx / n
    return (np.roll(f, -1) - np.roll(f, 1)) / (2 * dy), 2 * np.pi / Ly * np.cos(2 * np.pi * y / Ly)


def test_vary_one_finds_the_parameter_that_breaks_a_passing_test():
    r = vary_one(_dy_buggy, {"Lx": 1.0, "Ly": 1.0, "n": 256}, {"Lx": 2.0, "Ly": [2.0, 3.0], "n": 512}, rtol=1e-3, atol=1e-3)
    assert not r.ok
    assert "Lx = 2.0" in r.message and "Ly = 2.0" in r.message and "n = 512" not in r.message


def test_vary_one_passes_a_correct_test_and_reports_a_failing_default():
    good = lambda a, b: (a + b, b + a)  # noqa: E731
    assert vary_one(good, {"a": 1.0, "b": 1.0}, {"a": [2.0, -3.0]}).ok
    bad = lambda a: False  # noqa: E731
    assert "already at the defaults" in vary_one(bad, {"a": 1}, {"a": 2}).message
    with pytest.raises(ValueError):
        vary_one(good, {"a": 1.0, "b": 1.0}, {"c": 1})


# --- check_scale: shape right, size wrong ---

def test_check_scale_names_a_missing_factor():
    x = np.linspace(0, 1, 50)
    exact = np.cos(x)
    r = check_scale(2 * exact, exact)
    assert not r.ok and "which is 2" in r.message
    assert check_scale(exact * (1 + 1e-9), exact).ok
    assert "shape" in check_scale(np.sin(7 * x), exact).message


# --- check_vec_convention ---

def test_vec_convention_tells_row_from_column_stacking():
    rng = np.random.default_rng(0)
    A, X = rng.normal(size=(3, 3)), rng.normal(size=(3, 3))
    left = lambda M: A @ M  # noqa: E731
    S_col = np.kron(np.eye(3), A)  # vec(A X) = (I kron A) vec(X) for column stacking
    assert "F-order" in check_vec_convention(S_col, left, X).message
    assert not check_vec_convention(S_col, left, X, expected="C").ok
    assert check_vec_convention(np.kron(A, np.eye(3)), left, X, expected="C").ok


# --- stencils ---

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


# --- fluxes ---

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


# --- Zernike reference ---

def test_zernike_osa_is_orthonormal_on_the_unit_disk():
    # Gauss-Legendre in rho (weight rho) times a uniform rule in theta: exact for these polynomials
    x, w = np.polynomial.legendre.leggauss(20)
    rho, wr = 0.5 * (x + 1), 0.5 * w
    th = np.linspace(0, 2 * np.pi, 64, endpoint=False)
    R, T = np.meshgrid(rho, th, indexing="ij")
    W = (wr * rho)[:, None] * (2 * np.pi / th.size) / np.pi  # mean over the disk
    modes = [(0, 0), (1, -1), (1, 1), (2, 0), (2, 2), (3, -3), (4, 0), (4, -2)]
    gram = np.array([[np.sum(W * zernike_osa(*a, R, T) * zernike_osa(*b, R, T)) for b in modes] for a in modes])
    assert np.allclose(gram, np.eye(len(modes)), atol=1e-12)
    assert np.isclose(zernike_osa(2, 0, 1.0, 0.0), np.sqrt(3))  # defocus sqrt(3) (2 rho^2 - 1)
    with pytest.raises(ValueError):
        zernike_osa(3, 0, 0.5, 0.0)
