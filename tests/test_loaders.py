"""Loading user code: answering input prompts, extracting functions, repairing imports."""

import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

from physverify.loaders import (  # noqa: E402
    extract_functions,
    load_repaired,
    repairs_note,
    run_script,
)

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


def test_run_script_answers_input_prompts(tmp_path):
    p = tmp_path / "ask.py"
    p.write_text("n = int(input('n? '))\nx = float(input('x? '))\nresult = n * x\nprint(result)\n")
    g, out = run_script(p, inputs=[3, 1.5])
    assert g["result"] == 4.5 and "4.5" in out
    with pytest.raises(EOFError):
        run_script(p, inputs=[3])


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
