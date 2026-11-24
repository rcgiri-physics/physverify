"""Stable IDs for the patterns `physverify scan` reports.

An ID never changes meaning and is never reused: a rule that is dropped keeps its number, and a rule whose
meaning changes gets a new one. Ignore comments, baseline files and SARIF output refer to these IDs.
The hundreds digit is the stage: 1 tables, 2 grid and pairs, 3 constants, 4 names, 5 api, 6 literals,
7 units, 8 flow, 9 the probes of `scan --run`. docs/scan-rules.md describes each rule.
"""

from __future__ import annotations

from typing import NamedTuple


class Rule(NamedTuple):
    id: str
    name: str
    stage: str
    summary: str


_TABLE = [
    ("PV101", "rk-table-literal", "tables", "a Runge-Kutta table written as literals fails its claimed order or stability"),
    ("PV102", "rk-table-code", "tables", "a stepper whose stages are written as code fails its claimed order"),
    ("PV201", "linspace-spacing", "grid", "a spacing that differs from the spacing of the linspace grid it belongs to"),
    ("PV202", "inverse-pair", "pairs", "two functions whose names say they are inverses; worth a round-trip check"),
    ("PV301", "near-constant", "constants", "a number close to, but not equal to, a physical constant"),
    ("PV302", "many-constants", "constants", "so many near-constants that the file is most likely data"),
    ("PV401", "undefined-name", "names", "a name used but never defined or imported; NameError when reached"),
    ("PV402", "host-names", "names", "many undefined names, most likely provided at run time by a host program"),
    ("PV403", "annotation-only-name", "names", "a name used only in annotations and never defined; NameError on Python 3.13 and older"),
    ("PV404", "parse-error", "names", "the file does not parse, so it cannot run"),
    ("PV405", "template-file", "names", "the file does not parse but looks like a template"),
    ("PV406", "snippet-folder", "names", "undefined names defined in sibling files: a folder of snippets"),
    ("PV501", "import-time-download", "api", "a download that runs when the module is imported"),
    ("PV502", "numpy-removed", "api", "a NumPy name that has been removed"),
    ("PV503", "numpy-readded", "api", "a NumPy name missing from NumPy 1.24 to 1.26"),
    ("PV504", "numpy-deprecated", "api", "a NumPy name deprecated in NumPy 2"),
    ("PV505", "array-copy-false", "api", "np.array(..., copy=False), which raises ValueError in NumPy 2 when a copy is needed"),
    ("PV506", "stack-generator", "api", "a NumPy stacking function given a generator; TypeError since NumPy 1.24"),
    ("PV507", "jax-clip-keywords", "api", "jnp.clip with a_min= or a_max=, which current JAX rejects"),
    ("PV508", "scipy-removed", "api", "a SciPy name or module that has been removed"),
    ("PV509", "python-removed", "api", "a module removed from the Python standard library"),
    ("PV601", "exponent-typo", "literals", "1e0 - 5 and the like: the operator was probably meant inside the number"),
    ("PV602", "xor-power", "literals", "x ^ 2: ^ is exclusive or in Python, not a power"),
    ("PV603", "indexed-literal", "literals", "a literal indexed with a tuple or string; a comma or name is probably missing"),
    ("PV604", "called-literal", "literals", "a literal that is called; a comma is probably missing"),
    ("PV605", "nan-comparison", "literals", "== or != with NaN, which is never or always true"),
    ("PV701", "unit-dimension", "units", "a value whose dimension differs from the unit named next to it"),
    ("PV801", "maybe-unbound", "flow", "a local assigned only inside an if and read after it; UnboundLocalError"),
    ("PV802", "array-alias", "flow", "b = a makes the same array; a is changed in place and b read afterwards"),
    ("PV803", "one-sided-spacing", "flow", "a west/south coefficient that uses only east/north spacings"),
    ("PV804", "numba-scipy", "flow", "an eagerly compiled numba function that calls SciPy; TypingError at import"),
    ("PV805", "factorial2-minus-one", "flow", "factorial2(2n - 1) at n = 0, which current SciPy returns as 0"),
    ("PV806", "int-step-count", "flow", "int(t_end / dt) truncates, so the run can stop one step early"),
    ("PV901", "dead-argument", "deadargs", "changing an argument leaves the result unchanged"),
    ("PV902", "nonfinite-edge", "edges", "an edge input gives NaN or inf without an error"),
    ("PV903", "branch-jump", "branches", "the result jumps where the code switches formula"),
    ("PV904", "roundtrip-mismatch", "roundtrip", "two functions named as inverses do not undo each other"),
    ("PV905", "sibling-mismatch", "siblings", "two versions of one computation differ"),
    ("PV906", "option-mismatch", "siblings", "two options of one function give different answers"),
    ("PV907", "known-mismatch", "known", "a function named as a known operation matches none of its definitions"),
    ("PV908", "not-monotone", "monotone", "a result that should rise or fall with an input does not"),
    ("PV909", "test-import-error", "smoke", "the project's own test file does not import under pytest"),
    ("PV910", "script-error", "smoke", "a script stops with an error"),
]

RULES: dict[str, Rule] = {r[0]: Rule(*r) for r in _TABLE}
