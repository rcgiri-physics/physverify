"""Operator invariants (physverify.operators), each with a correct code and the bug pattern found in the
2026-11-01 corpus sessions, rebuilt here in a few lines."""


import numpy as np
import pytest

from physverify.operators import (
    check_advection_direction,
    check_force_gradient,
    check_nullspace,
    check_path,
    check_uniform_state,
)


def laplacian_1d(n, dx):
    A = np.zeros((n, n))
    for i in range(1, n - 1):
        A[i, i - 1:i + 2] = [1.0, -2.0, 1.0]
    return A / dx ** 2


def test_nullspace_passes_for_laplacian():
    assert check_nullspace(laplacian_1d(20, 0.05), 20).ok


def test_nullspace_catches_scrambled_coefficients():
    # the polar-grid bug: per-cell coefficients stacked in the wrong order, so rows no longer sum to zero
    n, dx = 12, 0.1
    A = laplacian_1d(n, dx)
    r = np.linspace(1, 2, n)
    B = A * r[:, None]
    B[3, 2:5] = B[5, 4:7]  # coefficients of another row
    B[3, 2:5] *= np.array([1.0, 1.0, 1.3])
    res = check_nullspace(B, n)
    assert res.status == "FAIL" and "index (3,)" in res.message


def test_nullspace_2d_callable_and_linear_field():
    def lap(f):
        out = np.zeros_like(f)
        out[1:-1, 1:-1] = f[2:, 1:-1] + f[:-2, 1:-1] + f[1:-1, 2:] + f[1:-1, :-2] - 4 * f[1:-1, 1:-1]
        return out
    X, Y = np.meshgrid(np.arange(8.0), np.arange(9.0), indexing="ij")
    assert check_nullspace(lap, (8, 9)).ok
    assert check_nullspace(lap, (8, 9), field=3 * X - 2 * Y + 1).ok  # linear fields too
    assert not check_nullspace(lap, (8, 9), field=X ** 2).ok


def upwind_step(T, F=0.0):
    # flux-difference rate times dt/(rho V), the solver convention in the corpus code
    out = T.copy()
    out[1:-1] += F * (T[:-2] - T[1:-1])
    return out


def lw_as_value(T, F=0.0):
    # the bug: the scheme returns the new value T + correction, and the solver adds it as a rate
    new = T.copy()
    new[1:-1] = T[1:-1] - 0.5 * F * (T[2:] - T[:-2]) + 0.5 * F ** 2 * (T[2:] - 2 * T[1:-1] + T[:-2])
    out = T.copy()
    out[1:-1] += 1e-3 * new[1:-1]
    return out


def test_uniform_state():
    T = np.full(21, 300.0)
    assert check_uniform_state(upwind_step, T).ok
    res = check_uniform_state(lw_as_value, T)
    assert res.status == "FAIL" and "uniform state changed after 1 step" in res.message


def advect(f, t, u=1.0, sign=1.0):
    n = len(f)
    dx = 1.0 / n
    c = 0.4
    dt = c * dx / abs(u)
    for _ in range(int(round(t / dt))):
        if sign * u > 0:
            f = f - c * (f - np.roll(f, 1))
        else:
            f = f + c * (np.roll(f, -1) - f)
    return f


def test_advection_direction():
    x = np.arange(400) / 400
    assert check_advection_direction(lambda f, t: advect(f, t, 1.0), x, 1.0, 0.2).ok
    assert check_advection_direction(lambda f, t: advect(f, t, -1.0), x, -1.0, 0.2).ok
    res = check_advection_direction(lambda f, t: advect(f, t, 1.0, sign=-1.0), x, 1.0, 0.2)
    assert res.status == "FAIL" and "opposite to the velocity" in res.message
    res = check_advection_direction(lambda f, t: advect(f, 1.5 * t, 1.0), x, 1.0, 0.2)
    assert res.status == "FAIL" and "expected u t" in res.message


def test_advection_too_far():
    with pytest.raises(ValueError):
        check_advection_direction(lambda f, t: f, np.arange(10) / 10, 1.0, 0.6)


def test_force_gradient():
    lam = np.array([6e-11, 1.5e-11, 3e-11])
    c = np.array([0.35, 0.55, 0.10])
    U = lambda r: np.sum(c * np.exp(-r / lam)) / r
    good = lambda r: np.sum(c * np.exp(-r / lam) / r * (1 / r + 1 / lam))
    bad = lambda r: np.sum(c * np.exp(-r / lam) / r * (1 / r + c))  # the Moliere bug: c_i instead of 1/lambda_i
    rs = [2e-11, 5e-11, 1e-10]
    assert check_force_gradient(U, good, rs).ok
    res = check_force_gradient(U, bad, rs)
    assert res.status == "FAIL" and "ratio" in res.message
    lj = lambda r: 4 * ((1 / r) ** 12 - (1 / r) ** 6)
    ljf = lambda r: 24 * (2 * (1 / r) ** 12 - (1 / r) ** 6) / r
    assert check_force_gradient(lj, ljf, np.linspace(0.95, 3.0, 20)).ok


def _aoup_msd(dt, with_dt=True, T=2.0, n=4000, seed=1):
    """x' = p, p' = -p + xi: mean squared displacement at T, with its standard error."""
    rng = np.random.default_rng(seed)
    p = rng.uniform(-1, 1, n)
    x = np.zeros(n)
    for _ in range(int(round(T / dt))):
        x += p * dt if with_dt else p
        p += -p * dt + np.sqrt(dt) * rng.standard_normal(n)
    return float((x ** 2).mean()), float((x ** 2).std() / np.sqrt(n))


def _moving_wall_error(tol, frozen):
    """u_t = u_xx + x cos t, u(0)=0, u(1)=sin t, exact u = x sin t; RK4 with dt ~ tol^(1/5), as an adaptive RK45 would use."""
    n = 11
    x = np.linspace(0, 1, n)
    h = x[1] - x[0]

    def F(t, y):
        d = np.zeros(n)
        d[1:-1] = (y[2:] - 2 * y[1:-1] + y[:-2]) / h ** 2 + x[1:-1] * np.cos(t)
        return d

    steps = int(np.ceil(1 / (0.04 * tol ** 0.2)))  # stable: dt below h^2 / 2
    dt = 1 / steps
    y, t = np.zeros(n), 0.0
    for _ in range(steps):
        K, stages = [], [(0, 0.0), (0.5, 0.5), (0.5, 0.5), (1, 1.0)]
        for s, (a, c) in enumerate(stages):
            Y = y + (dt * a * K[-1] if s else 0)
            if not frozen:
                Y = Y.copy()
                Y[-1] = np.sin(t + c * dt)
            K.append(F(t + c * dt, Y))
        y = y + dt / 6 * (K[0] + 2 * K[1] + 2 * K[2] + K[3])
        t += dt
        y[-1] = np.sin(t)
    return np.abs(y - x * np.sin(t)).max()


def fine_integrals(steps, n=2000, m=2, seed=0):
    """Left-point sums on `steps` substeps of a unit interval: correct integrals whose error falls with `steps`."""
    rng = np.random.default_rng(seed)
    d = rng.standard_normal((n, steps, m)) / np.sqrt(steps)
    W = np.zeros((n, m))
    I2 = np.zeros((n, m, m))
    I3 = np.zeros((n, m, m, m))
    for k in range(steps):
        dw = d[:, k]
        I3 += I2[:, :, :, None] * dw[:, None, None, :]
        I2 += W[:, :, None] * dw[:, None, :]
        W += dw
    return W, I2, I3


def test_path():
    square = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 0)]
    assert check_path(square, segment_lengths=1.0, closed=True).ok
    jumped = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 0, 0), (1, -1, 0)]  # each new segment started from vertex 1
    res = check_path(jumped, segment_lengths=1.0)
    assert res.status == "FAIL" and "segment 2" in res.message
    assert check_path(jumped[:4] + [(1, -1, 0)], closed=True).status == "FAIL"
