import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

from physverify.checks import EXACT, FAIL, INCONCLUSIVE, PASS
from physverify.order import (
    check_exact,
    check_order,
    fit_order,
    fit_order_error,
    gci,
    pairwise_orders,
)

HS = [0.1, 0.05, 0.025, 0.0125]


def test_pairwise_and_fit_recover_known_order():
    errs = [3.0 * h**4 for h in HS]
    assert np.allclose(pairwise_orders(HS, errs), 4.0)
    assert abs(fit_order(HS, errs) - 4.0) < 1e-12


def test_correct_order_passes():
    result = check_order(HS, [3.0 * h**4 for h in HS], 4.0)
    assert result.status == PASS and result.ok
    assert abs(result.fitted - 4.0) < 1e-9


def test_order_too_low_fails():
    result = check_order(HS, [0.5 * h for h in HS], 4.0)
    assert result.status == FAIL and "below" in result.message


def test_order_too_high_fails_unless_upper_tolerance_is_widened():
    errs = [3.0 * h**4 for h in HS]
    assert check_order(HS, errs, 2.0).status == FAIL
    assert check_order(HS, errs, 2.0, tol_high=float("inf")).status == PASS


def test_plateau_fails():
    result = check_order(HS, [2e-2, 2e-2, 1.9e-2, 1.9e-2], 4.0)
    assert result.status == FAIL and "does not decrease" in result.message


def test_roundoff_level_errors_are_exact_not_failures():
    result = check_order(HS, [1e-15, 3e-16, 2e-15, 1e-15], 4.0)
    assert result.status == EXACT and result.ok


def test_non_finite_error_fails():
    assert check_order(HS, [1e-3, 1e-4, float("nan"), 1e-6], 4.0).status == FAIL
    assert check_order(HS, [1e-3, 1e-4, float("inf"), 1e-6], 4.0).status == FAIL


def test_single_measurable_point_is_inconclusive():
    errs = [1e-6, 1e-14, 1e-15, 1e-15]
    assert check_order(HS, errs, 4.0).status == INCONCLUSIVE


def test_input_order_does_not_matter():
    errs = [3.0 * h**4 for h in HS]
    result = check_order(HS[::-1], errs[::-1], 4.0)
    assert result.status == PASS


def test_check_exact_accepts_round_off_level_errors():
    result = check_exact(HS, [3e-16, 1e-15, 5e-16, 2e-15])
    assert result.status == EXACT and result.ok


def test_check_exact_rejects_a_small_error_that_converges_at_the_expected_order():
    """An error that shrinks at a perfectly good order is still a failure when the answer should be exact."""
    errs = [3.0 * h for h in HS]  # first order, so check_order(expected=1) would pass it
    assert check_order(HS, errs, 1.0).status == PASS
    result = check_exact(HS, errs)
    assert result.status == FAIL and "exact" in result.message


def test_check_exact_reports_the_order_of_a_failing_error():
    result = check_exact(HS, [3.0 * h for h in HS])
    assert abs(result.fitted - 1.0) < 1e-9 and "order 1.00" in result.message


def test_check_exact_fails_on_non_finite_error():
    assert check_exact(HS, [1e-15, float("nan"), 1e-15, 1e-15]).status == FAIL


def test_only_points_above_the_floor_are_fitted():
    hs = [0.2, 0.1, 0.05, 0.025, 0.0125]
    errs = [3.0 * h**4 for h in hs]
    errs[-1] = 5e-15  # round-off: must not drag the fit down
    assert check_order(hs, errs, 4.0).status == PASS


def test_signed_errors_use_their_size():
    """A large negative error is not round-off (it used to give EXACT, which counts as a pass)."""
    assert check_order([0.1, 0.05, 0.025], [-1.0, -2.0, -4.0], 2.0).status == FAIL
    signed = check_order([0.1, 0.05, 0.025], [-1e-2, 2.5e-3, -6.25e-4], 2.0)
    assert signed.status == PASS
    assert abs(signed.fitted - 2.0) < 1e-9
    assert check_exact([0.1, 0.05], [-1.0, -1.0]).status == FAIL


@pytest.mark.parametrize("ratio", [1.05, 1.1, 1.3, 1.5, 2.0, 3.0, 4.0])
@pytest.mark.parametrize("p", [1.0, 2.0, 4.0])
def test_correct_order_passes_at_any_refinement_ratio(ratio, p):
    hs = [0.1 / ratio**i for i in range(5)]
    assert check_order(hs, [0.3 * h**p for h in hs], p).status == PASS


@pytest.mark.parametrize("ratio", [1.05, 1.1, 2.0])
def test_plateau_fails_at_any_refinement_ratio(ratio):
    hs = [0.1 / ratio**i for i in range(5)]
    assert check_order(hs, [2e-2] * 5, 2.0).status == FAIL


def test_gci_flags_change_that_does_not_shrink():
    for fine, medium, coarse in [(1.0, 1.1, 1.101), (1.0, 1.1, 1.2)]:
        g = gci(fine, medium, coarse, 2.0)
        assert g["not_converging"]
        assert math.isnan(g["order"]) and math.isnan(g["gci_fine"])
    assert not gci(1.01, 1.04, 1.16, 2.0)["not_converging"]


# issue #8: a PASS should say when it rests on little data


def test_pass_from_two_step_sizes_says_so():
    r = check_order([0.1, 0.05], [1e-2, 2.5e-3], expected=2)
    assert r.status == PASS and "two step sizes" in r.message and math.isnan(r.fitted_se)


def test_repeated_step_sizes_are_not_counted_as_evidence():
    r = check_order([0.1, 0.1, 0.05, 0.05], [1e-2, 1e-2, 2.5e-3, 2.5e-3], expected=2)
    assert r.status == PASS and "only 2 distinct step sizes" in r.message


def test_wide_standard_error_is_reported():
    errs = [h**2 * f for h, f in zip(HS, [1.0, 2.2, 0.6, 1.5])]
    r = check_order(HS, errs, expected=2)
    assert r.status == PASS and r.fitted_se > 0.3 and "standard error" in r.message


def test_clean_pass_gives_small_standard_error_and_no_warning():
    r = check_order(HS, [3.0 * h**4 for h in HS], expected=4)
    assert r.status == PASS and r.fitted_se < 1e-10 and r.message == "observed order 4.00 (expected 4)"


def test_exact_warns_about_self_made_references():
    r = check_order(HS, [0.0] * 4, expected=2)
    assert r.status == EXACT and "computed by the code under test" in r.message


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


def test_check_order_tol_alias_and_round_off_hints():
    hs = [0.1, 0.05, 0.025, 0.0125]
    errs = [h**2 for h in hs]
    assert check_order(hs, errs, 2.6, tol=0.7).status == PASS
    assert check_order(hs, errs, 2.6, tol=0.1).status == FAIL
    r = check_order([0.1, 0.05, 0.025], [3e-12, 5e-13, 4e-13], 4)
    assert r.status == INCONCLUSIVE and "coarser" in r.message
    r = check_order([0.1, 0.05, 0.025], [2e-11, 2.1e-11, 2.05e-11], 4)
    assert r.status == FAIL and "round-off" in r.message


def test_check_order_reports_an_accuracy_only_failure():
    hs = np.array([0.1, 0.05, 0.025, 0.0125])
    errs = 3.0 * hs**2
    assert check_order(hs, errs, 2).status == PASS
    r = check_order(hs, errs, 2, atol=1e-4)
    assert r.status == FAIL and "only the accuracy requirement fails" in r.message
    assert "2.2 times smaller steps" in r.message  # finest error 4.69e-4, order 2: sqrt(4.69)
    assert check_order(hs, errs, 2, atol=1e-3).status == PASS
    bad = check_order(hs, 3.0 * hs, 2, atol=1e-4)
    assert bad.status == FAIL and "below the expected" in bad.message and "also above" in bad.message


def test_order_with_standard_error_and_gci():
    hs = np.array([0.1, 0.05, 0.025, 0.0125])
    p, se = fit_order_error(hs, 3.0 * hs ** 2)
    assert abs(p - 2) < 1e-12 and se < 1e-10
    noisy = 3.0 * hs ** 2 * np.array([1.0, 1.3, 0.8, 1.2])
    p, se = fit_order_error(hs, noisy)
    assert se > 0.05
    # f(h) = 1 + h^2 on h = 0.1, 0.2, 0.4: p = 2, extrapolate 1
    g = gci(1.01, 1.04, 1.16, 2.0)
    assert abs(g["order"] - 2) < 1e-12 and abs(g["extrapolated"] - 1.0) < 1e-12
    assert abs(g["gci_fine"] - 1.25 * 0.03 / 1.01 / 3) < 1e-12
    assert gci(1.0, 1.1, 1.05, 2.0)["oscillatory"]
