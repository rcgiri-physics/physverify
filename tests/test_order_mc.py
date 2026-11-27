"""check_order_mc: synthetic noise with a known order, and geometric Brownian motion with an exact solution."""

import numpy as np
import pytest

from physverify.order import _normal_quantile, check_order_mc


def test_normal_quantile():
    from statistics import NormalDist
    for p in (1e-6, 0.005, 0.3, 0.5, 0.995):
        assert abs(_normal_quantile(p) - NormalDist().inv_cdf(p)) < 1e-8


def _rates(true, claim, noise, n_h, runs, seed):
    rng = np.random.default_rng(seed)
    hs = 0.1 / 2.0 ** np.arange(n_h)
    out = {"PASS": 0, "FAIL": 0, "INCONCLUSIVE": 0}
    for _ in range(runs):
        e = np.abs(hs**true * (1 + noise * rng.standard_normal(n_h)))
        out[check_order_mc(hs, e, noise * hs**true, claim).status] += 1
    return out


def test_false_alarms_and_power_on_synthetic_noise():
    assert _rates(1.0, 1.0, 0.1, 4, 2000, 1)["FAIL"] == 0
    edge = _rates(0.7, 1.0, 0.1, 4, 2000, 2)  # the true order on the edge of the band
    assert edge["FAIL"] <= 20  # 1%; the 99% interval allows 0.5%
    low = _rates(0.5, 1.0, 0.1, 6, 2000, 3)
    assert low["PASS"] == 0 and low["FAIL"] >= 1900


def _gbm_errors(scheme, ns, paths=4000, seed=0, mu=0.5, sigma=0.8, t_end=1.0, x0=1.0):
    """Strong error E|X_N - X(T)| for geometric Brownian motion, with the exact solution from the same path."""
    rng = np.random.default_rng(seed)
    n_fine = max(ns)
    dw_fine = rng.standard_normal((paths, n_fine)) * np.sqrt(t_end / n_fine)
    exact = x0 * np.exp((mu - 0.5 * sigma**2) * t_end + sigma * dw_fine.sum(axis=1))
    hs, errs, ses = [], [], []
    for n in ns:
        dw = dw_fine.reshape(paths, n, n_fine // n).sum(axis=2)
        h = t_end / n
        x = np.full(paths, x0)
        for k in range(n):
            step = mu * x * h + sigma * x * dw[:, k]
            if scheme in ("milstein", "milstein_bug"):
                factor = 0.5 if scheme == "milstein" else 0.25  # bug: half the correction
                step += factor * sigma**2 * x * (dw[:, k] ** 2 - h)
            x = x + step
        d = np.abs(x - exact)
        hs.append(h)
        errs.append(d.mean())
        ses.append(d.std(ddof=1) / np.sqrt(paths))
    return hs, errs, ses


@pytest.mark.parametrize("scheme,order", [("euler", 0.5), ("milstein", 1.0)])
def test_gbm_strong_order(scheme, order):
    hs, e, s = _gbm_errors(scheme, (8, 16, 32, 64, 128, 256))
    r = check_order_mc(hs, e, s, order, tol=0.2)
    assert r.status == "PASS", r.message


def test_gbm_milstein_with_half_the_correction_fails():
    hs, e, s = _gbm_errors("milstein_bug", (8, 16, 32, 64, 128, 256))
    r = check_order_mc(hs, e, s, 1.0, tol=0.2)
    assert r.status == "FAIL", r.message


def test_unusable_input():
    assert check_order_mc([0.1, 0.05], [1, 0.5], [0.1, 0.1], 1).status == "INCONCLUSIVE"
    assert check_order_mc([0.1, 0.05, 0.025], [1, 0.5, 0.0], [0.1, 0.1, 0.1], 1).status == "INCONCLUSIVE"
    assert check_order_mc([0.1, 0.05, 0.025], [1, 0.5, np.nan], [0.1, 0.1, 0.1], 1).status == "FAIL"
    assert check_order_mc([0.1, 0.05, 0.025], [1, 0.5], [0.1, 0.1, 0.1], 1).status == "INCONCLUSIVE"
