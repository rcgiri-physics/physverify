"""Identity checks: round trips, derivatives, unitarity, scale factors and conventions."""

import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

from physverify.checks import FAIL, PASS
from physverify.identities import (
    check_agree,
    check_derivative,
    check_identity,
    check_roundtrip,
    check_scale,
    check_unitary,
    check_vec_convention,
    fd_derivative,
    laplacian_fd,
    vary_one,
)

ROOT = Path(__file__).resolve().parents[1]


def _runner():
    spec = importlib.util.spec_from_file_location("pv_runner_b8", ROOT / "sandbox" / "runner.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pixel_to_sky(p, n, crpix):
    return (p + 1 - crpix) * 2.0  # 0-based pixel to arcsec, FITS reference pixel crpix at 0 arcsec


def _sabine(S, V, a, m, c=343.0):
    return 24 * math.log(10) / c * V / (a * S + 4 * m * V)


def _eyring_bug(S, V, a, m, c=343.0):
    return -(24 * math.log(10) / c) * V / (S * math.log(1 - a) + 4 * m * V)


def _eyring(S, V, a, m, c=343.0):
    return -(24 * math.log(10) / c) * V / (S * math.log(1 - a) - 4 * m * V)


SOURCE = '''
from __future__ import annotations
import numpy as np
import package_that_is_not_installed
from .sibling import helper

SCALE = 2.0

def centered_diff(x):
    return np.gradient(x)

def curvature(p: Spec) -> float:
    return SCALE * centered_diff(p)

def unrelated():
    raise RuntimeError("must not be needed")

run_the_whole_simulation_at_import()
'''


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


def test_roundtrip_catches_a_half_pixel_reference():
    n = 20
    centre = (n - 1) / 2  # 0-based centre pixel
    good = check_roundtrip(lambda p: _pixel_to_sky(p, n, (n + 1) / 2), lambda s: s / 2.0 + (n + 1) / 2 - 1, [centre, 0.0, 7.3])
    assert good.status == PASS
    # the buggy copy rebuilds the header with crpix = 1 + n/2, the inverse still uses the original (n + 1)/2
    bad = check_roundtrip(lambda p: _pixel_to_sky(p, n, 1 + n / 2), lambda s: s / 2.0 + (n + 1) / 2 - 1, [centre])
    assert bad.status == FAIL and "0.5" in bad.message


def test_roundtrip_handles_arrays_and_complex():
    rng = np.random.default_rng(0)
    S = (rng.normal(size=(3, 2, 2)) + 1j * rng.normal(size=(3, 2, 2))) * 0.3
    eye = np.eye(2)
    s2z = lambda s: 50 * (eye + s) @ np.linalg.inv(eye - s)  # noqa: E731
    z2s = lambda z: (z / 50 - eye) @ np.linalg.inv(z / 50 + eye)  # noqa: E731
    assert check_roundtrip(s2z, z2s, [S], atol=1e-12).status == PASS


def test_agree_catches_the_eyring_air_sign():
    # Eyring -> Sabine as a -> 0, with or without air absorption
    cases = [(94.0, 60.0, 1e-4, m) for m in (0.0, 0.005, 0.05)]
    assert check_agree(_eyring, _sabine, cases, rtol=1e-3, names=("eyring", "sabine")).status == PASS
    r = check_agree(_eyring_bug, _sabine, cases, rtol=1e-3, names=("eyring", "sabine"))
    assert r.status == FAIL and "eyring" in r.message


def test_derivative_check_and_fd():
    f = lambda x: np.exp(-x) * np.sin(3 * x)  # noqa: E731
    df = lambda x: np.exp(-x) * (3 * np.cos(3 * x) - np.sin(3 * x))  # noqa: E731
    assert check_derivative(f, df, [0.0, 0.4, 2.0]).status == PASS
    assert check_derivative(f, lambda x: df(x) + 1e-3 * np.cos(x), [0.4]).status == FAIL
    assert abs(fd_derivative(np.cos, 0.3, order=2) + math.cos(0.3)) < 1e-6


def test_margules_activity_derivative():
    # binary symmetric Margules, GE/RT = A x1 x2: ln g1 = A x2^2. d g1/d n1 at n = 1 is -2 A x2^2 g1 (exact)
    A = 1.0

    def gamma1(n1, n2=0.75):
        x2 = n2 / (n1 + n2)
        return math.exp(A * x2 * x2)

    def exact(n1, n2=0.75):  # d/dn1 exp(A x2^2), dx2/dn1 = -n2/n^2
        n = n1 + n2
        return gamma1(n1) * 2 * A * (n2 / n) * (-n2 / n**2)

    assert check_derivative(gamma1, exact, [0.25]).status == PASS
    wrong = lambda n1: -A * 0.75 * gamma1(n1)  # the "x-derivative" a static reader proposed  # noqa: E731
    assert check_derivative(gamma1, wrong, [0.25]).status == FAIL


def test_poisson_identity_for_plummer():
    b = 0.8
    phi = lambda x: -1.0 / np.sqrt(x @ x + b * b)  # noqa: E731
    rho = lambda x: 3 / (4 * np.pi * b**3) * (1 + (x @ x) / b**2) ** -2.5  # noqa: E731
    pts = [np.array([0.3, 0.1, -0.2]), np.array([1.0, 0.5, 0.2])]
    good = check_identity([(f"x={p}", laplacian_fd(phi, p), 4 * np.pi * rho(p)) for p in pts], rtol=1e-5, what="Poisson")
    assert good.status == PASS
    bad = check_identity([(f"x={p}", laplacian_fd(phi, p), 4 * np.pi * rho(p) * 1.02) for p in pts], rtol=1e-5, what="Poisson")
    assert bad.status == FAIL


def test_unitary():
    th = 0.7
    U = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]]) * np.exp(0.3j)
    assert check_unitary(np.stack([U, U.T])).status == PASS
    assert check_unitary(U * 1.001).status == FAIL


def test_nonfinite_is_a_failure():
    assert check_identity([("nan", np.nan, 1.0)]).status == FAIL


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


def test_check_scale_names_a_missing_factor():
    x = np.linspace(0, 1, 50)
    exact = np.cos(x)
    r = check_scale(2 * exact, exact)
    assert not r.ok and "which is 2" in r.message
    assert check_scale(exact * (1 + 1e-9), exact).ok
    assert "shape" in check_scale(np.sin(7 * x), exact).message


def test_vec_convention_tells_row_from_column_stacking():
    rng = np.random.default_rng(0)
    A, X = rng.normal(size=(3, 3)), rng.normal(size=(3, 3))
    left = lambda M: A @ M  # noqa: E731
    S_col = np.kron(np.eye(3), A)  # vec(A X) = (I kron A) vec(X) for column stacking
    assert "F-order" in check_vec_convention(S_col, left, X).message
    assert not check_vec_convention(S_col, left, X, expected="C").ok
    assert check_vec_convention(np.kron(A, np.eye(3)), left, X, expected="C").ok
