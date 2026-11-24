# Scan rules

Each pattern `physverify scan` reports has a stable ID, shown in brackets in the text output and as `rule` in the JSON.
An ID never changes meaning and is never reused. The hundreds digit is the stage.

False alarms were measured per stage, not per rule, on the corpus rescan of 2026-10-24 (physverify 0.5.0;
[results/corpus/FEATURES.md](https://github.com/rcgiri-physics/physverify/blob/main/results/corpus/FEATURES.md)).
The counts describe that sample only. Rules added later have no measurement yet.


## `tables`

Corpus: every WARN checked by hand: all 13 real (10 known defects in 3 repositories).

| ID | Name | Looks for |
|---|---|---|
| PV101 | `rk-table-literal` | a Runge-Kutta table written as literals fails its claimed order or stability |
| PV102 | `rk-table-code` | a stepper whose stages are written as code fails its claimed order |

## `grid`

Corpus: every WARN checked by hand: 8 real, 1 benign.

| ID | Name | Looks for |
|---|---|---|
| PV201 | `linspace-spacing` | a spacing that differs from the spacing of the linspace grid it belongs to |

## `pairs`

Corpus: NOTE only; a sample of 30: 18 plausible inverse pairs.

| ID | Name | Looks for |
|---|---|---|
| PV202 | `inverse-pair` | two functions whose names say they are inverses; worth a round-trip check |

## `constants`

Corpus: NOTE only; a sample of 50 notes: about 10 worth a look, about 30 coincidences.

| ID | Name | Looks for |
|---|---|---|
| PV301 | `near-constant` | a number close to, but not equal to, a physical constant |
| PV302 | `many-constants` | so many near-constants that the file is most likely data |

## `names`

Corpus: a sample of 100 undefined names: about 82 real.

| ID | Name | Looks for |
|---|---|---|
| PV401 | `undefined-name` | a name used but never defined or imported; NameError when reached |
| PV402 | `host-names` | many undefined names, most likely provided at run time by a host program |
| PV403 | `annotation-only-name` | a name used only in annotations and never defined; NameError on Python 3.13 and older |
| PV404 | `parse-error` | the file does not parse, so it cannot run |
| PV405 | `template-file` | the file does not parse but looks like a template |
| PV406 | `snippet-folder` | undefined names defined in sibling files: a folder of snippets |

## `api`

Corpus: most WARNs are real removals; only 1 of 27 repositories pinned an old NumPy or SciPy.

| ID | Name | Looks for |
|---|---|---|
| PV501 | `import-time-download` | a download that runs when the module is imported |
| PV502 | `numpy-removed` | a NumPy name that has been removed |
| PV503 | `numpy-readded` | a NumPy name missing from NumPy 1.24 to 1.26 |
| PV504 | `numpy-deprecated` | a NumPy name deprecated in NumPy 2 |
| PV505 | `array-copy-false` | np.array(..., copy=False), which raises ValueError in NumPy 2 when a copy is needed |
| PV506 | `stack-generator` | a NumPy stacking function given a generator; TypeError since NumPy 1.24 |
| PV507 | `jax-clip-keywords` | jnp.clip with a_min= or a_max=, which current JAX rejects |
| PV508 | `scipy-removed` | a SciPy name or module that has been removed |
| PV509 | `python-removed` | a module removed from the Python standard library |

## `literals`

Corpus: every WARN checked by hand: real.

| ID | Name | Looks for |
|---|---|---|
| PV601 | `exponent-typo` | 1e0 - 5 and the like: the operator was probably meant inside the number |
| PV602 | `xor-power` | x ^ 2: ^ is exclusive or in Python, not a power |
| PV603 | `indexed-literal` | a literal indexed with a tuple or string; a comma or name is probably missing |
| PV604 | `called-literal` | a literal that is called; a comma is probably missing |
| PV605 | `nan-comparison` | == or != with NaN, which is never or always true |

## `units`

Corpus: every WARN checked by hand: real.

| ID | Name | Looks for |
|---|---|---|
| PV701 | `unit-dimension` | a value whose dimension differs from the unit named next to it |

## `flow`

Corpus: added after the 2026-10-24 rescan; not yet measured on the corpus.

| ID | Name | Looks for |
|---|---|---|
| PV801 | `maybe-unbound` | a local assigned only inside an if and read after it; UnboundLocalError |
| PV802 | `array-alias` | b = a makes the same array; a is changed in place and b read afterwards |
| PV803 | `one-sided-spacing` | a west/south coefficient that uses only east/north spacings |
| PV804 | `numba-scipy` | an eagerly compiled numba function that calls SciPy; TypingError at import |
| PV805 | `factorial2-minus-one` | factorial2(2n - 1) at n = 0, which current SciPy returns as 0 |
| PV806 | `int-step-count` | int(t_end / dt) truncates, so the run can stop one step early |

## `deadargs` (needs `--run`)

Corpus: see the `scan --run` table in FEATURES.md; deadargs WARNs held no real dead argument.

| ID | Name | Looks for |
|---|---|---|
| PV901 | `dead-argument` | changing an argument leaves the result unchanged |

## `edges` (needs `--run`)

Corpus: see the `scan --run` table in FEATURES.md; deadargs WARNs held no real dead argument.

| ID | Name | Looks for |
|---|---|---|
| PV902 | `nonfinite-edge` | an edge input gives NaN or inf without an error |

## `branches` (needs `--run`)

Corpus: see the `scan --run` table in FEATURES.md; deadargs WARNs held no real dead argument.

| ID | Name | Looks for |
|---|---|---|
| PV903 | `branch-jump` | the result jumps where the code switches formula |

## `roundtrip` (needs `--run`)

Corpus: see the `scan --run` table in FEATURES.md; deadargs WARNs held no real dead argument.

| ID | Name | Looks for |
|---|---|---|
| PV904 | `roundtrip-mismatch` | two functions named as inverses do not undo each other |

## `siblings` (needs `--run`)

Corpus: see the `scan --run` table in FEATURES.md; deadargs WARNs held no real dead argument.

| ID | Name | Looks for |
|---|---|---|
| PV905 | `sibling-mismatch` | two versions of one computation differ |
| PV906 | `option-mismatch` | two options of one function give different answers |

## `known` (needs `--run`)

Corpus: see the `scan --run` table in FEATURES.md; deadargs WARNs held no real dead argument.

| ID | Name | Looks for |
|---|---|---|
| PV907 | `known-mismatch` | a function named as a known operation matches none of its definitions |

## `monotone` (needs `--run`)

Corpus: see the `scan --run` table in FEATURES.md; deadargs WARNs held no real dead argument.

| ID | Name | Looks for |
|---|---|---|
| PV908 | `not-monotone` | a result that should rise or fall with an input does not |

## `smoke` (needs `--run`)

Corpus: see the `scan --run` table in FEATURES.md; deadargs WARNs held no real dead argument.

| ID | Name | Looks for |
|---|---|---|
| PV909 | `test-import-error` | the project's own test file does not import under pytest |
| PV910 | `script-error` | a script stops with an error |
