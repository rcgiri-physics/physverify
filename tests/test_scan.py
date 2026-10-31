"""physverify scan: each stage finds its pattern, and stays quiet on correct code."""

import json
import sys
import textwrap

import pytest

from physverify.cli import main
from physverify.scan import NOTE, WARN, scan


def _write(tmp_path, name, src):
    p = tmp_path / name
    p.write_text(textwrap.dedent(src), encoding="utf-8")
    return p


def _by_stage(findings, stage):
    return [f for f in findings if f.stage == stage]


def test_correct_rk4_table_is_a_note_only(tmp_path):
    _write(tmp_path, "rk.py", '''
        def rk4():
            A = [[0, 0, 0, 0], [0.5, 0, 0, 0], [0, 0.5, 0, 0], [0, 0, 1, 0]]
            b = [1/6, 1/3, 1/3, 1/6]
            c = [0, 0.5, 0.5, 1]
            return A, b, c
        ''')
    t = _by_stage(scan(tmp_path)[0], "tables")
    assert len(t) == 1 and t[0].level == NOTE and "order 4" in t[0].message


def test_table_below_its_claimed_order_and_bad_row_sum(tmp_path):
    # Heun's third-order table with a32 typed wrong, labelled order 3, and c that does not match
    _write(tmp_path, "rk.py", '''
        import numpy as np
        def method_order3():
            A = np.array([[0, 0, 0], [1/3, 0, 0], [0, 0.6, 0]])
            b = np.array([1/4, 0, 3/4])
            c = [0, 1/3, 2/3]
            return A, b, c
        ''')
    (t,) = _by_stage(scan(tmp_path)[0], "tables")
    assert t.level == WARN
    assert "suggests order 3" in t.message and "row 2 of A sums to" in t.message


def test_error_weights_must_sum_to_zero(tmp_path):
    _write(tmp_path, "rk.py", '''
        A = [[0, 0], [1, 0]]
        b = [0.5, 0.5]
        e = [0.5, -0.47]
        ''')
    (t,) = _by_stage(scan(tmp_path)[0], "tables")
    assert t.level == WARN and "sum to 0.03" in t.message


def test_vector_that_is_not_weights_is_not_a_table(tmp_path):
    _write(tmp_path, "m.py", '''
        A = [[1, 0], [2, 3]]
        b = [4, 5]
        ''')
    assert not _by_stage(scan(tmp_path)[0], "tables")


def test_grid_spacing_mismatch_same_file(tmp_path):
    _write(tmp_path, "g.py", '''
        import numpy as np
        def grid(L, N):
            x = np.linspace(0, L, N)
            dx = L / N
            return x, dx
        def interior(W, N):
            x = np.linspace(0, W, N + 1)[1:-1]
            dx = W / (N - 1)
            return x, dx
        ''')
    g = _by_stage(scan(tmp_path)[0], "grid")
    assert [f.line for f in g] == [5, 9] and all(f.level == WARN for f in g)


def test_correct_grid_spacings_are_quiet(tmp_path):
    _write(tmp_path, "g.py", '''
        import numpy as np
        def grid(L, N, a, b):
            x = np.linspace(0, L, N + 1)
            dx = L / N
            y = np.linspace(a, b, N)
            dy = (b - a) / (N - 1)
            z = np.linspace(0, L, N, endpoint=False)
            dz = L / N
            return x, dx, y, dy, z, dz
        ''')
    assert not _by_stage(scan(tmp_path)[0], "grid")


def test_grid_mismatch_across_files_is_a_note(tmp_path):
    _write(tmp_path, "ham.py", '''
        class H:
            def __init__(self, N, extent):
                self.N, self.extent = N, extent
                self.dx = extent / N
        ''')
    _write(tmp_path, "particle.py", '''
        import numpy as np
        def grid(H):
            return np.linspace(-H.extent / 2, H.extent / 2, H.N)
        ''')
    (g,) = _by_stage(scan(tmp_path)[0], "grid")
    assert g.level == NOTE and g.path == "ham.py"


def test_inverse_pairs_and_constants(tmp_path):
    _write(tmp_path, "c.py", '''
        g = 9
        def cart_to_polar(x): return x
        def polar_to_cart(x): return x
        def s2z(x): return x
        def z2s(x): return x
        ''')
    f = scan(tmp_path)[0]
    assert len(_by_stage(f, "pairs")) == 2
    assert _by_stage(f, "constants")


def test_unparsable_file_is_a_warning_not_an_exception(tmp_path):
    _write(tmp_path, "bad.py", "def f(:\n")
    findings, unparsed = scan(tmp_path)
    assert unparsed == [] and [f.message.startswith("the file does not parse") for f in findings] == [True]
    findings, unparsed = scan(tmp_path, stages=("tables",))
    assert findings == [] and len(unparsed) == 1


def test_cli_exit_codes_and_json(tmp_path, capsys):
    _write(tmp_path, "g.py", "import numpy as np\nL, N = 1.0, 10\nx = np.linspace(0, L, N)\ndx = L / N\n")
    assert main(["scan", str(tmp_path)]) == 1
    assert main(["scan", str(tmp_path), "--only", "pairs"]) == 0
    assert main(["scan", str(tmp_path), "--only", "nope"]) == 2
    capsys.readouterr()
    assert main(["scan", str(tmp_path), "--json", "-"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["warn"] == 1 and data["findings"][0]["stage"] == "grid"


def test_grid_of_another_size_is_not_flagged(tmp_path):
    # element length L/n next to a plotting grid of n*100 points (a false alarm in the corpus rescan)
    _write(tmp_path, "fem.py", '''
        import numpy as np
        L, n = 1.0, 10
        h = L / n
        x = np.linspace(0, L, n * 100)
        ''')
    assert not _by_stage(scan(tmp_path)[0], "grid")


def test_grid_mismatch_in_another_function_is_a_note(tmp_path):
    _write(tmp_path, "s.py", '''
        import numpy as np
        class Spectra:
            def bins(self):
                self.dv = self.vmax / self.nbins
            def velocities(self):
                return np.linspace(0, self.vmax, self.nbins)
        ''')
    (g,) = _by_stage(scan(tmp_path)[0], "grid")
    assert g.level == NOTE and "another function" in g.message


def test_constants_skip_ordinary_numbers_and_group_repeats(tmp_path):
    _write(tmp_path, "c.py", '''
        a = 3.3        # within 10% of pi, but an ordinary number
        b = 2.5        # within 10% of e
        y = 9.7 * 2    # near g, but not assigned to a gravity name
        p1 = 3.14
        p2 = 3.14
        G = 6.67e-11
        ''')
    (c,) = _by_stage(scan(tmp_path)[0], "constants")
    assert "pi" in c.message and "also lines 6" in c.message


def test_order_stated_by_a_property_wins_over_the_docstring(tmp_path):
    _write(tmp_path, "rk.py", '''
        class RK32:
            """Explicit Runge-Kutta of order 2."""
            A = [[0, 0, 0], [0.5, 0, 0], [0, 1, 0]]
            b = [0, 1, 0]
            c = [0, 0.5, 1]

            @property
            def order(self):
                return 3
        ''')
    (t,) = _by_stage(scan(tmp_path)[0], "tables")
    assert t.level == WARN and "order 3 stated in the code" in t.message


def test_awkward_literals_do_not_stop_the_scan(tmp_path):
    _write(tmp_path, "odd.py", '''
        import numpy as np
        A = np.array([[0, 0], [1, 0]]) / 2.0
        big = 10 ** 400
        x = big / 3
        y = 123456789 ** 50 / 7
        ''')
    findings, unparsed = scan(tmp_path)
    assert unparsed == []


def test_tables_written_as_fraction_strings(tmp_path):
    _write(tmp_path, "rk.py", '''
        def midpoint():
            A = [["0", "0"], ["1/2", "0"]]
            b = ["0", "1"]
            c = ["0", "1/2"]
            return A, b, c
        ''')
    (t,) = _by_stage(scan(tmp_path)[0], "tables")
    assert "order 2" in t.message and t.level == NOTE


def test_slice_step_is_its_own_grid(tmp_path):
    _write(tmp_path, "p.py", '''
        import numpy as np
        def plot(xmin, xmax, n):
            x = np.linspace(xmin, xmax, n)
            g = np.mgrid[xmin:xmax:(xmax - xmin) / n]
            return x, g
        ''')
    assert not _by_stage(scan(tmp_path)[0], "grid")


_RK4_CODE = '''
    def rk4(f, t, y, h):
        k1 = f(t, y)
        k2 = f(t + h / 2, y + h / 2 * k1)
        k3 = f(t + h / 2, y + h / 2 * k2)
        k4 = f(t + h, y + h * k3)
        return y + h * (k1 + 2 * k2 + 2 * k3 + k4) / 6
    '''


def test_stages_written_as_code_correct_rk4(tmp_path):
    _write(tmp_path, "rk.py", _RK4_CODE)
    (t,) = _by_stage(scan(tmp_path)[0], "tables")
    assert t.level == NOTE and "4 stages, order 4" in t.message


def test_stage_fed_with_the_wrong_earlier_stage(tmp_path):
    # Heun's third-order method with k1 where k2 belongs (a real defect found by the corpus rescan)
    _write(tmp_path, "rk.py", '''
        def heun3(model, t, x, h):
            k1 = model(t, x)
            k2 = model(t + 1/3 * h, x + 1/3 * h * k1)
            k3 = model(t + 2/3 * h, x + 2/3 * h * k1)
            return h * (1/4 * k1 + 3/4 * k3)
        ''')
    (t,) = _by_stage(scan(tmp_path)[0], "tables")
    assert t.level == WARN and "order 2" in t.message and "suggests order 3" in t.message


def test_stage_time_and_docstring_table(tmp_path):
    _write(tmp_path, "rk.py", """
        import numpy as np
        def heun(fun, x, y0):
            '''
            Explicit Heun 2nd order
             0 | 0   0
             1 | 1   0
            ---------
               | 1/2 1/2
            '''
            h = x[1] - x[0]
            y = np.zeros((len(x), 1))
            for n in range(len(x) - 1):
                k1 = h * fun(x[n], y[n, :])
                k2 = h * fun(x[n], y[n, :] + k1)
                y[n + 1, :] = y[n, :] + k1 / 2.0 + k2 / 2.0
            return y
        """)
    (t,) = _by_stage(scan(tmp_path)[0], "tables")
    assert t.level == WARN and "stage 2 is evaluated at t + 0 h" in t.message
    assert "matches the Butcher table in its docstring" in t.message


def test_stage_without_the_step_size(tmp_path):
    _write(tmp_path, "rk.py", '''
        def rk3(f, t, y, h):
            k1 = f(t, y)
            k2 = f(t + h / 2, y + h / 2 * k1)
            k3 = f(t + h, y - k1 + 2 * k2)
            return y + h * (k1 + 4 * k2 + k3) / 6
        ''')
    (t,) = _by_stage(scan(tmp_path)[0], "tables")
    assert t.level == WARN and "without the step size h" in t.message


def test_function_that_is_not_a_stepper_is_ignored(tmp_path):
    _write(tmp_path, "m.py", '''
        def energy(pot, x, v, m):
            a = pot(x, 1) + pot(x, 2)
            return 0.5 * m * v**2 + a
        ''')
    assert not _by_stage(scan(tmp_path)[0], "tables")


def test_autonomous_and_split_systems_are_not_flagged(tmp_path):
    _write(tmp_path, "rk.py", '''
        def rk4(dt, state, p):
            k1 = derivatives(state, p)
            k2 = derivatives(state + 0.5 * dt * k1, p)
            k3 = derivatives(state + 0.5 * dt * k2, p)
            k4 = derivatives(state + dt * k3, p)
            return state + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)

        def rk4_second_order(f, x, y, z, h):
            k1 = h * z
            l1 = h * f(x, y, z)
            k2 = h * (z + 0.5 * l1)
            l2 = h * f(x + 0.5 * h, y + 0.5 * k1, z + 0.5 * l1)
            k3 = h * (z + 0.5 * l2)
            l3 = h * f(x + 0.5 * h, y + 0.5 * k2, z + 0.5 * l2)
            k4 = h * (z + l3)
            l4 = h * f(x + h, y + k3, z + l3)
            return y + (k1 + 2 * k2 + 2 * k3 + k4) / 6.0, z + (l1 + 2 * l2 + 2 * l3 + l4) / 6.0
        ''')
    assert not [f for f in _by_stage(scan(tmp_path)[0], "tables") if f.level == WARN]


def test_wrong_weights_against_the_docstring(tmp_path):
    _write(tmp_path, "rk.py", """
        def ode4(f, y, x, h):
            '''
            Runge-Kutta 4th order
             0   | 0   0   0   0
             1/2 | 1/2 0   0   0
             1/2 | 0   1/2 0   0
             1   | 0   0   1   0
            -----------------------
                 | 1/6 1/3 1/3 1/6
            '''
            k1 = h * f(x, y)
            k2 = h * f(x + h / 2, y + k1 / 2)
            k3 = h * f(x + h / 2, y + k2 / 2)
            k4 = h * f(x + h, y + k3)
            return y + k1 / 3 + k2 / 6 + k3 / 6 + k4 / 3
        """)
    (t,) = _by_stage(scan(tmp_path)[0], "tables")
    assert t.level == WARN and "order 2" in t.message and "docstring" in t.message


def test_table_passed_to_a_constructor(tmp_path):
    # error weights that sum to 0.97 instead of 0 (the Tsit5 defect reported in the corpus study)
    _write(tmp_path, "tab.py", '''
        def Heun():
            """Heun's method."""
            return ButcherTableau(
                a=torch.tensor([[0.0, 0.0], [1.0, 0.0]]),
                b=torch.tensor([0.5, 0.5]),
                c=torch.tensor([0.0, 1.0]),
                b_error=torch.tensor([0.5 - 0.03, -0.5]),
                order=2,
            )
        ''')
    (t,) = _by_stage(scan(tmp_path)[0], "tables")
    assert t.level == WARN and "in Heun" in t.message and "sum to -0.03" in t.message


def test_inherited_table_built_by_slices(tmp_path):
    _write(tmp_path, "rk.py", '''
        import numpy as np
        class SDIRK2:
            g = 1
            A = np.zeros((2, 2))
            A[0, :1] = [1 - 2 ** -0.5]
            A[1, :2] = [2 ** -0.5, 1 - 2 ** -0.5]
            b = A[-1]
            c = np.array([1 - 2 ** -0.5, 1.0])
            order = 2

        class Labelled(SDIRK2):
            order = 3
        ''')
    t = _by_stage(scan(tmp_path)[0], "tables")
    by_name = {("Labelled" in f.message): f for f in t}
    assert by_name[False].level == NOTE and "order 2" in by_name[False].message
    assert by_name[True].level == WARN and "order 3 stated in the code" in by_name[True].message


def test_stated_embedded_order(tmp_path):
    _write(tmp_path, "rk.py", '''
        class Heun21:
            A = [[0, 0], [1, 0]]
            b = [0.5, 0.5]
            b2 = [1, 0]
            order = 2
            orderEmbedded = 2
        ''')
    (t,) = _by_stage(scan(tmp_path)[0], "tables")
    assert t.level == WARN and "embedded weights b2 have order 1, but order 2 is stated" in t.message


def test_undefined_names(tmp_path):
    _write(tmp_path, "cad.py", '''
        import sys

        class Rocket:
            def __init__(self, wall_thickness):
                self.tw = wall_thicknesss

        def plot(x):
            return np.sin(x)

        try:
            maxint = sys.maxint
        except AttributeError:
            maxint = unicode_fallback

        if sys.version_info < (3,):
            text = unicode("a")
        ''')
    f = _by_stage(scan(tmp_path)[0], "names")
    assert [x.message.split()[0] for x in f] == ["wall_thicknesss", "np", "unicode_fallback"]
    assert "did you mean wall_thickness?" in f[0].message


def test_star_import_and_exec_turn_the_name_check_off(tmp_path):
    _write(tmp_path, "a.py", "from numpy import *\nx = sin(1)\n")
    _write(tmp_path, "b.py", "exec('y = 1')\nprint(y)\n")
    assert not _by_stage(scan(tmp_path)[0], "names")


def test_removed_numpy_scipy_and_python_features(tmp_path):
    _write(tmp_path, "old.py", '''
        import imp
        import numpy as np
        from numpy import NaN
        from scipy.integrate import simps
        from scipy.misc import factorial
        a = np.array([1, 2], copy=False)
        b = np.float(2) + np.Inf
        c = np.trapz([1, 2])
        d = np.array([1, 2], copy=True) + np.nan
        ''')
    f = _by_stage(scan(tmp_path)[0], "api")
    text = " | ".join(x.message for x in f)
    for part in ("imp", "numpy.NaN", "simps", "factorial", "copy=False", "np.float was removed", "np.Inf"):
        assert part in text
    assert [x.level for x in f if "trapz" in x.message] == [NOTE]
    assert not [x for x in f if x.line == 10]


def test_scipy_romb_is_not_removed_but_romberg_is(tmp_path):
    # SciPy 1.15 removed romberg and quadrature; romb still exists (it gave 4 false WARNs on a corpus repository)
    _write(tmp_path, "integ.py", '''
        import scipy.integrate as si
        import scipy
        from scipy.integrate import romb, quad
        from scipy.integrate import romberg
        a = romb([1.0, 2.0, 3.0])
        b = scipy.integrate.quadrature
        c = scipy.integrate.romb
        ''')
    f = _by_stage(scan(tmp_path)[0], "api")
    assert [x.line for x in f] == [5, 7]
    assert all("scipy.integrate.quad" in x.message for x in f)


def test_literal_typos(tmp_path):
    _write(tmp_path, "lit.py", '''
        import numpy as np
        cutoff = 1e0 - 5
        small = 1e-99 + 1
        r2 = r ^ 2
        bad = x == np.nan
        mask = flags ^ 0xFF
        ''')
    f = _by_stage(scan(tmp_path)[0], "literals")
    assert [x.line for x in f] == [3, 5, 6]
    assert "1e-5" in f[0].message and "exclusive or" in f[1].message and "never" in f[2].message


def test_unit_table_dimensions(tmp_path):
    _write(tmp_path, "physical.py", '''
        from astropy.units import si
        _units_and_physical_types = [
            (si.W * si.m**2 * si.Hz**-1, "surface tension"),
            (si.N / si.m, "surface tension"),
            (si.J / si.K, {"entropy", "heat capacity"}),
            (si.kg / si.m**3, "mass density"),
        ]
        ''')
    (f,) = _by_stage(scan(tmp_path)[0], "units")
    assert f.line == 4 and "surface tension" in f.message and "kg s^-2" in f.message


def test_exact_and_cgs_constants(tmp_path):
    _write(tmp_path, "c.py", '''
        h = 6.62607015e-34
        h_CGS = 6.626196e-27
        au = 149597870691
        au_exact = 149597870700
        ''')
    f = _by_stage(scan(tmp_path)[0], "constants")
    assert [x.line for x in f] == [3, 4]
    assert "h (CGS)" in f[0].message and "astronomical unit" in f[1].message


@pytest.mark.skipif(sys.version_info < (3, 12), reason="type parameter syntax needs Python 3.12")
def test_type_parameters_are_defined_names(tmp_path):
    _write(tmp_path, "g.py", "def generic[T](x: T) -> T:\n    return x\n")
    assert not _by_stage(scan(tmp_path)[0], "names")


def test_name_check_respects_noqa_annotations_and_templates(tmp_path):
    _write(tmp_path, "a.py", '''
        def f(x) -> Dot:  # noqa: F821
            return helper(x)  # noqa
        def g(x: Missing) -> int:
            return 1
        ''')
    _write(tmp_path, "b.py", "from __future__ import annotations\ndef g(x: Missing) -> Other:\n    return 1\n")
    _write(tmp_path, "tpl.py", "{% for name in names %}\nx = {{ name }}\n{% endfor %}\n")
    (tmp_path / "bom.py").write_bytes(b"\xef\xbb\xbfimport numpy as np\nx = np.pi\n")
    f = scan(tmp_path)[0]
    names = {(x.path, x.level, x.message.split()[0]) for x in _by_stage(f, "names")}
    assert names == {("a.py", NOTE, "Missing"), ("tpl.py", NOTE, "the")}


def test_compatibility_shims_are_not_removed_api_findings(tmp_path):
    _write(tmp_path, "compat.py", '''
        import numpy as np
        try:
            float_ = np.float_
        except AttributeError:
            float_ = np.float64
        x = np.NaN
        ''')
    (f,) = _by_stage(scan(tmp_path)[0], "api")
    assert f.line == 7


def test_environment_names_and_nan_tests_are_quiet(tmp_path):
    _write(tmp_path, "jupyter_notebook_config.py", "c.NotebookApp.port = 8888\n")
    (tmp_path / "tests").mkdir()
    _write(tmp_path / "tests", "test_nan.py", "import math\nassert not (1.0 == math.nan)\n")
    f = scan(tmp_path)[0]
    assert not _by_stage(f, "names") and not _by_stage(f, "literals")


def test_extract_tables_returns_the_coefficients(tmp_path):
    from physverify.butcher import check_tableau
    from physverify.scan import extract_tables

    _write(tmp_path, "rk.py", _RK4_CODE)
    _write(tmp_path, "tab.py", '''
        def ssprk3():
            """order 3"""
            A = [[0, 0, 0], [1, 0, 0], [0.25, 0.25, 0]]
            b = [1/6, 1/6, 2/3]
            c = [0, 1, 0.5]
            return A, b, c
        ''')
    tables = {t["name"]: t for t in extract_tables(tmp_path)}
    assert set(tables) == {"rk4", "ssprk3"}
    assert tables["rk4"]["kind"] == "stages written as code" and tables["rk4"]["claimed"] == 4
    t = tables["ssprk3"]
    assert check_tableau(t["A"], t["b"], t["c"], claimed=t["claimed"]).status == "PASS"


def test_spacing_of_its_own_periodic_grid_is_not_paired_elsewhere(tmp_path):
    _write(tmp_path, "spectral.py", """
        import numpy as np
        def evolve(x_min, x_max, n_points):
            x = np.linspace(x_min, x_max, n_points, endpoint=False)
            dx = (x_max - x_min) / n_points
            return x, dx
        """)
    _write(tmp_path, "fd.py", """
        import numpy as np
        def states(x_min, x_max, n_points):
            x = np.linspace(x_min, x_max, n_points)
            return x, x[1] - x[0]
        """)
    assert not _by_stage(scan(tmp_path)[0], "grid")


def test_many_injected_names_become_one_note(tmp_path):
    _write(tmp_path, "host.py", """
        sel = NamedSelection.Create(FaceSelection.Create(GetRootPart().Faces), Selection.Empty())
        opts = FixMissingFacesOptions()
        DocumentSave.Execute(GetRootPart().Document.Path)
        CloseWindow()
        """)
    _write(tmp_path, "forgot.py", "x = np.sin(1)\ny = plt.plot(x)\nz = sparse.eye(3)\nw = linalg.inv(z)\nv = a + b + c\n")
    f = _by_stage(scan(tmp_path)[0], "names")
    host = [x for x in f if x.path == "host.py"]
    assert len(host) == 1 and host[0].level == NOTE and "run time" in host[0].message
    assert len([x for x in f if x.path == "forgot.py" and x.level == WARN]) >= 5


def test_constants_in_data_files_and_tables_are_summarised(tmp_path):
    _write(tmp_path, "rates.py", "\n".join(f"r{i} = rate({2.7175 + 1e-5 * i:.6f}, {3.1405 + 1e-5 * i:.6f})"
                                            for i in range(30)) + "\n")
    _write(tmp_path, "table.py", "y = [3.1, 3.12, 3.13, 3.14, 3.15, 2.27, 2.71, 2.72]\n")
    _write(tmp_path, "masses.py", "amu = 1.66053906660e-27\nm_n = 1.67492749804e-27\ncharge = 1.44e-19\n")
    f = _by_stage(scan(tmp_path)[0], "constants")
    assert [(x.path, "close to physical constants" in x.message) for x in f] == [("rates.py", True)]


def test_test_functions_are_not_inverse_pairs(tmp_path):
    _write(tmp_path, "t.py", """
        def test_xyz_to_lab(): pass
        def test_lab_to_xyz(): pass
        def c2k(t): return t
        def k2c(t): return t
        """)
    f = _by_stage(scan(tmp_path)[0], "pairs")
    assert len(f) == 1 and "c2k" in f[0].message


# --- rules from the 2026-10 daily corpus sessions ------------------------------------------------------

def test_generator_passed_to_vstack_is_a_warn(tmp_path):
    _write(tmp_path, "s.py", '''
        import numpy as np
        a = np.vstack(np.ones(3) * k for k in range(4))
        b = np.vstack([np.ones(3) * k for k in range(4)])
    ''')
    api = _by_stage(scan(tmp_path)[0], "api")
    assert [(f.level, f.line) for f in api] == [(WARN, 3)]
    assert "generator" in api[0].message


def test_copy_false_on_a_buffer_is_quiet(tmp_path):
    _write(tmp_path, "b.py", '''
        import numpy as np
        def f(shared_buffer, x):
            a = np.array(shared_buffer, dtype="B", copy=False)
            b = np.array(x, copy=False)
            return a, b
    ''')
    api = _by_stage(scan(tmp_path)[0], "api")
    assert [f.line for f in api] == [5]


def test_cell_centred_linspace_is_quiet(tmp_path):
    _write(tmp_path, "c.py", '''
        import numpy as np
        def axis(dmin, dmax, dn, cells):
            if cells:
                dd = (dmax - dmin) / dn
                return np.linspace(dmin + dd / 2.0, dmax - dd / 2.0, dn)
            return np.linspace(dmin, dmax, dn)
    ''')
    assert not _by_stage(scan(tmp_path)[0], "grid")


def test_lowercase_py3_branch_is_not_a_missing_name(tmp_path):
    _write(tmp_path, "v.py", '''
        import sys
        py3 = sys.version_info[0] == 3
        if py3:
            val = input("x: ")
        else:
            val = raw_input("x: ")
    ''')
    assert not _by_stage(scan(tmp_path)[0], "names")


def test_unparseable_loose_script_is_a_note(tmp_path):
    (tmp_path / "misc").mkdir()
    _write(tmp_path, "misc/old.py", "print 'hello'\n")
    _write(tmp_path, "pkg.py", "print 'hello'\n")
    names = {f.path.replace("\\", "/"): f.level for f in _by_stage(scan(tmp_path)[0], "names")}
    assert names == {"misc/old.py": NOTE, "pkg.py": WARN}


def test_fitted_coefficients_and_standard_atmosphere_are_not_constants(tmp_path):
    _write(tmp_path, "fit.py", '''
        def f(x):
            return 1.2 + 2.71439 * x + 0.3 * x**2 + 0.01 * x**3 + 0.002 * x**4
    ''')
    _write(tmp_path, "coesa.py", '''
        """1976 US Standard Atmosphere."""
        coesaRu = 8.31432
    ''')
    _write(tmp_path, "gas.py", "R = 8.31432\n")
    consts = {f.path for f in _by_stage(scan(tmp_path)[0], "constants")}
    assert consts == {"gas.py"}


def test_snippet_folder_is_one_note(tmp_path):
    (tmp_path / "tut").mkdir()
    _write(tmp_path, "tut/a.py", "import numpy as np\ndef make(n):\n    return np.eye(n)\n")
    _write(tmp_path, "tut/b.py", "S = make(3)\nprint(helper(S))\n")
    _write(tmp_path, "tut/c.py", "def helper(x):\n    return x\nprint(make(2), S)\n")
    _write(tmp_path, "tut/d.py", "S = make(4)\nprint(helper(S))\n")
    names = _by_stage(scan(tmp_path)[0], "names")
    assert [f.level for f in names] == [NOTE] and "snippets" in names[0].message


def test_download_at_import_is_a_note(tmp_path):
    _write(tmp_path, "d.py", '''
        from urllib.request import urlretrieve
        urlretrieve("https://example.org/bin", "bin")
        def later():
            urlretrieve("https://example.org/x", "x")
    ''')
    api = _by_stage(scan(tmp_path)[0], "api")
    assert [(f.level, f.line) for f in api] == [(NOTE, 3)]


def test_probe_call_copies_array_inputs():
    import numpy as np
    from physverify.probes import _Fn
    import ast
    def step(u):
        u += 1.0
        return u
    node = ast.parse("def step(u): pass").body[0]
    f = _Fn("step", step, node, None)
    u = np.zeros(3)
    y1, _ = f.call({"u": u})
    y2, _ = f.call({"u": u})
    assert np.all(u == 0) and np.all(y1 == 1) and np.all(y2 == 1)
