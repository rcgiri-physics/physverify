"""Checks added after testing other people's repositories (sandbox/README.md).

Each test reproduces, in a few lines, the pattern a real code had, and shows the new check sees it.
"""

import numpy as np

from physverify.checks import FAIL, PASS
from physverify.constants import check_value, scan
from physverify.loaders import load_definitions_from_path
from physverify.mms import ManufacturedODE
from physverify.order import check_order
from physverify.steppers import rk4
from physverify.studies import backward_mms_study, time_grid_check


def while_loop_times(t0, t1, n):
    """`while t <= t_end: t += h`, as in a real RK4 library."""
    h = (t1 - t0) / n
    t, times = t0, [t0]
    while t <= t1:
        t += h
        times.append(t)
    return times


def counted_times(t0, t1, n):
    h = (t1 - t0) / n
    return [t0 + i * h for i in range(n + 1)]


def test_time_grid_check_catches_the_extra_step_only_for_exact_binary_steps():
    bad = time_grid_check(lambda n: while_loop_times(0.0, 2.0, n), 0.0, 2.0, (4, 8, 20))
    assert bad.status == FAIL
    assert "h=0.5" in bad.message and "h=0.25" in bad.message and "h=0.1:" not in bad.message
    assert time_grid_check(lambda n: counted_times(0.0, 2.0, n), 0.0, 2.0, (4, 8, 20)).status == PASS


def test_time_grid_check_reports_empty_and_nonfinite_times():
    empty = time_grid_check(lambda n: [], 0.0, 1.0, (2,))
    assert empty.status == FAIL and "no times" in empty.message
    for times in ([0.0, 0.5, np.nan], [0.0, np.inf, 1.0]):
        invalid = time_grid_check(lambda n, times=times: times, 0.0, 1.0, (2,))
        assert invalid.status == FAIL and "non-finite" in invalid.message


def test_time_grid_check_accepts_a_column_of_times():
    assert time_grid_check(lambda n: np.linspace(0.0, 1.0, n + 1)[:, None], 0.0, 1.0, (4, 8)).status == PASS


MMS = ManufacturedODE(lambda t: np.array([np.exp(np.sin(t))]), lambda t, y: np.array([y[0] * np.cos(t)]))


def backward(stage_time_sign):
    """RK4 from t_end down to 0; stage_time_sign = +1 reproduces the bug (stages at t + h/2 while stepping back)."""
    def integrate_back(source, y_end, t_end, n):
        h = t_end / n
        y, t = np.array(y_end, dtype=float), t_end
        g = lambda s, u: -(MMS.rhs_ref(s, u) + source(s))  # dy/d(-t)
        for _ in range(n):
            if stage_time_sign > 0:
                y = rk4(g, t, y, h)
            else:
                y = rk4(lambda s, u: g(-s, u), -t, y, h)
            t -= h
        return y
    return integrate_back


def test_backward_study_separates_wrong_stage_times():
    ns = (10, 20, 40, 80)
    assert backward_mms_study(backward(-1), MMS, 2.0, ns, 4).status == PASS
    bad = backward_mms_study(backward(+1), MMS, 2.0, ns, 4)
    assert bad.status == FAIL and bad.fitted < 1.5


def test_order_check_says_when_the_steps_are_too_coarse():
    hs = np.array([0.04, 0.02, 0.01, 0.005])
    errs = hs**4 / (1 + 40 * hs)  # pre-asymptotic: pairwise orders 3.47, 3.64, 3.78, climbing toward 4
    r = check_order(hs, errs, 4.0)
    assert r.status == FAIL and "pre-asymptotic" in r.message
    assert "pre-asymptotic" not in check_order(hs, hs**2, 4.0).message


def test_constant_near_misses(tmp_path):
    assert check_value(3.14)[0] == "pi" and check_value(3.1416) is None
    assert check_value(39.47692640889762)[0].startswith("G M_sun") and check_value(4 * np.pi**2) is None
    assert check_value(9.81) is None and check_value(6.674e-11) is None
    src = tmp_path / "game.py"
    src.write_text("g = 9\nn = 10\nU = 110\nG = 39.47692640889762\nx = 3.14 * 2\n")
    names = [n.constant for n in scan(src)]
    assert names == ["g", "G M_sun / 4 pi^2 (au, yr)", "pi"]


def test_load_definitions_skips_the_script_body(tmp_path):
    src = tmp_path / "sim.py"
    src.write_text(
        "import math\nimport argparse\nargs = argparse.ArgumentParser().parse_args(['--bogus'])\n"
        "J = 2.0\nraise SystemExit('the simulation ran')\n"
        "def energy(s):\n    return -J * s * math.cos(0)\n"
        "def cell():\n    def inner(x):\n        return x + 1\n    return inner\n"
    )
    mod = load_definitions_from_path("sim_defs", src, keep=("J",), inner=("inner",))
    assert mod.energy(3.0) == -6.0 and mod.inner(1) == 2


def test_butcher_order_conditions():
    from physverify.butcher import check_tableau, tableau_order, trees

    assert [len(trees(n)) for n in range(1, 8)] == [1, 1, 2, 4, 9, 20, 48]
    A = np.array([[0, 0, 0, 0], [0.5, 0, 0, 0], [0, 0.5, 0, 0], [0, 0, 1, 0]])
    b = np.array([1 / 6, 1 / 3, 1 / 3, 1 / 6])
    assert tableau_order(A, b) == 4
    assert check_tableau(A, b, [0, 0.5, 0.5, 1], claimed=4).status == PASS
    # a real case: an order-3 table labelled as order 4
    bad = check_tableau(A, b, claimed=5)
    assert bad.status == FAIL and "only up to 4" in bad.message
    s = np.sqrt(15)
    gauss3 = np.array([[5 / 36, 2 / 9 - s / 15, 5 / 36 - s / 30], [5 / 36 + s / 24, 2 / 9, 5 / 36 - s / 24],
                       [5 / 36 + s / 30, 2 / 9 + s / 15, 5 / 36]])
    assert tableau_order(gauss3, [5 / 18, 4 / 9, 5 / 18], max_order=7) == 6  # implicit tables work too
    # coefficients typed with few digits are noted
    rough = check_tableau(np.round(gauss3, 8), [5 / 18, 4 / 9, 5 / 18], claimed=6, tol=1e-6)
    assert rough.status == PASS and "limited digits" in rough.message


def test_order_check_flags_non_monotone_errors():
    hs = np.array([0.1, 0.05, 0.025, 0.0125])
    errs = np.array([1e-6, 1e-8, 2e-8, 1e-8])  # leading term changes sign between the second and third
    r = check_order(hs, errs, 4.0, floor=1e-14)
    assert r.status == FAIL and "not monotone" in r.message


def test_order_check_explains_a_step_independent_error():
    hs = np.array([0.004, 0.002, 0.001, 0.0005])
    r = check_order(hs, np.array([0.0164, 0.0164, 0.0163, 0.0163]), 2.0)  # the MD cutoff-crossing case
    assert r.status == FAIL and "independent of the step" in r.message


def test_size_sweep_finds_a_crash_at_odd_sizes():
    from physverify.studies import size_sweep_check

    def halves(n):  # the pattern of a real spectral code
        k = np.arange(float(n))
        k[int(n / 2):] = k[: int(n / 2)] - 1.0
        return True

    r = size_sweep_check(halves)
    assert r.status == FAIL and "n=15" in r.message and "n=16" not in r.message
    assert size_sweep_check(lambda n: np.fft.fftfreq(n).size == n).status == PASS


def test_load_definitions_stubs_missing_imports(tmp_path):
    src = tmp_path / "sim.py"
    src.write_text("import not_installed_plotting_pkg\nimport math\ndef f(x):\n    return math.sqrt(x)\n")
    mod = load_definitions_from_path("sim_stub", src, stubs=("not_installed_plotting_pkg",))
    assert mod.f(4.0) == 2.0


def test_balance_check_catches_a_converging_but_non_conservative_scheme():
    from physverify.studies import balance_check

    # a budget that is wrong by 1/n: converges, never conserves (the heat-loss pattern of a real code)
    r = balance_check(lambda n: 1.0 / n, 0.0, (10, 20, 40), tol=1e-12)
    assert r.status == FAIL and "converges but does not conserve" in r.message
    # exact at every resolution
    assert balance_check(lambda n: 2.0, 2.0, (10, 100)).status == PASS
    # wrong and growing with n (a source added without dt): FAIL without the converging hint
    r = balance_check(lambda n: 2.0 * n, 2.0, (10, 100))
    assert r.status == FAIL and "converges" not in r.message


def test_stub_modules_provide_names_and_keep_decorated_functions():
    import sys

    from physverify.loaders import Placeholder, stub_modules

    names = stub_modules({"no_such_pkg_xyz.metrics": ["score"], "no_such_web_xyz": ["Flask"]})
    try:
        import no_such_web_xyz
        from no_such_pkg_xyz.metrics import score  # noqa: F401  (a parent package is created too)

        app = no_such_web_xyz.Flask(__name__)

        @app.route("/x", methods=["POST"])
        def view():
            return 42

        assert view() == 42 and isinstance(score, Placeholder)
        assert stub_modules(["math"]) == []  # a module that imports for real is left alone
    finally:
        for n in names:
            sys.modules.pop(n, None)


def test_run_script_returns_globals_and_output(tmp_path):
    from physverify.loaders import run_script

    src = tmp_path / "demo.py"
    src.write_text("import sys\nx = 6 * 7\nprint('hello', sys.argv[1:])\n")
    g, out = run_script(src, argv=["a"])
    assert g["x"] == 42 and "hello ['a']" in out
