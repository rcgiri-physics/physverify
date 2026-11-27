"""physverify mutate: the changes it makes, and one run on a small solver."""

import ast
import shutil
import textwrap
from pathlib import Path

import pytest

from physverify.cli import main
from physverify.mutate import mutant_source, mutants

SOLVER = textwrap.dedent("""
    def integrate(source, y0, t_end, n_steps):
        h = t_end / n_steps
        y = y0
        for i in range(n_steps):
            y = y + h * (-y + source(i * h))
        return y
""")


def test_mutants_skip_loop_counts_and_cover_operators():
    found = mutants(SOLVER)
    kinds = [m.description for m in found]
    assert "operator / -> *" in kinds and "operator + -> -" in kinds and "unary minus removed" in kinds
    assert all(m.line != 5 for m in found)  # range(n_steps) is left alone


def test_each_mutant_is_one_change_and_valid_python():
    for m in mutants(SOLVER):
        changed = mutant_source(SOLVER, m.index)
        compile(changed, "<mutant>", "exec")
        assert changed != ast.unparse(ast.parse(SOLVER))


def test_mutant_index_out_of_range():
    with pytest.raises(IndexError):
        mutant_source(SOLVER, 10_000)


@pytest.mark.slow
def test_mutate_run_restores_the_file(tmp_path, capsys, monkeypatch):
    examples = Path(__file__).resolve().parents[1] / "examples"
    for name in ("damped_oscillator.py", "verify_damped_oscillator.py"):
        shutil.copy(examples / name, tmp_path / name)
    original = (tmp_path / "damped_oscillator.py").read_bytes()
    monkeypatch.chdir(tmp_path)
    code = main(["mutate", "verify_damped_oscillator.py", "--target", "damped_oscillator.py", "--limit", "3"])
    out = capsys.readouterr().out
    assert (tmp_path / "damped_oscillator.py").read_bytes() == original
    assert "caught 3 of 3 changes" in out and code == 0


def test_mutate_refuses_when_baseline_fails(tmp_path, capsys, monkeypatch):
    (tmp_path / "solver.py").write_text("X = 1.0\n", encoding="utf-8")
    (tmp_path / "verify_bad.py").write_text("def checks():\n    raise RuntimeError('broken spec')\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert main(["mutate", "verify_bad.py", "--target", "solver.py"]) == 2
    assert "unchanged code" in capsys.readouterr().err
    assert (tmp_path / "solver.py").read_text(encoding="utf-8") == "X = 1.0\n"


def test_times_one_is_not_mutated():
    assert not [m for m in mutants("def f(x):\n    return x * 1\n") if m.description.startswith("operator")]


@pytest.mark.slow
def test_lines_the_specs_never_run_are_reported(tmp_path, capsys, monkeypatch):
    examples = Path(__file__).resolve().parents[1] / "examples"
    for name in ("damped_oscillator.py", "verify_damped_oscillator.py"):
        shutil.copy(examples / name, tmp_path / name)
    solver = tmp_path / "damped_oscillator.py"
    solver.write_text(solver.read_text(encoding="utf-8") + "\n\ndef unused(y):\n    return -y\n", encoding="utf-8")
    original = solver.read_bytes()
    monkeypatch.chdir(tmp_path)
    found = mutants(original.decode())
    last = len(found)  # the unused function holds the last change
    code = main(["mutate", "verify_damped_oscillator.py", "--target", "damped_oscillator.py", "--limit", str(last)])
    out = capsys.readouterr().out
    assert solver.read_bytes() == original
    assert "NOT RUN" in out and "never run" in out and code == 1


def test_comparisons_and_constant_indices_are_mutated():
    src = "def f(y, t, t_end):\n    if t < t_end:\n        return y[0] + y[-1]\n    return y[1:]\n"
    kinds = {m.description for m in mutants(src)}
    assert {"comparison < -> <=", "index [0] -> [1]", "index [-1] -> [-2]"} <= kinds
    assert not any("[1:]" in k or "constant 1 " in k for k in kinds)  # slices are left alone
    for m in mutants(src):
        compile(mutant_source(src, m.index), "<mutant>", "exec")
    changed = [mutant_source(src, m.index) for m in mutants(src) if m.description == "index [-1] -> [-2]"][0]
    assert "y[-2]" in changed


def test_keyword_defaults_are_scaled():
    assert "constant 0.5 -> 0.55" in {m.description for m in mutants("def f(x, theta=0.5):\n    return x\n")}


def test_json_report_counts():
    import json

    from physverify.mutate import Mutant, to_json
    found = [Mutant(0, 3, 1, "a", status="caught"), Mutant(1, 2, 1, "b", status="survived"),
             Mutant(2, 4, 1, "c", status="not run")]
    d = json.loads(to_json("s.py", found))
    assert (d["total"], d["caught"], d["survived"], d["not_run"]) == (3, 1, 1, 1)
    assert [r["line"] for r in d["mutants"]] == [2, 3, 4]
