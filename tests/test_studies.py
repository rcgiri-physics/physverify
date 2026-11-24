import importlib.util
import math
import time
from pathlib import Path

import numpy as np
import pytest

from physverify.checks import EXACT, FAIL, PASS
from physverify.mms import ManufacturedODE, mms_order_study, mms_trajectory_study
from physverify.order import check_order, effective_floor
from physverify.steppers import euler, midpoint, rk4
from physverify.studies import (  # noqa: E402
    close_result,
    coverage_check,
    damped_sinusoid_fit,
    decay_rate,
    patch_study,
    residual_check,
    trajectory_order_study,
)
from pvbench.problems._common import make_integrate


def rhs(t, y):
    return np.array([y[1], -np.sin(y[0]) - 0.1 * y[1] * abs(y[1])])


def integrate_with(stepper, steps_extra=0):
    def integrate(source, y0, t_end, n):
        h = t_end / n
        y = np.array(y0, dtype=float)
        for i in range(n + steps_extra):
            y = stepper(lambda t, s: rhs(t, s) + source(t), i * h, y, h)
        return y

    return integrate


@pytest.mark.parametrize("stepper", [euler, midpoint, rk4])
def test_every_consistent_runge_kutta_method_reproduces_a_linear_solution(stepper):
    result = patch_study(integrate_with(stepper), rhs, [0.3, -0.5], [0.7, 0.4], 1.0, (5, 10, 20, 40))
    assert result.status == EXACT, result.message


def test_patch_catches_an_extra_step_that_keeps_the_order():
    result = patch_study(integrate_with(euler, steps_extra=1), rhs, [0.3, -0.5], [0.7, 0.4], 1.0, (10, 20, 40, 80))
    assert result.status == FAIL
    assert abs(result.fitted - 1.0) < 0.1  # same order as Euler itself


def test_patch_catches_a_wrong_right_hand_side():
    def wrong(t, y):
        return rhs(t, y) * np.array([1.0, 1.01])

    def integrate(source, y0, t_end, n):
        return make_integrate(wrong, frozenset())(source, y0, t_end, n)

    assert patch_study(integrate, rhs, [0.3, -0.5], [0.7, 0.4], 1.0, (10, 20, 40)).status == FAIL


def test_effective_floor_grows_only_for_large_solutions():
    assert effective_floor(1e-12, 1.0) == 1e-12
    assert effective_floor(1e-12, 10.0) == 1e-12
    assert effective_floor(1e-12, 1e6) == pytest.approx(1e-7)
    assert effective_floor(1e-12, float("nan")) == 1e-12


def test_scaled_floor_turns_large_round_off_into_exact():
    hs = [0.1, 0.05, 0.025]
    errs = [3e-9, 2e-9, 3e-9]  # round-off for a solution of size 1e5
    assert check_order(hs, errs, 4.0).status == FAIL
    assert check_order(hs, errs, 4.0, scale=1e5).status == EXACT


def test_trajectory_study_sees_an_error_that_cancels_at_the_end():
    """A code that is wrong in the middle of the run and right at the end."""
    mms = ManufacturedODE(lambda t: np.array([np.sin(t), np.cos(t)]), lambda t, y: np.array([y[1], -y[0]]))
    good = make_integrate(lambda t, y: np.array([y[1], -y[0]]), frozenset(), trajectory=True)

    def bad(source, y0, t_end, n):
        states = good(source, y0, t_end, n)
        states[n // 2] += 1e-3  # a wrong value reported half-way, final state untouched
        return states

    assert mms_trajectory_study(good, mms, 1.0, (10, 20, 40, 80), 4.0).status == PASS
    assert mms_trajectory_study(bad, mms, 1.0, (10, 20, 40, 80), 4.0).status == FAIL


def test_trajectory_study_rejects_the_wrong_number_of_states():
    mms = ManufacturedODE(lambda t: np.array([t]), lambda t, y: np.array([1.0]))
    with pytest.raises(ValueError):
        mms_trajectory_study(lambda s, y0, t, n: np.zeros((n, 1)), mms, 1.0, (4, 8), 1.0)


def test_close_result():
    assert close_result([1.0, 2.0], [1.0, 2.0005], 1e-3).ok
    assert not close_result([1.0, 2.1], [1.0, 2.0], 1e-3).ok
    assert not close_result([np.nan], [1.0], 1e-3).ok


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


def _slow_study(delay):
    mms = ManufacturedODE(lambda t: np.array([np.sin(t)]), lambda t, y: np.array([0.0]))

    def integrate(src, y0, t_end, n):  # RK4 on y' = src(t)
        time.sleep(delay * n / 8)
        y, h = np.array(y0, float), t_end / n
        for k in range(n):
            t = k * h
            y = y + h / 6 * (np.asarray(src(t)) + 4 * np.asarray(src(t + h / 2)) + np.asarray(src(t + h)))
        return y

    return lambda: mms_order_study(integrate, mms, 1.0, [8, 16, 32, 64, 128], 4)


def _euler_runs(ns, t_end, short_by=0):
    runs = []
    for n in ns:
        h = t_end / n
        steps = n - short_by
        t = np.arange(steps + 1) * h
        y = np.empty(steps + 1)
        y[0] = 1.0
        for k in range(steps):
            y[k + 1] = y[k] * (1 - h)
        runs.append((t, y))
    return runs


def _gauss_mean(sigma_used):
    def simulate(mu, rng):
        return rng.normal(mu, 1.0, size=10)

    def interval(x, level):
        z = {0.68: 0.994457883, 0.95: 1.959963985}[level]
        half = z * sigma_used / math.sqrt(len(x))
        return x.mean() - half, x.mean() + half

    return simulate, interval


def test_damped_sinusoid_fit_recovers_frequency_and_damping_after_a_pulse():
    t = np.arange(0, 200, 0.3)
    w0 = 0.4836 - 0.0968j
    y = np.exp(-0.0968 * (t - 50)) * np.cos(0.4836 * t + 0.3) * (t > 50) + 5 * np.exp(-((t - 40) / 4) ** 2)
    w = damped_sinusoid_fit(t, y, 70, 140)
    assert abs(w - w0) < 1e-6


def test_decay_rate_skips_the_start_up_transient():
    t = np.linspace(0, 6, 2001)
    y = np.exp(-0.7 * t) + 30.0 * np.exp(-3.0 * t)  # a large, fast transient on top of the slow mode
    naive = -np.polyfit(t, np.log(y), 1)[0]
    gamma, t0 = decay_rate(t, y)
    assert abs(naive - 0.7) > 0.3 and abs(gamma - 0.7) < 0.7 * 0.05 and t0 > 0  # accurate to about steady_tol
    g_tight, t_tight = decay_rate(t, y, steady_tol=0.005, windows=12)
    assert abs(g_tight - 0.7) < 0.7 * 0.005 and t_tight > t0
    g2, _ = decay_rate(t, y, t_skip=5.0)
    assert abs(g2 - 0.7) < 1e-3
    with pytest.raises(ValueError):
        decay_rate(t, np.exp(-0.1 * t**2))  # rate keeps growing: no steady stretch


def test_residual_check_catches_a_solver_that_does_not_iterate():
    rng = np.random.default_rng(1)
    n = 30
    A = np.diag(np.full(n, 4.0)) + np.diag(np.full(n - 1, -1.0), 1) + np.diag(np.full(n - 1, -1.0), -1)
    b = rng.normal(size=n)
    D = np.diag(A)

    def jacobi(tol, max_sweeps=10000):
        x = np.zeros(n)
        for _ in range(max_sweeps):
            x = (b - (A @ x - D * x)) / D
            if np.linalg.norm(b - A @ x) <= tol:
                break
        return x

    def one_sweep(tol):  # the real bug: a single sweep whatever the tolerance
        return (b - (A @ np.zeros(n) - 0.0)) / D

    res = lambda x: np.linalg.norm(b - A @ x)  # noqa: E731
    assert residual_check(jacobi, res).status == PASS
    r = residual_check(one_sweep, res, label="pressure solve")
    assert r.status == FAIL and "hardly changes" in r.message


def test_trajectory_study_measures_order_at_a_fixed_time():
    r = trajectory_order_study(_euler_runs([20, 40, 80, 160], 2.0), lambda t: math.exp(-t), 2.0, 1)
    assert r.status == PASS


def test_trajectory_study_flags_a_run_that_stops_one_step_short():
    r = trajectory_order_study(_euler_runs([20, 40, 80, 160], 2.0, short_by=1), lambda t: math.exp(-t), 2.0, 1)
    assert r.status == FAIL and "1 step(s) short" in r.message


def test_trajectory_study_notes_a_whole_number_of_periods():
    ns = [40, 80, 160, 320]
    runs = []
    for n in ns:
        h = 2 * math.pi / n
        t = np.arange(n + 1) * h
        q = np.cos(t + 0.3 * h * h * t)  # phase error O(h^2) at all times
        runs.append((t, q))
    r = trajectory_order_study(runs, math.cos, 2 * math.pi, 2, period=2 * math.pi)
    assert "whole period" in r.message


def test_coverage_of_a_correct_interval_passes():
    sim, iv = _gauss_mean(1.0)
    assert coverage_check(sim, iv, lambda rng: rng.uniform(-5, 5), level=0.68, trials=600).status == PASS


def test_coverage_of_an_overconfident_interval_fails():
    sim, iv = _gauss_mean(0.6)  # interval too narrow by the factor 0.6
    r = coverage_check(sim, iv, lambda rng: rng.uniform(-5, 5), level=0.68, trials=600)
    assert r.status == FAIL and "stated 0.68" in r.message
