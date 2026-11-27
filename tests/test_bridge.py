"""The command-line bridge, with a Python script standing in for a compiled program."""

import sys
import textwrap

import numpy as np
import pytest

from physverify.bridge import command, command_integrate, parse_numbers
from physverify.mms import zero_source
from physverify.studies import reference_study

PROGRAM = textwrap.dedent("""
    import math, sys
    y = [float(a) for a in sys.argv[1:3]]
    t_end, n = float(sys.argv[3]), int(sys.argv[4])
    h = t_end / n
    f = lambda y: [y[1], -y[0]]
    for _ in range(n):  # RK4 for the harmonic oscillator
        k1 = f(y); k2 = f([y[i] + h / 2 * k1[i] for i in range(2)])
        k3 = f([y[i] + h / 2 * k2[i] for i in range(2)]); k4 = f([y[i] + h * k3[i] for i in range(2)])
        y = [y[i] + h / 6 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]) for i in range(2)]
    print("final state:")
    print("%.17E %.17E" % tuple(y))
""")


@pytest.fixture
def program(tmp_path):
    p = tmp_path / "rk4.py"
    p.write_text(PROGRAM, encoding="utf-8")
    return [sys.executable, str(p), "{y0}", "{t_end}", "{n_steps}"]


def test_parse_numbers_reads_fortran_exponents():
    v = parse_numbers("x = 1.5D+02, y=-2e-3 z .5")
    assert v.tolist() == [150.0, -0.002, 0.5]


def test_reference_study_on_a_program(program):
    integrate = command_integrate(program)
    rhs = lambda t, y: np.array([y[1], -y[0]])  # noqa: E731
    r = reference_study(integrate, rhs, np.array([1.0, 0.0]), 1.0, (8, 16, 32, 64), 4.0)
    assert r.status == "PASS", r.message


def test_non_zero_source_is_refused(program):
    with pytest.raises(ValueError, match="cannot call a Python source"):
        command_integrate(program)(lambda t: np.array([t, 0.0]), [1.0, 0.0], 1.0, 4)
    assert command_integrate(program)(zero_source, [1.0, 0.0], 1.0, 4).shape == (2,)


def test_failures_are_reported(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("import sys; print('oops', file=sys.stderr); sys.exit(3)", encoding="utf-8")
    with pytest.raises(RuntimeError, match="status 3: oops"):
        command([sys.executable, str(bad)])()
    quiet = tmp_path / "quiet.py"
    quiet.write_text("print('done')", encoding="utf-8")
    with pytest.raises(RuntimeError, match="no numbers"):
        command([sys.executable, str(quiet)])()
    with pytest.raises(RuntimeError, match="cannot run"):
        command([str(tmp_path / "missing-program")])()
