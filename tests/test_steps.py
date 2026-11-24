"""Step-size checks: step independence and tolerance response."""

import numpy as np
import pytest

from physverify.steps import check_step_independence, check_tolerance_response


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


def test_step_independence():
    assert check_step_independence(_aoup_msd, [0.1, 0.05, 0.02]).ok
    assert check_step_independence(lambda dt: 1.0 + 3 * dt, [0.4, 0.2, 0.1]).ok  # converging, not yet within rtol
    res = check_step_independence(lambda dt: _aoup_msd(dt, with_dt=False), [0.1, 0.05, 0.02])
    assert res.status == "FAIL" and "dt^-" in res.message
    assert check_step_independence(lambda dt: float("nan"), [0.1, 0.05, 0.02]).status == "FAIL"
    with pytest.raises(ValueError):
        check_step_independence(lambda dt: 1.0, [0.1, 0.05])


def test_tolerance_response():
    tols = [1e-5, 1e-7, 1e-9, 1e-11]
    assert check_tolerance_response(lambda tol: _moving_wall_error(tol, False), tols, floor=1e-13).ok
    res = check_tolerance_response(lambda tol: _moving_wall_error(tol, True), tols, floor=1e-13)
    assert res.status == "FAIL" and "tol^0.2" in res.message
    assert check_tolerance_response(lambda t: 1e-16, [1e-4, 1e-6, 1e-8], floor=1e-13).status == "INCONCLUSIVE"

    solve_ivp = pytest.importorskip("scipy.integrate").solve_ivp

    def scipy_err(tol):  # a correct adaptive solver, on an exact solution
        s = solve_ivp(lambda t, y: -y, (0, 2), [1.0], rtol=tol, atol=tol * 1e-2)
        return s.y[0, -1] - np.exp(-2)

    assert check_tolerance_response(scipy_err, [1e-4, 1e-6, 1e-8, 1e-10], floor=1e-13).ok
