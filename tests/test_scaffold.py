"""`physverify init`, Markdown output, glob patterns, and the CI integration files."""

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

import physverify
from physverify.cli import expand_specs, main

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"

RK4 = '''
import numpy as np


def rhs(t, y):
    return np.array([-0.5 * y[0] + np.cos(t), y[0] * y[2], -y[1]])


def step(source, y0, t_end, n_steps):
    h = t_end / n_steps
    y = np.array(y0, dtype=float)
    f = lambda t, y: rhs(t, y) + source(t)
    for i in range(n_steps):
        t = i * h
        k1 = f(t, y)
        k2 = f(t + h / 2, y + h / 2 * k1)
        k3 = f(t + h / 2, y + h / 2 * k2)
        k4 = f(t + h, y + h * k3)
        y = y + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
    return y
'''


@pytest.fixture
def folder(tmp_path):
    yield tmp_path
    for name in ("damped_oscillator", "rk4_solver"):
        sys.modules.pop(name, None)
    if str(tmp_path) in sys.path:
        sys.path.remove(str(tmp_path))


def fill_rhs(spec: Path, body: str):
    text = spec.read_text()
    text, n = re.subn(r'    raise NotImplementedError\("write reference_rhs in [^"]+"\)', "    " + body, text)
    assert n == 1
    spec.write_text(text)


def run_json(spec, capsys):
    code = main(["run", str(spec), "--json", "-"])
    return code, json.loads(capsys.readouterr().out)


def test_init_spec_fails_until_the_equations_are_written(folder, capsys):
    shutil.copy(EXAMPLES / "damped_oscillator.py", folder)
    spec = folder / "verify_solver.py"
    assert main(["init", str(spec), "--solver", "damped_oscillator"]) == 0
    assert "TODO" in spec.read_text()
    capsys.readouterr()
    code, data = run_json(spec, capsys)
    assert code == 1 and {c["status"] for c in data["checks"]} == {"ERROR"}
    assert "write reference_rhs" in data["checks"][0]["message"]


def test_init_spec_passes_a_correct_solver_and_fails_a_broken_one(folder, capsys):
    shutil.copy(EXAMPLES / "damped_oscillator.py", folder)
    spec = folder / "verify_solver.py"
    main(["init", str(spec), "--solver", "damped_oscillator", "--order", "2"])
    fill_rhs(spec, "return np.array([y[1], -9.0 * y[0] - 0.8 * y[1]])")
    capsys.readouterr()
    code, data = run_json(spec, capsys)
    assert code == 0
    assert {c["family"] for c in data["checks"]} == {"mms", "reference", "patch"}

    solver = folder / "damped_oscillator.py"
    solver.write_text(solver.read_text().replace("damping = 2.0 * GAMMA", "damping = 2.0 * GAMMA * 1.1"))
    sys.modules.pop("damped_oscillator", None)
    code, data = run_json(spec, capsys)
    assert code == 1 and not any(c["ok"] for c in data["checks"])


def test_init_spec_for_a_fourth_order_three_component_solver(folder, capsys):
    (folder / "rk4_solver.py").write_text(RK4)
    spec = folder / "verify_rk4.py"
    main(["init", str(spec), "--solver", "rk4_solver", "--function", "step", "--dim", "3", "--order", "4", "--t-end", "2"])
    fill_rhs(spec, "return np.array([-0.5 * y[0] + np.cos(t), y[0] * y[2], -y[1]])")
    capsys.readouterr()
    code, data = run_json(spec, capsys)
    assert code == 0, data
    orders = [c["observed_order"] for c in data["checks"] if c["family"] != "patch"]
    assert all(abs(p - 4) < 0.3 for p in orders)


def test_init_refuses_to_overwrite_and_rejects_bad_names(folder, capsys):
    spec = folder / "verify_solver.py"
    spec.write_text("keep me\n")
    assert main(["init", str(spec)]) == 2
    assert "exists" in capsys.readouterr().err and spec.read_text() == "keep me\n"
    assert main(["init", str(spec), "--force"]) == 0
    assert main(["init", str(folder / "v.py"), "--solver", "my-solver"]) == 2
    assert main(["init", str(folder / "w.py"), "--dim", "0"]) == 2


def test_markdown_summary_is_appended(folder, capsys):
    for name in ("damped_oscillator.py", "verify_damped_oscillator.py"):
        shutil.copy(EXAMPLES / name, folder / name)
    summary = folder / "summary.md"
    summary.write_text("earlier step\n")
    assert main(["run", str(folder / "verify_damped_oscillator.py"), "--markdown", str(summary), "--quiet"]) == 0
    text = summary.read_text()
    assert text.startswith("earlier step\n")
    assert "4 of 4 checks passed" in text and "| mms | PASS |" in text
    assert re.search(r"\| [12]\.\d\d \(expected 2\) \|", text)


def test_glob_patterns_are_expanded_and_an_empty_match_is_an_error(folder, capsys):
    (folder / "sub").mkdir()
    for p in (folder / "verify_a.py", folder / "sub" / "verify_b.py", folder / "other.py"):
        p.write_text("")
    found = expand_specs([str(folder / "**" / "verify_*.py")])
    assert sorted(Path(f).name for f in found) == ["verify_a.py", "verify_b.py"]
    assert expand_specs([str(folder / "verify_a.py"), str(folder / "verify_a.py")]) == [str(folder / "verify_a.py")]
    assert main(["run", str(folder / "none" / "verify_*.py")]) == 2
    assert "no spec file matches" in capsys.readouterr().err


def test_citation_version_matches_the_package():
    text = (ROOT / "CITATION.cff").read_text()
    assert re.search(r"^version: (\S+)$", text, re.M).group(1) == physverify.__version__


def test_action_and_pre_commit_files_are_valid_yaml():
    yaml = pytest.importorskip("yaml")
    action = yaml.safe_load((ROOT / "action.yml").read_text())
    assert action["runs"]["using"] == "composite"
    used = set(re.findall(r"inputs\.([a-z-]+)", (ROOT / "action.yml").read_text()))
    assert used <= set(action["inputs"])
    hooks = yaml.safe_load((ROOT / ".pre-commit-hooks.yaml").read_text())
    assert hooks[0]["id"] == "physverify" and hooks[0]["entry"] == "physverify run"
