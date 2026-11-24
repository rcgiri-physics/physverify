"""sandbox.py deps --source / --prefix and the memory setting (issue 48). Docker is not called."""

import importlib.util
import math
import time
from pathlib import Path

import numpy as np

from physverify.mms import ManufacturedODE, mms_order_study

ROOT = Path(__file__).resolve().parents[1]


def _load(monkeypatch, tmp_path, memory=None):
    monkeypatch.setenv("PHYSVERIFY_CORPUS", str(tmp_path))
    if memory:
        monkeypatch.setenv("PHYSVERIFY_MEMORY", memory)
    spec = importlib.util.spec_from_file_location("pv_sandbox_installs", ROOT / "sandbox" / "sandbox.py")
    sb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sb)
    calls = []
    monkeypatch.setattr(sb, "timed", lambda args, name, limit, keep=None: calls.append(args) or 0)
    monkeypatch.setattr(sb, "remove_stale", lambda name: None)
    monkeypatch.setattr(sb, "head", lambda repo: "abc")
    return sb, calls


def test_deps_default_is_wheels_only_target(monkeypatch, tmp_path):
    sb, calls = _load(monkeypatch, tmp_path)
    assert sb.main(["deps", "X1", "numpy"]) == 0
    args = calls[0]
    assert "--only-binary=:all:" in args and "--target=/deps" in args and "--memory=2g" in args


def test_deps_source_and_prefix(monkeypatch, tmp_path):
    sb, calls = _load(monkeypatch, tmp_path, memory="4g")
    assert sb.main(["deps", "--source", "--prefix", "X1", "git+https://example.org/p.git"]) == 0
    args = calls[0]
    assert "--only-binary=:all:" not in args and "--prefix=/deps" in args and "--target=/deps" not in args
    assert "--memory=4g" in args and "--memory-swap=4g" in args


def test_run_adds_prefix_paths(monkeypatch, tmp_path):
    sb, calls = _load(monkeypatch, tmp_path)
    (tmp_path / "repos" / "X1").mkdir(parents=True)
    (tmp_path / "deps" / "X1" / "lib" / "python3.13" / "site-packages").mkdir(parents=True)
    script = tmp_path / "a.py"
    script.write_text("print(1)\n")
    sb.main(["run", "X1", str(script)])
    args = calls[0]
    assert "PYTHONPATH=/deps:/deps/lib/python3.13/site-packages" in args and "LD_LIBRARY_PATH=/deps/lib" in args


def test_oom_note_names_the_setting(monkeypatch, tmp_path, capsys):
    sb, _ = _load(monkeypatch, tmp_path)
    assert sb.oom_note(137) == 137
    assert "PHYSVERIFY_MEMORY" in capsys.readouterr().out


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


def _slow_study(delay):
    mms = ManufacturedODE(lambda t: np.array([np.sin(t)]), lambda t, y: np.array([0.0]))

    def integrate(src, y0, t_end, n):  # RK4 on y' = src(t)
        time.sleep(delay * n / 8)
        y, h = np.array(y0, float), t_end / n
        for k in range(n):
            t = k * h
            y = y + h / 6 * (np.asarray(src(t)) + 4 * np.asarray(src(t + h / 2)) + np.asarray(src(t + h)))
        return y

    return lambda: mms_order_study(integrate, mms, 1.0, [8, 16, 32, 64, 128], 4)


def _euler_runs(ns, t_end, short_by=0):
    runs = []
    for n in ns:
        h = t_end / n
        steps = n - short_by
        t = np.arange(steps + 1) * h
        y = np.empty(steps + 1)
        y[0] = 1.0
        for k in range(steps):
            y[k + 1] = y[k] * (1 - h)
        runs.append((t, y))
    return runs


def _gauss_mean(sigma_used):
    def simulate(mu, rng):
        return rng.normal(mu, 1.0, size=10)

    def interval(x, level):
        z = {0.68: 0.994457883, 0.95: 1.959963985}[level]
        half = z * sigma_used / math.sqrt(len(x))
        return x.mean() - half, x.mean() + half

    return simulate, interval


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


def test_sandbox_stack_hint():
    spec = importlib.util.spec_from_file_location("pv_sandbox_b8", ROOT / "sandbox" / "sandbox.py")
    sb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sb)
    out = ("The conflict is caused by:\n    kfactory 3.5.0 depends on scipy<2 and >=1.18.1\n"
           "    opticalglass 2.0.2 depends on numpy>=2.5.1\nERROR: ResolutionImpossible: for help")
    hint = sb.stack_hint(out)
    assert "numpy >=2.5.1" in hint and "scipy <2 and >=1.18.1" in hint and "--stack latest" in hint
    assert sb.stack_hint("ERROR: No matching distribution found for pydy") == ""


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


def test_py314_shim_puts_the_future_import_first():
    shim = _runner().py314_shim
    out = shim('"""Doc."""\nclass A:\n    def f(self) -> B: ...\nclass B: ...\n')
    assert out.startswith('"""Doc."""\nfrom __future__ import annotations\n')
    compile(out, "x", "exec")
    assert shim("#!/usr/bin/env python\nx = 1\n").splitlines()[:2] == ["#!/usr/bin/env python", "from __future__ import annotations"]
    assert shim("from __future__ import annotations\nx = 1\n") is None
    assert shim("def f(:\n") is None
    both = shim('"""d"""\nfrom __future__ import division\nx = 1\n')
    compile(both, "x", "exec")


def test_runner_reports_files_written_into_the_repository(tmp_path):
    r = _runner()
    root = tmp_path / "repo"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "m.py").write_text("x = 1\n")
    before = r.snapshot(root)
    (root / "pkg" / "cache.npy").write_bytes(b"0")
    assert r.written(before, r.snapshot(root)) == ["pkg/cache.npy"]
