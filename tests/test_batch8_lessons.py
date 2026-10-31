"""Helpers added after batch 8 of the corpus study (popular libraries): identity checks, extracting
functions from a file that cannot be imported, and the sandbox's placeholder version files.

Each check is shown catching the kind of bug that was found, and passing on the corrected code."""

import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

from physverify.checks import FAIL, PASS
from physverify.identities import (check_agree, check_derivative, check_identity, check_roundtrip, check_unitary,
                                   fd_derivative, laplacian_fd)
from physverify.loaders import extract_functions

ROOT = Path(__file__).resolve().parents[1]


def _runner():
    spec = importlib.util.spec_from_file_location("pv_runner_b8", ROOT / "sandbox" / "runner.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- round trips: a reference pixel at 1 + n/2 instead of (n + 1)/2 ---

def _pixel_to_sky(p, n, crpix):
    return (p + 1 - crpix) * 2.0  # 0-based pixel to arcsec, FITS reference pixel crpix at 0 arcsec


def test_roundtrip_catches_a_half_pixel_reference():
    n = 20
    centre = (n - 1) / 2  # 0-based centre pixel
    good = check_roundtrip(lambda p: _pixel_to_sky(p, n, (n + 1) / 2), lambda s: s / 2.0 + (n + 1) / 2 - 1, [centre, 0.0, 7.3])
    assert good.status == PASS
    # the buggy copy rebuilds the header with crpix = 1 + n/2, the inverse still uses the original (n + 1)/2
    bad = check_roundtrip(lambda p: _pixel_to_sky(p, n, 1 + n / 2), lambda s: s / 2.0 + (n + 1) / 2 - 1, [centre])
    assert bad.status == FAIL and "0.5" in bad.message


def test_roundtrip_handles_arrays_and_complex():
    rng = np.random.default_rng(0)
    S = (rng.normal(size=(3, 2, 2)) + 1j * rng.normal(size=(3, 2, 2))) * 0.3
    eye = np.eye(2)
    s2z = lambda s: 50 * (eye + s) @ np.linalg.inv(eye - s)  # noqa: E731
    z2s = lambda z: (z / 50 - eye) @ np.linalg.inv(z / 50 + eye)  # noqa: E731
    assert check_roundtrip(s2z, z2s, [S], atol=1e-12).status == PASS


# --- sibling agreement: Eyring's air term with the wrong sign ---

def _sabine(S, V, a, m, c=343.0):
    return 24 * math.log(10) / c * V / (a * S + 4 * m * V)


def _eyring_bug(S, V, a, m, c=343.0):
    return -(24 * math.log(10) / c) * V / (S * math.log(1 - a) + 4 * m * V)


def _eyring(S, V, a, m, c=343.0):
    return -(24 * math.log(10) / c) * V / (S * math.log(1 - a) - 4 * m * V)


def test_agree_catches_the_eyring_air_sign():
    # Eyring -> Sabine as a -> 0, with or without air absorption
    cases = [(94.0, 60.0, 1e-4, m) for m in (0.0, 0.005, 0.05)]
    assert check_agree(_eyring, _sabine, cases, rtol=1e-3, names=("eyring", "sabine")).status == PASS
    r = check_agree(_eyring_bug, _sabine, cases, rtol=1e-3, names=("eyring", "sabine"))
    assert r.status == FAIL and "eyring" in r.message


# --- derivatives: settles a claim about a dropped term ---

def test_derivative_check_and_fd():
    f = lambda x: np.exp(-x) * np.sin(3 * x)  # noqa: E731
    df = lambda x: np.exp(-x) * (3 * np.cos(3 * x) - np.sin(3 * x))  # noqa: E731
    assert check_derivative(f, df, [0.0, 0.4, 2.0]).status == PASS
    assert check_derivative(f, lambda x: df(x) + 1e-3 * np.cos(x), [0.4]).status == FAIL
    assert abs(fd_derivative(np.cos, 0.3, order=2) + math.cos(0.3)) < 1e-6


def test_margules_activity_derivative():
    # binary symmetric Margules, GE/RT = A x1 x2: ln g1 = A x2^2. d g1/d n1 at n = 1 is -2 A x2^2 g1 (exact)
    A = 1.0

    def gamma1(n1, n2=0.75):
        x2 = n2 / (n1 + n2)
        return math.exp(A * x2 * x2)

    def exact(n1, n2=0.75):  # d/dn1 exp(A x2^2), dx2/dn1 = -n2/n^2
        n = n1 + n2
        return gamma1(n1) * 2 * A * (n2 / n) * (-n2 / n**2)

    assert check_derivative(gamma1, exact, [0.25]).status == PASS
    wrong = lambda n1: -A * 0.75 * gamma1(n1)  # the "x-derivative" a static reader proposed  # noqa: E731
    assert check_derivative(gamma1, wrong, [0.25]).status == FAIL


# --- identities ---

def test_poisson_identity_for_plummer():
    b = 0.8
    phi = lambda x: -1.0 / np.sqrt(x @ x + b * b)  # noqa: E731
    rho = lambda x: 3 / (4 * np.pi * b**3) * (1 + (x @ x) / b**2) ** -2.5  # noqa: E731
    pts = [np.array([0.3, 0.1, -0.2]), np.array([1.0, 0.5, 0.2])]
    good = check_identity([(f"x={p}", laplacian_fd(phi, p), 4 * np.pi * rho(p)) for p in pts], rtol=1e-5, what="Poisson")
    assert good.status == PASS
    bad = check_identity([(f"x={p}", laplacian_fd(phi, p), 4 * np.pi * rho(p) * 1.02) for p in pts], rtol=1e-5, what="Poisson")
    assert bad.status == FAIL


def test_unitary():
    th = 0.7
    U = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]]) * np.exp(0.3j)
    assert check_unitary(np.stack([U, U.T])).status == PASS
    assert check_unitary(U * 1.001).status == FAIL


def test_nonfinite_is_a_failure():
    assert check_identity([("nan", np.nan, 1.0)]).status == FAIL


# --- extract_functions ---

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


def test_extract_functions_follows_same_file_helpers(tmp_path):
    f = tmp_path / "bends.py"
    f.write_text(SOURCE, encoding="utf-8")
    mod = extract_functions(f, ["curvature"])
    assert mod.__extracted__ == ["SCALE", "centered_diff", "curvature"]
    assert np.allclose(mod.curvature(np.array([0.0, 1.0, 4.0])), 2 * np.gradient([0.0, 1.0, 4.0]))
    assert not hasattr(mod, "unrelated")
    assert any("package_that_is_not_installed" in s for s in mod.__skipped_imports__)
    assert any("relative import" in s for s in mod.__skipped_imports__)
    with pytest.raises(KeyError):
        extract_functions(f, ["no_such_function"])


# --- sandbox: placeholder version files ---

def test_runner_writes_placeholder_version_files(tmp_path):
    r = _runner()
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text('[tool.setuptools_scm]\nversion_file = "src/pkg/_version.py"\n'
                                             '[tool.hatch.build.hooks.vcs]\nversion-file = "src/pkg/version.py"\n', encoding="utf-8")
    assert sorted(r.add_version_stubs(tmp_path)) == ["src/pkg/_version.py", "src/pkg/version.py"]
    ns = {}
    exec((tmp_path / "src" / "pkg" / "_version.py").read_text(), ns)
    assert ns["__version__"] == "0+unknown" and ns["version_tuple"][0] == 0
    assert r.add_version_stubs(tmp_path) == []  # existing files are left alone


def test_runner_version_file_from_setup_py_and_no_escape(tmp_path):
    r = _runner()
    (tmp_path / "pkg").mkdir()
    (tmp_path / "setup.py").write_text('setup(use_scm_version={"write_to": "pkg/_version.py"})\n', encoding="utf-8")
    assert r.add_version_stubs(tmp_path) == ["pkg/_version.py"]
    (tmp_path / "pyproject.toml").write_text('[tool.setuptools_scm]\nwrite_to = "../outside.py"\n', encoding="utf-8")
    assert r.version_files(tmp_path) == [(tmp_path / "pkg" / "_version.py").resolve()]


# --- roadmap items done after batch 8 ---

from physverify.loaders import load_repaired, repairs_note  # noqa: E402
from physverify.order import check_order  # noqa: E402
from physverify.studies import decay_rate, residual_check  # noqa: E402


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


def test_decay_rate_skips_the_start_up_transient():
    t = np.linspace(0, 6, 2001)
    y = np.exp(-0.7 * t) + 30.0 * np.exp(-3.0 * t)  # a large, fast transient on top of the slow mode
    naive = -np.polyfit(t, np.log(y), 1)[0]
    gamma, t0 = decay_rate(t, y)
    assert abs(naive - 0.7) > 0.3 and abs(gamma - 0.7) < 0.7 * 0.05 and t0 > 0  # accurate to about steady_tol
    g_tight, t_tight = decay_rate(t, y, steady_tol=0.005, windows=12)
    assert abs(g_tight - 0.7) < 0.7 * 0.005 and t_tight > t0
    g2, _ = decay_rate(t, y, t_skip=5.0)
    assert abs(g2 - 0.7) < 1e-3
    with pytest.raises(ValueError):
        decay_rate(t, np.exp(-0.1 * t**2))  # rate keeps growing: no steady stretch


def test_residual_check_catches_a_solver_that_does_not_iterate():
    rng = np.random.default_rng(1)
    n = 30
    A = np.diag(np.full(n, 4.0)) + np.diag(np.full(n - 1, -1.0), 1) + np.diag(np.full(n - 1, -1.0), -1)
    b = rng.normal(size=n)
    D = np.diag(A)

    def jacobi(tol, max_sweeps=10000):
        x = np.zeros(n)
        for _ in range(max_sweeps):
            x = (b - (A @ x - D * x)) / D
            if np.linalg.norm(b - A @ x) <= tol:
                break
        return x

    def one_sweep(tol):  # the real bug: a single sweep whatever the tolerance
        return (b - (A @ np.zeros(n) - 0.0)) / D

    res = lambda x: np.linalg.norm(b - A @ x)  # noqa: E731
    assert residual_check(jacobi, res).status == PASS
    r = residual_check(one_sweep, res, label="pressure solve")
    assert r.status == FAIL and "hardly changes" in r.message


def test_load_repaired_records_the_repair(tmp_path):
    f = tmp_path / "py2.py"
    f.write_text("def area(r):\n    return 3.14159265358979 * r ** 2\nprint 'loaded'\n", encoding="utf-8")
    with pytest.raises(SyntaxError):
        compile(f.read_text(), str(f), "exec")
    m = load_repaired("pv_py2_test", f, {"print 'loaded'": "print('loaded')"})
    assert abs(m.area(2.0) - 4 * math.pi) < 1e-12
    assert "tested after repairs" in repairs_note(m) and "print 'loaded'" in repairs_note(m)
    with pytest.raises(ValueError):
        load_repaired("pv_py2_test2", f, {"no such text": ""})
    assert not list(tmp_path.glob("__pycache__"))


def test_sandbox_stack_hint():
    spec = importlib.util.spec_from_file_location("pv_sandbox_b8", ROOT / "sandbox" / "sandbox.py")
    sb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sb)
    out = ("The conflict is caused by:\n    kfactory 3.5.0 depends on scipy<2 and >=1.18.1\n"
           "    opticalglass 2.0.2 depends on numpy>=2.5.1\nERROR: ResolutionImpossible: for help")
    hint = sb.stack_hint(out)
    assert "numpy >=2.5.1" in hint and "scipy <2 and >=1.18.1" in hint and "--stack latest" in hint
    assert sb.stack_hint("ERROR: No matching distribution found for pydy") == ""


# --- sandbox: importlib.metadata in a source checkout (daily corpus sessions, 2026-10) ---

def test_runner_metadata_shim_answers_for_own_package_only(tmp_path, monkeypatch):
    import subprocess
    import sys
    r = _runner()
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "my_pkg"\n', encoding="utf-8")
    assert r.dist_names(tmp_path) == ["my_pkg"]
    site = tmp_path / "site"
    site.mkdir()
    (site / "sitecustomize.py").write_text(r.SITE, encoding="utf-8")
    code = ("import importlib.metadata as m\nprint(m.version('my-pkg'))\n"
            "try:\n    m.version('not-a-package-xyz')\nexcept m.PackageNotFoundError:\n    print('raised')\n")
    env = {**__import__("os").environ, "PYTHONPATH": str(site), "PHYSVERIFY_SOURCE_DISTS": "my_pkg"}
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, cwd=tmp_path)
    assert out.stdout.split() == ["0+source", "raised"]
