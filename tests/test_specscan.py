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
