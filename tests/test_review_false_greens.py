"""Regression tests for false greens found in an outside review of 0.9.0.

Each reference is from the mathematics, not the code: 4e-13 exceeds an atol of 1e-14; forward Euler is
A = [[0]], b = [1], c = [0]; its first-order continuous extension is b(theta) = theta (so b(0) = 0); an
additive method needs one weight vector per part.
"""

import subprocess
import sys
from math import nan

from physverify import check_order
from physverify.butcher import (
    check_additive,
    check_dense_output,
    check_rosenbrock,
    check_tableau,
)


def test_atol_enforced_below_floor():
    r = check_order([0.2, 0.1], [5e-13, 4e-13], expected=2, atol=1e-14)
    assert r.status == "FAIL" and "absolute tolerance" in r.message
    assert check_order([0.2, 0.1], [5e-13, 4e-13], expected=2, atol=1e-12).status == "EXACT"


def test_tableau_rejects_nan():
    assert check_tableau([[0]], [1], [nan], claimed=1).status == "FAIL"
    assert check_tableau([[0]], [1], [0], claimed=1, embedded=[nan], claimed_embedded=0).status == "FAIL"
    assert check_tableau([[0]], [1], [0], claimed=1).status == "PASS"


def test_tableau_compact_and_fsal_layouts_still_pass():
    # Heun stored as s x (s - 1), and Bogacki-Shampine with its FSAL stage of weight 0
    assert check_tableau([[0], [1]], [0.5, 0.5], [0, 1], claimed=2).status == "PASS"
    A = [[0, 0, 0, 0], [0.5, 0, 0, 0], [0, 0.75, 0, 0], [2 / 9, 1 / 3, 4 / 9, 0]]
    assert check_tableau(A, [2 / 9, 1 / 3, 4 / 9, 0], [0, 0.5, 0.75, 1], claimed=3).status == "PASS"


def test_dense_output_nan_and_left_endpoint():
    assert check_dense_output([[0]], lambda t: [nan], claimed=1).status == "FAIL"
    wrong_at_zero = check_dense_output([[0]], lambda t: [t if t > 0 else 1.0], claimed=1)
    assert wrong_at_zero.status == "FAIL"
    ok = check_dense_output([[0]], lambda t: [t], claimed=1)
    assert ok.status == "PASS" and "sampled points" in ok.message


def test_additive_partition_count_and_nan():
    assert check_additive([[[0]], [[0]]], [[1]], claimed=1).status == "FAIL"
    assert check_additive([[[0]], [[0]]], [[1], [1]], [[0]], claimed=1).status == "FAIL"
    assert check_additive([[[0]], [[0]]], [[1], [nan]], claimed=1).status == "FAIL"
    assert check_additive([[[0]], [[0]]], [[1], [1]], claimed=1).status == "PASS"


def test_rosenbrock_rejects_nan():
    assert check_rosenbrock([[0]], [[1]], [nan], claimed=1).status == "FAIL"
    assert check_rosenbrock([[0]], [[1]], [1], claimed=1).status == "PASS"


def _run(tmp_path, *extra):
    spec = tmp_path / "verify_skip.py"
    spec.write_text("from physverify import Check, requires\n"
                    "def optional():\n    requires('a_package_that_is_not_installed')\n"
                    "def checks():\n    return [Check('limit', 'optional', optional)]\n")
    return subprocess.run([sys.executable, "-m", "physverify", "run", str(spec), *extra],
                          capture_output=True, text=True)


def test_all_skipped_warns_and_strict_fails(tmp_path):
    r = _run(tmp_path)
    assert r.returncode == 0 and "nothing was verified" in r.stderr
    assert _run(tmp_path, "--strict").returncode == 1
