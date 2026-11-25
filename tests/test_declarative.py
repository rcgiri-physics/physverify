"""Specs written as [[tool.physverify.ode]] tables: a correct solver passes, seeded bugs fail, bad tables are refused."""

import importlib.metadata
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from physverify.agent import find_specs
from physverify.checks import run_check
from physverify.cli import main
from physverify.declarative import SpecError, compile_expression, load_toml_spec

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
TABLE = """
[[tool.physverify.ode]]
solver = "damped_oscillator:integrate"
order = 2
t_end = 1.0
y0 = { x = 1.0, v = 0.0 }
parameters = { omega = 3.0, gamma = 0.4 }
equations = { x = "v", v = "-omega**2 * x - 2*gamma*v" }
patch = true
"""
GENERIC = '''
import numpy as np

def rk2(f, y0, times):
    ys = [y0]
    for a, b in zip(times[:-1], times[1:]):
        h = b - a
        ys.append(ys[-1] + h * f(a + 0.5 * h, ys[-1] + 0.5 * h * f(a, ys[-1])))
    return np.array(ys)

def rk2_wrong_stage_time(f, y0, times):
    ys = [y0]
    for a, b in zip(times[:-1], times[1:]):
        h = b - a
        ys.append(ys[-1] + h * f(a, ys[-1] + 0.5 * h * f(a, ys[-1])))
    return np.array(ys)

def plain(y0, h, n_steps):
    return rk2(lambda t, y: np.array([y[1], -y[0]]), y0, h * np.arange(n_steps + 1))[-1]

def plain_wrong_sign(y0, h, n_steps):
    return rk2(lambda t, y: np.array([y[1], y[0]]), y0, h * np.arange(n_steps + 1))[-1]
'''
OSC = """
[[tool.physverify.ode]]
solver = "generic:{solver}"
args = {args}
returns = "{returns}"
order = 2
t_end = 1.0
y0 = {{ x = 1.0, v = 0.5 }}
equations = {{ x = "v", v = "-x" }}
conserved = "v**2 + x**2"
"""


@pytest.fixture
def project(tmp_path):
    saved = list(sys.path)
    shutil.copy(EXAMPLES / "damped_oscillator.py", tmp_path)
    (tmp_path / "generic.py").write_text(GENERIC)
    (tmp_path / "pyproject.toml").write_text(TABLE)
    yield tmp_path
    sys.path[:] = saved
    for name in ("damped_oscillator", "generic"):
        sys.modules.pop(name, None)


def statuses(project, text=None):
    path = project / "pyproject.toml"
    if text is not None:
        path.write_text(text)
    return {c.family: run_check(c).status for c in load_toml_spec(path)}


def osc(solver, args, returns):
    return OSC.format(solver=solver, args=args, returns=returns)


def test_correct_solver_passes(project):
    assert statuses(project) == {"mms": "PASS", "reference": "PASS", "patch": "EXACT"}
    assert main(["run", str(project / "pyproject.toml")]) == 0


def test_seeded_bug_fails_every_check(project):
    path = project / "damped_oscillator.py"
    text = path.read_text()
    assert "damping = 2.0 * GAMMA" in text
    path.write_text(text.replace("damping = 2.0 * GAMMA", "damping = 2.0 * GAMMA * 1.1"))
    assert set(statuses(project).values()) == {"FAIL"}


def test_wrong_equation_in_the_table_fails(project):
    assert statuses(project, TABLE.replace("2*gamma*v", "gamma*v"))["reference"] == "FAIL"


def test_solver_that_takes_f_and_returns_a_trajectory(project):
    args = '["f", "y0", "times"]'
    good = statuses(project, osc("rk2", args, "trajectory"))
    assert good == {"mms": "PASS", "reference": "PASS", "invariant": "PASS"}
    assert "integrator only" in load_toml_spec(project / "pyproject.toml")[0].label
    # y' = f(y) cannot see a wrong stage time; the manufactured forcing depends on t and does
    bad = statuses(project, osc("rk2_wrong_stage_time", args, "trajectory"))
    assert bad["mms"] == "FAIL" and bad["reference"] == "PASS"


def test_solver_without_a_hook_gets_the_reference_check_only(project):
    args = '["y0", "h", "n_steps"]'
    assert statuses(project, osc("plain", args, "final")) == {"reference": "PASS", "invariant": "PASS"}
    assert statuses(project, osc("plain_wrong_sign", args, "final"))["reference"] == "FAIL"


def test_wrong_output_shape_is_an_error_not_a_broadcast(project):
    assert set(statuses(project, osc("rk2", '["f", "y0", "times"]', "final")).values()) == {"ERROR"}


def test_same_module_name_in_two_projects_is_not_confused(project, tmp_path_factory):
    assert statuses(project)["mms"] == "PASS"
    other = tmp_path_factory.mktemp("other")
    text = (project / "damped_oscillator.py").read_text()
    (other / "damped_oscillator.py").write_text(text.replace("2.0 * GAMMA", "2.0 * GAMMA * 1.1"))
    assert statuses(other, TABLE)["mms"] == "FAIL"


@pytest.mark.parametrize("text", [
    "__import__('os').system('x')", "x.__class__", "(lambda: 1)()", "x[0]", "[x for x in y]", "x if x else 1",
    "open('f')", "x^2", "y", "sin(x, x)", "x @ x", "'a'", "1j", "True", "x < 1", "x +", "", "sin",
])
def test_expressions_outside_the_grammar_are_refused(text):
    with pytest.raises(SpecError):
        compile_expression(text, {"x"})


def test_expression_values():
    f = compile_expression("-x**2 / 4 + sin(pi/2) * arctan2(1, 1) - +t", {"x", "t"})
    assert f({"x": 3.0, "t": 0.5}) == pytest.approx(-9 / 4 + np.pi / 4 - 0.5)
    assert compile_expression("1/2", ())({}) == 0.5


@pytest.mark.parametrize(("old", "new", "message"), [
    ("order = 2", "order = 2\nordr = 3", "unknown key"),
    ("order = 2", "", "missing key"),
    ("order = 2", "order = true", "finite number"),
    ("order = 2", "order = -1", "positive"),
    ("t_end = 1.0", "t_end = inf", "finite number"),
    ("{ x = 1.0, v = 0.0 }", "{ x = 1.0 }", "same variables"),
    ("{ x = 1.0, v = 0.0 }", "{ v = 0.0, x = 1.0 }", "same order"),
    ("omega = 3.0", "t = 3.0", "cannot be used"),
    ("omega = 3.0", "x = 3.0", "both a variable"),
    ("order = 2", 'order = 2\nargs = ["y0", "t_end"]', "step size"),
    ("order = 2", 'order = 2\nargs = ["f", "source", "n_steps"]', "not both"),
    ("order = 2", 'order = 2\nargs = ["y0", "n_steps"]', "patch needs"),
    ("order = 2", "order = 2\nn_steps = [10, 10, 10]", "n_steps"),
    ("order = 2", "order = 2\nn_steps = [10, 20]", "n_steps"),
    ("damped_oscillator:integrate", "damped_oscillator.integrate", "module:function"),
    ("damped_oscillator:integrate", "damped_oscillator:nothing", "no function"),
    ("order = 2", 'order = 2\npath = ".."', "leaves the project"),
    ("[[tool.physverify.ode]]", "[tool.physverify.ode]", "two brackets"),
])
def test_bad_tables_are_refused_with_a_reason(project, old, new, message):
    text = TABLE.replace("[[tool.physverify.ode]]", new) if old.startswith("[[") else TABLE.replace(old, new, 1)
    (project / "pyproject.toml").write_text(text)
    with pytest.raises(SpecError, match=message):
        load_toml_spec(project / "pyproject.toml")


def test_cli_exit_codes(project):
    path = project / "pyproject.toml"
    path.write_text(TABLE.replace("order = 2", "order = 3"))
    assert main(["run", str(path)]) == 1
    path.write_text("[project]\nname = 'demo'\n")
    assert main(["run", str(path)]) == 2  # no table: nothing was tested


def test_hook_and_mcp_find_the_table_next_to_python_specs(project):
    shutil.copy(EXAMPLES / "verify_damped_oscillator.py", project)
    expected = ["verify_damped_oscillator.py", "pyproject.toml"]
    assert [p.name for p in find_specs(project)] == expected
    (project / "pyproject.toml").write_text("[tool.physverify]\nspecs = ['verify_damped_oscillator.py']\n" + TABLE)
    assert [p.name for p in find_specs(project)] == expected


def test_pytest_collects_the_table(project):
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "pyproject.toml"]
    if not any(e.name == "physverify" for e in importlib.metadata.entry_points(group="pytest11")):
        cmd += ["-p", "physverify.pytest_plugin"]
    out = subprocess.run(cmd, cwd=project, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0 and "3 passed" in out.stdout, out.stdout + out.stderr


def test_the_example_in_the_docs_runs(project):
    doc = (EXAMPLES.parent / "docs" / "declarative.md").read_text(encoding="utf-8")
    table = doc.split("```toml\n")[1].split("```")[0]
    assert statuses(project, table) == {"mms": "PASS", "reference": "PASS", "patch": "EXACT"}
