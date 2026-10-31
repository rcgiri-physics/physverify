"""Roadmap items done for 0.7.0: real tableaux, symplecticity, order uncertainty, independent references."""

import textwrap

import numpy as np
import pytest

from physverify.butcher import TABLES, check_tableau, compare_tableau, square_tableau, symplectic_residual
from physverify.order import fit_order_error, gci
from physverify.specscan import reference_notes


def test_published_tables_and_their_embedded_orders():
    for name, t in TABLES.items():
        r = check_tableau(t["A"], t["b"], t["c"], claimed=t["order"], embedded=t.get("embedded"),
                          claimed_embedded=t.get("embedded_order"), label=name)
        assert r.ok, r.message


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


def test_reference_that_uses_the_solver_is_noted(tmp_path):
    spec = tmp_path / "verify_x.py"
    spec.write_text(textwrap.dedent('''
        import numpy as np
        import mysolver
        from physverify import Check

        def exact(t):
            return mysolver.run(t, dt=1e-6)

        def analytic(t):
            return np.exp(-t)

        def checks():
            return []
    '''), encoding="utf-8")
    notes = reference_notes(spec)
    assert len(notes) == 1 and "exact()" in notes[0] and "mysolver" in notes[0]
