"""Each reference in physverify.references against an independent computation."""

import itertools
import math

import numpy as np
import pytest

from physverify import references as R
from physverify.references import zernike_osa


def test_ising_enumeration_matches_a_plain_loop():
    L, T, J, h = 3, 2.2, 0.8, 0.3
    Z = Es = Ms = 0.0
    for spins in itertools.product((-1, 1), repeat=L * L):
        s = np.array(spins).reshape(L, L)
        E = 0.0
        for i in range(L):
            for j in range(L):
                E -= J * s[i, j] * (s[(i + 1) % L, j] + s[i, (j + 1) % L]) + h * s[i, j]
        w = math.exp(-E / T)
        Z, Es, Ms = Z + w, Es + w * E, Ms + w * abs(s.sum())
    r = R.ising2d_exact(L, T, J, h)
    assert abs(r["e"] - Es / Z / L**2) < 1e-12
    assert abs(r["m_abs"] - Ms / Z / L**2) < 1e-12
    assert abs(r["Z"] - Z) / Z < 1e-12


def test_ising_specific_heat_is_the_temperature_derivative_of_energy():
    dT = 1e-4
    e = lambda T: R.ising2d_exact(4, T)["e"]  # noqa: E731
    c_fd = (e(2.3 + dT) - e(2.3 - dT)) / (2 * dT)
    assert abs(R.ising2d_exact(4, 2.3)["c"] - c_fd) < 1e-6


def test_heisenberg_chain_bond_energy_by_quadrature():
    # one bond: <cos theta> under exp(b cos theta) on the sphere
    b = 1.7
    z = np.linspace(-1, 1, 200001)
    w = np.exp(b * z)
    mean = np.trapezoid(z * w, z) / np.trapezoid(w, z)
    r = R.heisenberg_open_chain(5, 1.7, 1.0)
    assert abs(r["e"] - (-(4 / 5) * 1.7 * mean)) < 1e-9  # -(N-1)/N J <cos>
    assert abs(float(R.langevin(1e-5)) - 1e-5 / 3) < 1e-15


def test_heat_mode_and_gaussian_satisfy_their_equations():
    x, t, h = 0.37, 0.05, 1e-4
    u = lambda x, t: R.heat_sine_mode(x, t, L=2.0, kappa=0.7, mode=3)  # noqa: E731
    ut = (u(x, t + h) - u(x, t - h)) / (2 * h)
    uxx = (u(x + h, t) - 2 * u(x, t) + u(x - h, t)) / h**2
    assert abs(ut - 0.7 * uxx) < 1e-5
    g = lambda x, t: R.advection_diffusion_gaussian(x, t, 1.0, 0.5, v=0.3, D=0.2)  # noqa: E731
    x, t = 1.4, 2.0
    gt = (g(x, t + h) - g(x, t - h)) / (2 * h)
    gx = (g(x + h, t) - g(x - h, t)) / (2 * h)
    gxx = (g(x + h, t) - 2 * g(x, t) + g(x - h, t)) / h**2
    assert abs(gt + 0.3 * gx - 0.2 * gxx) < 1e-5


def test_double_pendulum_conserves_its_energy():
    p = (0.7, 1.9, 1.3, 0.6, 9.81)
    y = np.array([2.0, 0.0, -0.5, 0.3])

    def f(y):
        a = R.double_pendulum_acc(y[0], y[1], y[2], y[3], *p)
        return np.array([y[1], a[0], y[3], a[1]])

    E0 = R.double_pendulum_energy(y[0], y[1], y[2], y[3], *p)
    dt = 1e-3
    for _ in range(2000):
        k1 = f(y); k2 = f(y + dt / 2 * k1); k3 = f(y + dt / 2 * k2); k4 = f(y + dt * k3)
        y = y + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
    assert abs(R.double_pendulum_energy(y[0], y[1], y[2], y[3], *p) - E0) < 1e-6 * abs(E0)  # RK4, dt = 1e-3, 2 s: drift about 5e-8


def test_quantum_references():
    # infinite well against a fine finite-difference matrix
    n, W = 400, 2.0
    dx = W / n
    H = np.diag(np.full(n - 1, 1 / dx**2)) + np.diag(np.full(n - 2, -0.5 / dx**2), 1) + np.diag(np.full(n - 2, -0.5 / dx**2), -1)
    assert abs(np.linalg.eigvalsh(H)[0] / R.infinite_well_energy(1, W) - 1) < 1e-4
    # barrier: unitarity-free textbook limit, T -> 1 for V -> 0 and the E < V tunnelling formula
    assert abs(R.barrier_transmission(0.7, 1e-9, 2.0) - 1) < 1e-8
    k = math.sqrt(2 * 0.3) * 2.0
    assert abs(R.barrier_transmission(0.7, 1.0, 2.0) - 1 / (1 + math.sinh(k) ** 2 / (4 * 0.7 * 0.3))) < 1e-14
    # TFIM against dense diagonalisation
    N, J, h = 6, 1.1, 0.7
    X, Z, I = np.array([[0, 1], [1, 0]]), np.diag([1, -1]), np.eye(2)

    def op(d):
        out = np.ones((1, 1))
        for q in range(N):
            out = np.kron(out, d.get(q, I))
        return out

    Hd = sum(J * op({i: Z, i + 1: Z}) for i in range(N - 1)) + sum(h * op({i: X}) for i in range(N))
    assert abs(np.linalg.eigvalsh(Hd)[0] - R.tfim_open_ground_energy(N, J, h)) < 1e-10
    assert R.cantilever_tip(10.0, 5.0, 2e8, 1e-4)[0] == 10.0 * 125.0 / (3 * 2e8 * 1e-4)


def test_semi_infinite_step_limits():
    assert abs(R.semi_infinite_step(0.0, 1.0, 1e-5, 300.0, 1000.0) - 1000.0) < 1e-12
    assert abs(R.semi_infinite_step(1.0, 1.0, 1e-5, 300.0, 1000.0) - 300.0) < 1e-9


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


def test_morse_levels_match_finite_difference_eigenvalues():
    # hbar = m = 1: omega_e = a sqrt(2 D), omega_e x_e = a^2 / 2
    D, a = 12.0, 1.0
    x = np.linspace(-2.5, 14.0, 4000)
    h = x[1] - x[0]
    V = D * (1 - np.exp(-a * x)) ** 2
    H = np.diag(1 / h**2 + V) - np.diag(np.full(len(x) - 1, 0.5 / h**2), 1) - np.diag(np.full(len(x) - 1, 0.5 / h**2), -1)
    E = np.linalg.eigvalsh(H)[:4]
    assert np.max(np.abs(E - R.morse_levels(np.arange(4), a * math.sqrt(2 * D), a * a / 2))) < 2e-3


def test_morse_width_is_the_distance_between_turning_points():
    D, a, E = 3.0, 1.7, 1.1
    V = lambda r: D * (1 - math.exp(-a * r)) ** 2 - E  # noqa: E731
    lo, hi = R._bisect(V, -2.0, 0.0), R._bisect(V, 0.0, 20.0)
    assert abs((hi - lo) - R.morse_turning_width(E, D, a)) < 1e-12


def test_deflection_matches_orbit_integration_and_weak_field():
    b = 1000.0
    assert abs(R.schwarzschild_deflection(b) / (4 / b + 15 * math.pi / (4 * b * b) + 128 / (3 * b**3)) - 1) < 2e-6  # 2 int - pi loses digits at large b
    # integrate u'' + u = 3 u^2 from far away (RK4 in phi) and read the outgoing direction
    b = 8.0
    u, du, phi, dphi = 1e-6, 1 / b, 0.0, 1e-4
    f = lambda u: 3 * u * u - u  # noqa: E731
    while True:
        k1u, k1d = du, f(u)
        k2u, k2d = du + 0.5 * dphi * k1d, f(u + 0.5 * dphi * k1u)
        k3u, k3d = du + 0.5 * dphi * k2d, f(u + 0.5 * dphi * k2u)
        k4u, k4d = du + dphi * k3d, f(u + dphi * k3u)
        u_new = u + dphi / 6 * (k1u + 2 * k2u + 2 * k3u + k4u)
        du = du + dphi / 6 * (k1d + 2 * k2d + 2 * k3d + k4d)
        phi += dphi
        if u_new <= 0:
            phi -= dphi * u_new / (u_new - u)  # linear interpolation to u = 0
            break
        u = u_new
    assert abs((phi - math.pi) - R.schwarzschild_deflection(8.0)) < 1e-4
    with pytest.raises(ValueError):
        R.schwarzschild_deflection(5.0)


def test_kerr_isco_is_the_minimum_of_the_circular_orbit_energy():
    for a, pro in ((0.0, True), (0.5, True), (0.5, False), (0.9, True)):
        s = 1 if pro else -1
        r = np.linspace(1.2, 12, 200001)
        E = (r**1.5 - 2 * r**0.5 + s * a) / (r**0.75 * np.sqrt(np.maximum(r**1.5 - 3 * r**0.5 + 2 * s * a, 1e-300)))
        E[r**1.5 - 3 * r**0.5 + 2 * s * a <= 0] = np.inf
        assert abs(r[np.argmin(E)] - R.kerr_isco(a, pro)) < 2e-3
    assert R.kerr_isco(1.0) == pytest.approx(1.0) and R.kerr_isco(1.0, False) == pytest.approx(9.0)


def test_inhour_period_is_the_slowest_eigenvalue_of_point_kinetics():
    beta = np.array([0.000266, 0.001491, 0.001316, 0.002849, 0.000896, 0.000182])
    lam = np.array([0.0127, 0.0317, 0.115, 0.311, 1.40, 3.87])
    L = 2e-5
    for rho in (0.002, 0.0005, -0.001, -0.01):
        A = np.zeros((7, 7))
        A[0, 0] = (rho - beta.sum()) / L
        A[0, 1:] = lam
        A[1:, 0] = beta / L
        A[1:, 1:] = -np.diag(lam)
        w = np.max(np.linalg.eigvals(A).real)
        assert abs(R.inhour_stable_period(rho, L, beta, lam) * w - 1) < 1e-8
    assert R.inhour_stable_period(-0.05, L, beta, lam) == pytest.approx(-1 / lam.min(), rel=0.02)


def test_qnm_table_is_close_to_the_eikonal_limit_and_rejects_unknown_modes():
    for l in (1, 2):  # scalar modes approach the eikonal (photon-sphere) value quickly
        w = R.schwarzschild_qnm(l, 0)
        eik = ((l + 0.5) - 0.5j) / (3 * math.sqrt(3))
        assert abs(w - eik) / abs(eik) < 0.02
    assert R.schwarzschild_qnm(2, 2).real < R.schwarzschild_qnm(2, 0).real  # the -6M/r^3 term lowers the barrier
    with pytest.raises(ValueError):
        R.schwarzschild_qnm(7, 2)


def test_references_listing_names_real_functions():
    for name in R.REFERENCES:
        assert callable(getattr(R, name))


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
