"""Butcher tables: published tables, embedded orders, rounded coefficients, symplecticity."""

import numpy as np
import pytest

from physverify.butcher import (
    TABLES,
    check_tableau,
    compare_tableau,
    square_tableau,
    symplectic_residual,
)
from physverify.checks import FAIL


def test_check_tableau_points_at_rounded_coefficients():
    A = [[0, 0, 0, 0], [0.5, 0, 0, 0], [0, 0.5, 0, 0], [0, 0, 1, 0]]
    b = [0.166667, 0.333333, 0.333333, 0.166667]  # classical RK4 typed with 6 digits
    r = check_tableau(A, b, claimed=4)
    assert r.status == FAIL and "too few digits" in r.message


def test_published_tables_and_their_embedded_orders():
    for name, t in TABLES.items():
        r = check_tableau(t["A"], t["b"], t["c"], claimed=t["order"], embedded=t.get("embedded"),
                          claimed_embedded=t.get("embedded_order"), label=name)
        assert r.ok, r.message


def test_compare_tableau_rejects_nonfinite_weights():
    rk4 = TABLES["rk4"]
    weights = np.array(rk4["b"])
    weights[0] = np.nan
    result = compare_tableau(rk4["A"], weights, "rk4")
    assert result.status == FAIL and "non-finite" in result.message


def test_scipy_tables_when_available():
    integrate = pytest.importorskip("scipy.integrate")
    for cls, order, emb in ((integrate.RK23, 3, 2), (integrate.RK45, 5, 4)):
        A, B, C, E = cls.A, cls.B, cls.C, cls.E
        # SciPy stores error weights E (difference of the two weight vectors, sign by convention) over the
        # stages plus the FSAL stage; one sign gives the embedded method
        b_full = np.append(B, 0.0)
        rs = [check_tableau(A, B, C, claimed=order, embedded=b_full + s * E, claimed_embedded=emb) for s in (1, -1)]
        assert any(r.ok for r in rs), rs[0].message
    assert compare_tableau(integrate.RK45.A, integrate.RK45.B, "dormand_prince_5_4").ok


def test_fsal_shape_is_padded_and_a_wrong_embedded_claim_fails():
    t = TABLES["dormand_prince_5_4"]
    A = np.array(t["A"])[:, :-1]  # stored without the zero last column
    assert square_tableau(A, t["b"])[0].shape == (7, 7)
    r = check_tableau(A, t["b"], claimed=5, embedded=t["embedded"], claimed_embedded=5)
    assert not r.ok and "embedded order 5" in r.message
    bad = np.array(t["embedded"]); bad[0] += 1e-3
    assert "sum to" in check_tableau(A, t["b"], claimed=5, embedded=bad).message
    A2 = np.array(t["A"]); A2[4, 2] *= 1.001
    assert "A[4][2]" in compare_tableau(A2, t["b"], "dormand_prince_5_4").message


def test_symplectic_gauss_but_not_rk4():
    g, rk4 = TABLES["gauss_legendre_4"], TABLES["rk4"]
    assert symplectic_residual(g["A"], g["b"]) < 1e-14
    assert check_tableau(g["A"], g["b"], claimed=4, symplectic=True).ok
    r = check_tableau(rk4["A"], rk4["b"], claimed=4, symplectic=True)
    assert not r.ok and "symplectic" in r.message
