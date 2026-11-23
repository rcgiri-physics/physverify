"""Each reference in physverify.references against an independent computation."""

import itertools
import math

import numpy as np

from physverify import references as R


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
    trapezoid = getattr(np, "trapezoid", None) or np.trapz  # np.trapezoid is NumPy 2.0+
    mean = trapezoid(z * w, z) / trapezoid(w, z)
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
