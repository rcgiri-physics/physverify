# Changelog

## Unreleased

- **Major tag `v0`.** A workflow moves `v0` to each new release, so `uses: rcgiri-physics/physverify@v0` follows the newest 0.x version; `@v0.3.1` and other full versions stay fixed.
- **Dependabot** opens a pull request each month when an action used by `action.yml` or the workflows has a new version.

## 0.3.1 (2026-10-20)

For running physverify on every push ([docs/ci.md](docs/ci.md)):

- **GitHub Action** (`action.yml`): `uses: rcgiri-physics/physverify@<tag>` runs the spec files, fails the job when a check fails or no spec matches, writes the result table to the run's summary page and uploads the HTML report. CI runs it on Linux, Windows and macOS against the example, correct and with a seeded bug.
- **`physverify init`.** Writes a starter spec for a fixed-step ODE solver: manufactured solution, step counts for the claimed order and the exactness check filled in, the equations and a starting state left as TODO. Every check reports ERROR until the equations are written.
- **`physverify run --markdown FILE`** appends a Markdown result table (for `$GITHUB_STEP_SUMMARY`). `run` now expands glob patterns itself (`"**/verify_*.py"`), so they work in any shell, and exits 2 when a pattern matches nothing.
- **pre-commit hook** (`.pre-commit-hooks.yaml`) and **`CITATION.cff`**.

## 0.3.0 (2026-10-20)

From batches 5 and 6 of the corpus study: the 60 newest small repositories whose README says the work is complete (32 tested, 6 confirmed bugs in 5), then 20 picked because they are quick to test (16 tested, 1 confirmed bug) ([results/corpus/SUMMARY.md](results/corpus/SUMMARY.md)).

- **`studies.balance_check`.** Checks an exact budget at every resolution (total heat with insulated walls, heat gained from a known source or flux) and says when the mismatch shrinks with resolution: a scheme can converge and still not conserve. A zero-flux wall made by copying the neighbour value lost 8.5% of the heat in a real code whose own test passed.
- **Four more seeded method bugs** (`physverify.method_bugs`), each with a control: Dirichlet values written after the solve instead of inside the linear system; an insulated wall made by copying the neighbour; a source term without its factor dt; a grid spacing off by one interval (dx = W/(N-1) with N-1 interior points). All 9 bugs are caught and the 9 controls pass ([results/method_bugs.md](results/method_bugs.md)).
- **`physverify.references`.** Exact references that adapters kept writing by hand: the 2D Ising model by enumeration (up to 4x4), the classical Heisenberg chain, heat-equation modes, a moving and spreading Gaussian, the semi-infinite step solution, double-pendulum accelerations and energy, the cantilever tip, the infinite well, square-barrier transmission and the open transverse-field Ising ground energy. Each is tested against an independent computation.
- **`loaders.stub_modules`.** Stand-ins for imports a tested path does not use, including the names a `from x import y` needs (`{"sklearn.metrics": ["accuracy_score"]}`). The names are placeholders; used as decorators they return the function unchanged, so `@app.route(...)` and `@jit` leave the code usable. `load_module_from_path` and `load_definitions_from_path` take the same mapping in `stubs`.
- **`loaders.run_script`.** Runs a whole script (coursework, exported notebooks) with plotting off and returns its globals and what it printed.
- **Sandbox.** A step stopped by the time limit no longer leaves its container running (it raced the next install into the same folder); installs have their own limit, `PHYSVERIFY_DEPS_TIME_LIMIT` (default 2400 s); wheels that bundle their own OpenMP runtime (qiskit-aer) get it preloaded, which avoids "cannot allocate memory in static TLS block".

## 0.2.0 (2026-10-20)

Additions that came from testing 40 public repositories in the sandbox (`sandbox/`); 20 could be tested and 9 confirmed bugs were found in 6 of them ([results/corpus/SUMMARY.md](results/corpus/SUMMARY.md)). Each one is a pattern a real code had, or a mistake the first adapter made, and has a test in `tests/test_corpus_lessons.py`.

- **`studies.time_grid_check`.** Checks that a fixed-step run ends at `t_end` after exactly n steps. A `while t <= t_end` loop takes one extra step when t lands on `t_end` exactly (h = 0.5) and the right number otherwise (h = 0.1). An order study that compares at the time nearest `t_end` hid this.
- **`studies.backward_mms_study`.** An MMS order study run from `t_end` back to 0 with a time-dependent forcing. A code that evaluates its stages at t + h/2 while stepping backwards passes on autonomous problems but is first order here.
- **Pre-asymptotic hint in `check_order`.** When the fitted order is too low but the pairwise orders are still rising and the last one reaches the expected order, the message says to repeat with finer steps. The status is still FAIL.
- **`physverify.constants`.** Finds literals close to, but not equal to, a physical constant: π as 3.14, `g = 9`, G in au³/(M☉ yr²) given as 39.4769 (Gaussian) next to an orbital speed of 2π, which assumes 4π². It reports notes, not failures. Short literals are only noted when the name they are assigned to suggests the constant.
- **`loaders.load_definitions_from_path`.** Loads only the imports, functions, classes and named constants of a script whose top level parses argv or runs a simulation. It can also lift functions defined inside notebook cells (marimo).
- **Ising seeded bug `field_counted_twice`.** The measured energy uses -h × (sum of the 4 neighbours) / 2 per site, so the field term is -2hM. This was found in a real code. Predicted to be caught by `bookkeeping` and `moments`.
- Fixed: the `init` signature in the sampler docstring now includes `h`, as the checks call it.
- **`physverify.butcher`.** Checks a Runge-Kutta table's order exactly, from the order conditions on every rooted tree up to the claimed order plus one. It works for explicit and implicit tables and needs no test problem. Testing real packages found 3 wrong order labels in one and embedded weights that do not sum to 1 in another. The default tolerance 1e-8 accepts coefficients typed with about 10 digits and notes them.
- **More hints in `check_order`.** It says when the errors are not monotone (the leading term changes sign, or round-off is reached) and when the error is the same at every resolution, which points to something independent of the step. In a molecular-dynamics code, one pair crossing an unshifted cutoff added V(r_c) = -0.0163 to the energy whatever dt was.
- **Seeded method bugs (`physverify.method_bugs`, [results/method_bugs.md](results/method_bugs.md)).** Five bugs from real repositories that are bugs of a method rather than of one solver (an order label too high, error weights that sum to 0, backward stages on the wrong side, a `while` loop overshoot, an even-only spectral derivative), each with a bug-free control and the check meant to catch it. All 5 are caught and the 5 controls pass; the table says which older checks miss each one.
- **`studies.size_sweep_check`.** Runs a function at odd and even sizes and reports the sizes where it raises. A spectral derivative crashed for every odd grid while being exact for even ones; an order study on 16 to 128 points cannot see that.
- **`load_definitions_from_path(..., stubs=...)`** replaces missing imports (plotting, checkpointing, notebook packages) with empty modules.
- **`physverify.constants`** accepts both CODATA 2018 and 2022 values for m_e and m_p, and says to use the edition the code states.
- **Sandbox.** `deps` installs against the image's own package versions as constraints and gets a larger `/tmp`. The image has `libX11` and `libGL` for wheels such as Taichi. `fetch` leaves Git LFS files as pointer files even where LFS is marked required. `PHYSVERIFY_PASS_ENV` passes named environment variables into a run. Installs share one wheel cache (mounted only during installs), and `run` converts Git-Bash paths and checks the adapter exists before starting Docker.

## 0.1.0 (2026-10-19)

First release on PyPI.

- **Stochastic codes.** Checks for 2D Ising Monte Carlo samplers with exact references, 20 seeded bugs and a calibration study ([docs/ising.md](docs/ising.md)).
- **Audit of the author's public physics projects** ([results/own_work/SUMMARY.md](results/own_work/SUMMARY.md)).

- **Exactness (`patch`) checks for ODE codes.** Every consistent explicit Runge-Kutta method reproduces a solution linear in t exactly, so any error at all is a bug. [docs/patch.md](docs/patch.md) states the assumptions and proofs for this and for the heat-equation patch.
- **Larger benchmark.** It now has 37 seeded bugs over 5 problems. The new problems are Kepler (energy and angular-momentum invariants, orbit closure) and Sod's shock tube (exact Riemann solution, exact discrete conservation). New bugs include several that keep the scheme's order of convergence.
- **Benchmark records.** Each bug records its expected symptom, written before the run. `results/bug_catalogue.md` lists, for each bug, what is changed, the prediction and the outcome, including two predictions that turned out wrong and two bugs no check catches.
- **Comparison with plain tests.** `results/comparison.md` compares the families with plain single-run tests.
- **Reproducible tables.** The tests require the committed tables to match a fresh run.
- **Whole-trajectory MMS study.** The error is measured over the whole run, not only at the final time.
- **Scale-aware noise floor.**
- **Command line.** `physverify run` gives text, JSON (`--json`) and a self-contained HTML report (`--html`). The command also has `matrix` and `compare`.
- **pytest plugin.** Checks in `verify_*.py` files become tests.
- **Claude Code hook (`physverify hook`) and a minimal MCP server (`physverify mcp`).** The server answers both the older `initialize` handshake and the 2026-07-28 per-request protocol (`server/discover`). See [docs/agent.md](docs/agent.md).
- **SymPy-derived manufactured sources** (`physverify.symbolic`, optional extra `symbolic`).
- **Hypothesis property tests.**

## 0.0.1

- First prototype: four check families plus the heat-equation patch test, and a 22-bug benchmark over three solvers.
