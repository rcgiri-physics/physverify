import numpy as np

from physverify.checks import FAIL, INCONCLUSIVE, PASS
from physverify.longtime import check_energy_drift


def _pendulum(method, h=0.1, T=2000.0):
    """Energy of the pendulum q'' = -sin q from q = 1 at rest, sampled every step."""
    n = int(T / h)
    q, p = 1.0, 0.0
    E = np.empty(n + 1)
    E[0] = -np.cos(q)
    for i in range(n):
        if method == "leapfrog":
            p -= 0.5 * h * np.sin(q)
            q += h * p
            p -= 0.5 * h * np.sin(q)
        else:  # explicit midpoint (RK2), not symplectic
            qm, pm = q + 0.5 * h * p, p - 0.5 * h * np.sin(q)
            q, p = q + h * pm, p - h * np.sin(qm)
        E[i + 1] = 0.5 * p * p - np.cos(q)
    return np.arange(n + 1) * h, E


def test_leapfrog_bounded_rk2_drifts():
    t, E = _pendulum("leapfrog")
    r = check_energy_drift(t, E)
    assert r.status == PASS and "bounded" in r.message, r.message
    t, E = _pendulum("rk2")
    r = check_energy_drift(t, E)
    assert r.status == FAIL and "secular drift" in r.message, r.message
    assert check_energy_drift(t, E, expect="drift").status == PASS


def test_round_off_and_random_walk():
    t = np.linspace(0, 1000, 200001)
    assert check_energy_drift(t, np.full(t.size, 3.0)).status == PASS  # exactly conserved
    # a random walk (round-off accumulating) has k near 1/2: neither verdict (0 of 1000 seeds gave one)
    for seed in range(20):
        walk = 1.0 + 1e-9 * np.cumsum(np.random.default_rng(seed).standard_normal(t.size))
        assert check_energy_drift(t, walk).status == INCONCLUSIVE


def test_review_edge_cases():
    t = np.linspace(0, 1000, 20001)
    r = check_energy_drift(t, 0.5 * np.exp(-t / 5))  # decays and levels off: k near 0, but all energy is gone
    assert r.status == FAIL and "not conserved" in r.message, r.message
    q = 1 + 1e-6 * np.cos(t)
    q[10000:] = np.nan
    r = check_energy_drift(t, q)
    assert r.status == FAIL and "not finite from t = 500" in r.message
    q = np.ones_like(t)
    q[-1] = np.inf
    assert check_energy_drift(t, q).status == FAIL
    assert check_energy_drift(t[:5], np.arange(5.0)).status == INCONCLUSIVE
    p = 1e-15 * np.sin(t)  # a total momentum: zero up to round-off
    assert "pass qscale" in check_energy_drift(t, p).message
    assert check_energy_drift(t, p, qscale=1.0).status == PASS
