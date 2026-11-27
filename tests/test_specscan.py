"""Reading specs: a reference that calls the solver under test."""

import textwrap

from physverify.specscan import reference_notes


def test_reference_that_uses_the_solver_is_noted(tmp_path):
    spec = tmp_path / "verify_x.py"
    spec.write_text(textwrap.dedent('''
        import numpy as np
        import mysolver
        from physverify import Check

        def exact(t):
            return mysolver.run(t, dt=1e-6)

        def analytic(t):
            return np.exp(-t)

        def checks():
            return []
    '''), encoding="utf-8")
    notes = reference_notes(spec)
    assert len(notes) == 1 and "exact()" in notes[0] and "mysolver" in notes[0]

def test_reference_that_copies_solver_constants(tmp_path):
    spec = tmp_path / "spec.py"
    spec.write_text(textwrap.dedent('''
        import numpy as np
        import mysolver
        from mysolver import G

        sim = mysolver.Simulation()
        params = sim.params

        def exact(t):
            return np.cos(np.sqrt(mysolver.K / sim.mass) * t)

        def reference_period():
            return 2 * np.pi * np.sqrt(params["length"] / G)

        def analytic(t):
            return np.cos(2.0 * t)  # k = 4, m = 1 from the textbook
    '''), encoding="utf-8")
    notes = reference_notes(spec)
    assert len(notes) == 2, notes
    assert "mysolver.K" in notes[0] and "sim.mass" in notes[0] and "copied into the reference" in notes[0]
    assert "params['length']" in notes[1] and "G" in notes[1]


def test_reference_notes_calls_plus_constants_and_shadowing(tmp_path):
    spec = tmp_path / "spec.py"
    spec.write_text(textwrap.dedent('''
        import mysolver

        g = mysolver.G

        def exact(t):
            return mysolver.exact(t) * mysolver.G

        def reference(t, g=9.81):
            return 0.5 * g * t * t
    '''), encoding="utf-8")
    notes = reference_notes(spec)
    assert len(notes) == 1, notes
    assert "calls mysolver.exact" in notes[0] and "also reads mysolver.G" in notes[0]
