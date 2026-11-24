"""Scan stage "flow" (issue 46): each rule fires on the bug and stays quiet on the nearest correct code."""

import ast
import textwrap

from physverify.stages.flow import scan_flow


def flow(src):
    src = textwrap.dedent(src)
    return [f for f in scan_flow(None, ast.parse(src), "m.py")]


def test_unbound_after_if():
    hits = flow("""
        def rho(plane, q):
            if plane == "xz":
                dens = q * 2
            return dens
    """)
    assert len(hits) == 1 and "'dens'" in hits[0].message and hits[0].level == "NOTE"


def test_unbound_quiet_cases():
    assert not flow("""
        def f(a):
            if a:
                x = 1
            else:
                x = 2
            return x
    """)
    assert not flow("""
        def f(a):
            if a:
                x = 1
            elif a is None:
                x = 3
            else:
                raise ValueError
            return x
    """)
    assert not flow("""
        def f(a):
            x = 0
            if a:
                x = 1
            return x
    """)
    assert not flow("""
        def f(a):
            if not a:
                return 0
            y = 1
            return y
    """)
    assert not flow("""
        def f(a):
            if a:
                x = 1
            x = 5
            return x
    """)


def test_predictor_alias():
    hits = flow("""
        import numpy as np
        def rk2(u, dt, f):
            u_old = np.array(u)
            u_mid = u_old
            u_mid += 0.5 * dt * f(u_old)
            return u_old + dt * f(u_mid)
    """)
    assert len(hits) == 1 and "copy" in hits[0].message
    hits = flow("""
        def step(u, k):
            v = u
            v[1:] = v[1:] + k
            return u
    """)
    assert len(hits) == 1


def test_alias_quiet_cases():
    assert not flow("""
        def step(u, k):
            v = u.copy()
            v[1:] += k
            return u
    """)
    assert not flow("""
        def step(n):
            m = n
            m += 1
            return n
    """)  # integers: += rebinds, no alias
    assert not flow("""
        def step(u, k):
            v = u
            v[1:] += k
            return v
    """)


def test_spacing_mismatch():
    hits = flow("""
        def coeffs(DXe, DXw, DXp, u):
            ue = u / (DXp + DXe)
            uw = u / (DXp + DXe)
            return ue, uw
    """)
    assert len(hits) == 1 and "'uw'" in hits[0].message
    assert not flow("""
        def coeffs(DXe, DXw, DXp, u):
            ue = u / (DXp + DXe)
            uw = u / (DXp + DXw)
            return ue, uw
    """)
    assert not flow("""
        def coeffs(DXe, u):
            uw = u / DXe
            return uw
    """)  # no west spacing at all: a uniform grid by design


def test_numba_eager_scipy():
    src = """
        import numba
        from scipy import special
        @numba.jit("f8(f8)", nopython=True)
        def g(x):
            return special.erf(x)
    """
    assert len(flow(src)) == 1
    assert not flow(src.replace('"f8(f8)", ', ""))
    assert not flow(src.replace("special.erf(x)", "x * x"))


def test_factorial2_and_steps():
    hits = flow("""
        from scipy.special import factorial2
        def norm(n):
            return 1 / factorial2(2 * n - 1)
        nt = int(tmax / dt)
        ok = int(round(tmax / dt))
        other = int(a / b)
    """)
    assert sorted(h.message.split("(")[0] for h in hits) == ["factorial2", "int"]
    assert all(h.level == "NOTE" for h in hits)
