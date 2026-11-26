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
