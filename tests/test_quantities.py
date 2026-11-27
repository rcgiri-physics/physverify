"""compare_quantities: units are checked when pint is installed; bare numbers work without it."""

import numpy as np
import pytest

from physverify.quantities import compare_quantities


def test_bare_numbers():
    assert compare_quantities(1.0 + 1e-10, 1.0).status == "PASS"
    assert compare_quantities([1.0, 2.0], [1.0, 2.1], rtol=1e-3).status == "FAIL"
    assert compare_quantities([1.0, np.nan], [1.0, 1.0]).status == "FAIL"


pint = pytest.importorskip("pint")
ureg = pint.UnitRegistry()


def test_converts_before_comparing():
    r = compare_quantities(1.5 * ureg.km, 1500.0 * ureg.m)
    assert r.status == "PASS" and "compared in m" in r.message


def test_different_dimensions_fail():
    r = compare_quantities(2.0 * ureg.J, 2.0 * ureg.W)
    assert r.status == "FAIL" and "different dimensions" in r.message


def test_units_on_one_side_fail():
    assert "bare number" in compare_quantities(3.0 * ureg.m, 3.0).message
    assert compare_quantities(3.0, 3.0 * ureg.m).status == "FAIL"


def test_atol_with_units():
    assert compare_quantities(1.0001 * ureg.m, 1.0 * ureg.m, rtol=0, atol=1 * ureg.mm).status == "PASS"
    assert compare_quantities(1.0 * ureg.m, 1.0 * ureg.m, atol=1 * ureg.s).status == "FAIL"


def test_arrays():
    v = np.array([1.0, 2.0]) * ureg.cm
    assert compare_quantities(v, np.array([0.01, 0.02]) * ureg.m).status == "PASS"
