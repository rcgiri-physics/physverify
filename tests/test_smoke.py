"""physverify smoke: parse errors, crashes and input prompts."""

from physverify.smoke import CRASH, INPUT, OK, PARSES, smoke


def test_smoke_reports_parse_errors_crashes_and_input(tmp_path):
    (tmp_path / "good.py").write_text("x = 1 + 1\n")
    (tmp_path / "broken.py").write_text("def f(:\n    pass\n")
    (tmp_path / "crash.py").write_text("raise RuntimeError('boom')\n")
    (tmp_path / "ask.py").write_text("input('n? ')\n")
    got = {r.path.split("\\")[-1].split("/")[-1]: r.outcome for r in smoke(tmp_path, timeout=30)}
    assert got == {"good.py": OK, "broken.py": PARSES, "crash.py": CRASH, "ask.py": INPUT}
