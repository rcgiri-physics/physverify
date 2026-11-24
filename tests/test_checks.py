"""The check runner: skips, budgets, hanging checks and optional dependencies."""

import importlib.util
import math
import time
from pathlib import Path

import numpy as np

from physverify.checks import (
    ERROR,
    INCONCLUSIVE,
    PASS,
    SKIP,
    Check,
    Result,
    SkipCheck,
    requires,
    run_check,
)
from physverify.cli import main
from physverify.mms import ManufacturedODE, mms_order_study
from physverify.report import run_checks, summary

ROOT = Path(__file__).resolve().parents[1]


def _runner():
    spec = importlib.util.spec_from_file_location("pv_runner", ROOT / "sandbox" / "runner.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


def test_missing_optional_dependency_is_skip_not_pass():
    def needs_missing():
        requires("numpy", "no_such_module_pv")
        return Result(PASS, "ran")

    r = run_check(Check("limit", "needs shapely", needs_missing))
    assert r.status == SKIP and "no_such_module_pv" in r.message
    assert not r.ok and not r.failed


def test_skip_counts_separately_and_does_not_fail_the_run(tmp_path):
    spec = tmp_path / "verify_skip.py"
    spec.write_text(
        "from physverify import Check, Result, SkipCheck\n"
        "def skipped():\n    raise SkipCheck('no GPU')\n"
        "def checks():\n    return [Check('limit', 'ok', lambda: Result('PASS', '')), Check('limit', 'gpu', skipped)]\n")
    outs = run_checks([Check("limit", "s", lambda: (_ for _ in ()).throw(SkipCheck("x")))])
    assert summary(outs)["skipped"] == 1 and summary(outs)["not_ok"] == 0
    assert main(["run", "--quiet", str(spec)]) == 0


def test_budget_stops_adding_resolutions_and_says_so():
    r = run_check(Check("mms", "slow", _slow_study(0.05)), budget_s=0.5)
    assert "time budget: ran" in r.message
    assert len(r.hs) < 5
    assert run_check(Check("mms", "fast", _slow_study(0.0)), budget_s=30).status == PASS


def test_a_check_that_hangs_is_inconclusive_and_later_checks_run():
    hang = Check("limit", "hang", lambda: (time.sleep(5), Result(PASS))[1], budget_s=0.2)
    outs = run_checks([hang, Check("limit", "next", lambda: Result(PASS, ""))])
    assert outs[0].result.status == INCONCLUSIVE and outs[0].seconds < 2
    assert outs[1].result.status == PASS


def test_budget_keeps_errors_and_skips():
    assert run_check(Check("limit", "e", lambda: 1 / 0), budget_s=5).status == ERROR
    assert run_check(Check("limit", "s", lambda: requires("no_such_module_pv")), budget_s=5).status == SKIP
