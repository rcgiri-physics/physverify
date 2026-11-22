"""Property-based checks of check_order (need Hypothesis).

Errors that follow C h^p exactly must give order p and PASS for any refinement ratio above 1, any C, either
sign and any order of the inputs; errors that stop shrinking must FAIL. The 0.9.1 review found bugs in exactly
these cases (signed errors, unsorted inputs), so the properties are stated here once for all of them.
"""

import numpy as np
import pytest

from physverify.checks import FAIL, PASS
from physverify.order import check_order, fit_order_error

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import assume, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402


@st.composite
def power_law(draw):
    """(hs, errors, p): errors = C h^p (each with a random sign), shuffled, all well above the noise floor."""
    p = draw(st.floats(0.5, 6.0))
    ratio = draw(st.floats(1.1, 4.0))
    n = draw(st.integers(3, 6))
    h0 = draw(st.floats(1e-3, 1.0))
    c = draw(st.floats(1e-3, 1e3))
    hs = h0 / ratio ** np.arange(n)
    errs = c * hs ** p
    assume(errs.min() > 1e-8 and errs.max() < 1e100)  # clear of the noise floor and of overflow
    signs = np.array(draw(st.lists(st.sampled_from([-1.0, 1.0]), min_size=n, max_size=n)))
    perm = np.array(draw(st.permutations(range(n))))
    return hs[perm], (signs * errs)[perm], p


@settings(max_examples=200, deadline=None)
@given(power_law())
def test_exact_power_law_passes_at_its_order(data):
    hs, errs, p = data
    r = check_order(hs, errs, expected=p)
    assert r.status == PASS, r.message
    assert abs(r.fitted - p) < 1e-6


@settings(max_examples=200, deadline=None)
@given(power_law())
def test_fit_recovers_the_order_with_zero_standard_error(data):
    hs, errs, p = data
    fitted, se = fit_order_error(hs, np.abs(errs))
    assert abs(fitted - p) < 1e-6 and se < 1e-6


@settings(max_examples=200, deadline=None)
@given(power_law())
def test_power_law_fails_when_a_different_order_is_claimed(data):
    hs, errs, p = data
    assert check_order(hs, errs, expected=p + 1.5).status == FAIL
    if p - 1.5 > 0:
        assert check_order(hs, errs, expected=p - 1.5).status == FAIL


@settings(max_examples=200, deadline=None)
@given(power_law(), st.floats(1e-6, 1e3))
def test_constant_error_fails(data, level):
    hs, errs, p = data
    flat = np.sign(errs) * level
    assert check_order(hs, flat, expected=p).status == FAIL


@settings(max_examples=200, deadline=None)
@given(power_law())
def test_plateau_at_the_finest_resolutions_fails(data):
    """A constant error 100 times the second-finest power-law error swamps the last two resolutions."""
    hs, errs, p = data
    second_finest = np.sort(np.abs(errs))[1]
    plateaued = np.sign(errs) * (np.abs(errs) + 100 * second_finest)
    r = check_order(hs, plateaued, expected=p)
    assert r.status == FAIL, r.message
