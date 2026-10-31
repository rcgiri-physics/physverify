# Changelog

## 0.7.0 (2026-10-31)

From the daily corpus sessions of October 2026 (tests in `tests/test_helpers_2026_10.py`, `tests/test_scan.py`, `tests/test_batch8_lessons.py`):

- **`identities.vary_one(test, defaults, changes)`:** reruns a test that passes at the defaults with one parameter changed at a time and names each change that breaks it. 7 of the confirmed bugs in those sessions were hidden by symmetric example values (Lx = Ly, nx = ny, zero boundary data, one polarisation).
- **`identities.check_scale(got, ref)`:** fits got = k ref and reports k when the shape is right but the size is not (a missing grid spacing, time step or factor 1/2).
- **`stencils.check_stencil`:** consistency, scale and order of a finite-difference stencil from its Taylor moments, exact for integer and Fraction weights.
- **`fluxes.check_flux`:** consistency, supersonic upwinding and mirror symmetry of a numerical flux.
- **`identities.check_vec_convention`** (row- or column-major vectorisation of a superoperator) and **`references.zernike_osa`** (OSA/ANSI normalisation).
- New docs page: Hidden defaults, scale, stencils and fluxes; more entries in Convergence-study pitfalls.
- **`scan`:** a generator passed to `np.vstack`, `np.stack` or `np.concatenate` is a WARN (TypeError since NumPy 1.24; one missed bug). Fewer false alarms: `np.array(buffer, copy=False)` on a buffer; a spacing next to a cell-centred `linspace(a + d/2, b - d/2, n)`; names used under a lowercase `py3` flag; a file that does not parse in `misc/`, `scripts/` or `examples/` is a NOTE; near-constants that are coefficients of a long fitted sum, or the 1976 Standard Atmosphere's R; a folder of snippets that use each other's names is one NOTE. New NOTE: a download that runs when a module is imported.
- **`scan --run`:** each probe call gets copies of its array inputs, so a solver that updates its arrays in place cannot change the next probe's inputs.
- **Real tableaux in `check_tableau`:** tables stored as s x (s - 1), or with an FSAL stage of weight 0, are padded first (`square_tableau`); `embedded=` and `claimed_embedded=` check the error-estimate weights (sum to 1, order), including SciPy's error weights over the extra FSAL stage; `symplectic=` checks b_i a_ij + b_j a_ji = b_i b_j (`symplectic_residual`). `butcher.TABLES` ships RK4, Bogacki-Shampine 3(2), Dormand-Prince 5(4), the implicit midpoint rule and 2-stage Gauss, and `compare_tableau` checks a code's copy against them. Tested against SciPy's RK23 and RK45.
- **Uncertainty on the observed order:** `order.fit_order_error` gives the fitted order with its standard error; `order.gci` the grid convergence index of Roache and Celik et al. from three solutions.
- **Is the reference independent?** `physverify run` prints a note when a reference-like function in a spec (`exact`, `reference`, `analytic`, `expected`, `*_ref`) uses a module the spec imports as the code under test (`physverify.specscan`).
- **Sandbox:** `importlib.metadata.version` answers `0+source` for the repository's own package in a source checkout; exit 137 is reported as the likely memory limit; `deps --clean` empties the deps folder first.

## 0.6.0 (2026-10-26)

- **New: `physverify scan PATH --run`**, the first probes of Phase 2 of the scan plan (ROADMAP.md). They call the code, so use them on trusted code or in the sandbox: `smoke` (scripts run to the end, the project's tests collect), `deadargs` (an argument that changes nothing), `edges` (silent NaN at zero, negative or odd-size inputs), `branches` (a jump where `if x < a` switches formula) `roundtrip` (inverse pairs), `siblings` (two versions of one computation, and `method=` options, that should agree), `known` (cumulative trapezoid integrals, running means and autocorrelations against a slow direct loop) and `monotone` (the direction a named law or the docstring fixes). Each file is probed in its own process with `--timeout`; anything that runs out of time is SKIP, not passed. Tests in `tests/test_probes.py`. Measured on all 626 corpus repositories in the sandbox (results/corpus/FEATURES.md): `smoke` found scripts that stop on errors in their own code, `branches` J400's jump; the other six found no real defect, so `--run` alone runs only `smoke` and `branches`, and the rest are experimental, run with `--only`.
- **Related work and credits** (`docs/related-work.md`): the methods physverify is built from (Salari and Knupp, Roache, Oberkampf and Roy, the order conditions of Butcher and Hairer, Nørsett and Wanner) and the tools that overlap with it, NodePy first.
- `pyproject.toml` settings are read on Python 3.10 too (`tomli` when `tomllib` is missing); before, specs listed there were silently skipped on 3.10.
- The version test also covers the CI docs, the MCP registry entry and the CHANGELOG.

## 0.5.1 (2026-10-25)

- **Security fix (GCVE-110-VULN-PYPI-2026-000391, CWE-829):** `physverify hook` does nothing for an edit outside the session folder and never looks above it for the project root; `specs` entries in `[tool.physverify]` that leave the project root are dropped. Before, an assistant's edit in an untrusted folder ran that folder's `verify_*.py`. See `SECURITY.md`.
- **`physverify.scan.extract_tables(path)`:** every Runge-Kutta table the scan finds, with A, b, c, the claimed order and where the claim comes from, embedded and error weights; `scan --json` includes the same data. For checks the scan does not make itself, such as `check_tableau`'s stage order or stability claims.
- `results/corpus/FEATURES.md`: each feature measured on every corpus repository where it applies (`check_tableau`, stability and embedded-order claims, and every scan stage, with samples checked by hand).
- **Fewer false alarms in `scan`**, from those samples: constants with units are noted within 1% (was 10%), long numeric tables and files with more than 20 near-constants are summarised, the atomic mass unit and the neutron mass are known constants, and R has its exact value; `test_*` functions are not listed as inverse pairs; a file with six or more undefined names and no usual module alias is one NOTE (names injected by a host program); a spacing next to its own `linspace(..., endpoint=False)` is not paired with grids elsewhere; `distutils` imports are a NOTE, since setuptools still provides the module.

## 0.5.0 (2026-10-24)

**New: `physverify scan PATH`**, checks that need no spec file and run nothing (the source is only parsed). Stages: near-miss constants; Runge-Kutta tables written as literals (true order from the order conditions, row sums against `c`, error weights that must sum to 0, embedded weights, and the order a name or docstring claims); grid spacings that do not match their `linspace` grid, compared by substitution so `W/(N-1)` with `linspace(0, W, N+1)` is caught, within a file (WARN) and across files (NOTE); and inverse function pairs to round-trip. `--only`, `--json`; exit 1 on any WARN. Order claims are read from names (`rk4`, `heun3`), docstrings (`3rd order`) and `order = N` / `def order(self): return N`. Runge-Kutta stages written as code are read back into a table (each call of the right-hand side is a stage, every other expression a linear combination) and checked for order, stage times, a missing `h`, weights that sum to neither 1 nor 0, and against a Butcher table drawn in the docstring. Tables are also read from constructor keywords (`ButcherTableau(a=..., b=..., b_error=..., order=5)`), dicts, `torch.tensor`, classes that inherit their table from a base class, `A = np.zeros((s, s))` with `A[i, :k] = [...]`, and `b = A[-1]`; a stated `orderEmbedded` is checked against the embedded weights. On the corpus it recovers 18 of the 74 reported defects with no adapter and found 7 new ones, each confirmed by a run; see `results/corpus/RESCAN_2026-10.md`. Further stages in `physverify.lint`: names used but never defined (and files that do not parse), features removed from NumPy 2, SciPy and Python, typo-like literals (`1e0 - 5`, `x ^ 2`, `x == np.nan`), and unit tables whose dimension does not match the name; constants now include values fixed by definition (astronomical unit, torr, nautical mile, the SI 2019 constants in SI and CGS). Tests in `tests/test_scan.py`.

**Documentation and community:** a Start here page for readers new to Python tools, with a prompt to paste into an AI assistant; `AGENTS.md` for assistants that check projects or work on physverify; `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SUPPORT.md`, a question issue template and a pull-request template; `results/corpus/FINDINGS_BY_METHOD.md`, which says for each reported defect whether a physverify check, a plain run, the per-repository script, or code reading found it.

**Changed: the installed package holds only the checks.** The seeded-bug benchmark (`problems`, `matrix`, `compare`, `method_bugs`, the Ising matrix) and the adapters written for single corpus repositories moved from `src/physverify/` to `benchmark/pvbench/`, which is in the repository but not installed; the wheel shrank to 34 files (80 KB). The `physverify matrix` and `physverify compare` commands are removed: regenerate the tables with `python scripts/reproduce_all.py`, or run `PYTHONPATH=src:benchmark python -m pvbench.matrix` from a checkout. The tables are unchanged except for the source paths in the bug catalogue. Imports of `physverify.problems`, `physverify.adapters`, `physverify.matrix`, `physverify.compare`, `physverify.method_bugs` and `physverify.stochastic.matrix` become `pvbench.*`; none of them was public API.

From batch 8 of the corpus study (50 widely used libraries, tested in the sandbox). Each item has a test in `tests/test_batch8_lessons.py`.

- **`physverify.identities`:** checks that need no exact solution. `check_agree` (two code paths that must give the same answer), `check_roundtrip` (`inverse(forward(x)) == x`), `check_derivative` (an analytic derivative against finite differences, with one Richardson step), `check_identity` and `check_unitary`, plus `fd_derivative` and `laplacian_fd`. They handle complex values and report non-finite values as FAIL. New docs page: Identities and round trips.
- **`loaders.extract_functions(path, names)`:** loads named functions from a file that cannot be imported as a whole, together with the same-file helpers they use (followed transitively); each failing import is skipped and listed.
- **Sandbox:** the runner writes a placeholder for a missing setuptools-scm / hatch-vcs version file (`pkg/_version.py`) in the copy and reports it (`PHYSVERIFY_NO_VERSION_STUB=1` turns it off). `sandbox.py build --stack latest` builds a second image with the newest NumPy and SciPy; select it with `PHYSVERIFY_IMAGE=physverify-sandbox:latest-stack`, and its packages go to their own deps folder.
- **`check_order(..., atol=...)`:** an accuracy requirement on the finest grid, reported apart from the order: when the order is as claimed and only `atol` fails, the message says so and how much smaller the steps would need to be.
- **`studies.decay_rate`:** exponential decay rate that skips the start-up transient, found automatically from where the local rate settles, or from `t_skip`.
- **`studies.residual_check`:** an iterative solver asked for tolerance tol returns a residual of about tol; a residual that does not follow the tolerance points to a solver that does almost no work (a real pressure solver did one Jacobi sweep).
- **`loaders.load_repaired`, `repairs_note`:** import a file that does not run as published, after recorded text replacements, so a PASS on repaired code is reported as one.
- **Sandbox:** when `deps` fails because a package needs another NumPy or SciPy than the pinned image, it says which and suggests the latest-stack image.
- **Troubleshooting:** the reference mistakes made while testing libraries (units, coordinate origins, deliberate standards, limits, remembered constants, operator precedence), and the rule that a suspicion from reading code is reported only after a run confirms it.

## 0.4.2 (2026-10-22)

- **Documentation site** (MkDocs, published on GitHub Pages): a page per kind of check built around a small runnable example, recipes, convergence-study pitfalls, the command line and an API overview. `tests/test_docs_examples.py` re-runs every example and fails if its output no longer matches the page. `pip install physverify[docs]` installs the tools to build it.
- The text summary counts skipped checks ("0 of 2 checks passed, 1 skipped").
- Releases run the full test suite before uploading to PyPI.
- Citation: DOI 10.5281/zenodo.23534512 (all versions) and ORCID in `CITATION.cff`.
- **`physverify demo`:** runs the checks on a correct and on a broken example solver shipped in the package, so a first run needs only `pip install physverify`.
- **What a PASS means:** every report (text, Markdown, HTML, JSON) ends with "A PASS means these checks found nothing wrong; it does not prove the simulation correct." A new docs page lists what each check family assumes, with a worked example in which a reference copied from the code passes and an energy check catches the bug; `physverify init` and the recipes carry a short checklist.
- **JSON output:** new fields `schema_version` (1), `note`, and per check `claim` and (order studies) `acceptance`, the rule a PASS had to meet. The public API and the JSON layout are documented in `docs/api.md`.
- **Clearer verdicts on awkward input:** `check_order` reports INCONCLUSIVE, instead of a misleading FAIL or a crash, when all step sizes are equal, when a step size is zero, negative or NaN, or when there are not as many errors as step sizes. `physverify run` exits 2 when a spec's `checks()` returns no checks, instead of reporting "0 of 0 checks passed".
- **Benchmark as data:** `physverify matrix` also writes `detection_matrix.json` (full status, message, prediction and run time of every check, with the physverify version, git commit, Python, NumPy and platform) and `run_time.md`. The matrix says how many bugs were flagged by a FAIL and how many only by INCONCLUSIVE or ERROR (35 and 0). The bug catalogue links to the lines that switch each bug on. `python scripts/reproduce_all.py` regenerates every table and the README figure; see `results/README.md`.
- **CI:** builds the wheel and runs `physverify` from it in a clean environment (also before every release); tests Python 3.10 to 3.14 with coverage; runs the slow Monte Carlo tests weekly.
- Shorter README with the demo, a convergence plot, a diagram of the check loop and the GitHub Action snippet near the top; the docs home page takes its version number from the package.
- **Help wanted:** CONTRIBUTING.md lists what help is most useful (trial reports, blind tests, seeded bugs written by others, adapters), with a trial-report issue template. New Troubleshooting page: "is it my code or my spec?", common messages, and the adapter mistakes recorded in practice.
- **Release gates:** the docs must build with `--strict` in CI; a release fails if its tag does not match the package version; a test requires the version to agree in `pyproject.toml`, `CITATION.cff`, the README and the docs.
- ROADMAP.md states the project's principles: evidence before features, independence of the reference first, deepen before widening.

## 0.4.1 (2026-10-21)

- Shorter description in `action.yml` (the GitHub Marketplace allows at most 125 characters), so the action can be listed there. No change to physverify itself.

## 0.4.0 (2026-10-21)

From batch 7 of the corpus study: 450 repositories, 182 tested, at least one confirmed defect in 41 ([results/corpus/BATCH7.md](results/corpus/BATCH7.md)). Each item has a test in `tests/test_batch7_lessons.py`.

- **`physverify smoke PATH`** (`physverify.smoke`). Compiles each script and runs it in its own process with a time limit, stdin closed and plotting off; reports parse errors, crashes, scripts that wait for input and NaN/overflow warnings. Three batch-7 repositories did not parse and several crashed before any physics could be checked. It runs the code, so use it on trusted code or inside the sandbox.
- **`physverify references`** lists the exact references. New references: `morse_levels`, `morse_turning_width`, `schwarzschild_qnm` (fundamental modes for scalar and gravitational fields), `kerr_isco`, `schwarzschild_deflection` (exact integral, numpy only), `inhour_stable_period` (either sign of reactivity; a real code used Λ/ρ for negative ρ, off by about 7000 times). Each is tested against an independent computation (finite-difference eigenvalues, turning points, orbit integration, the circular-orbit energy minimum, point-kinetics eigenvalues).
- **`studies.damped_sinusoid_fit`.** Complex frequency of a ringdown from a two-pole Prony fit, no starting guess; the window should start after the direct pulse has passed.
- **`check_order(..., tol=...)`** sets both tolerances (an adapter that wrote `tol=` failed with a TypeError after its whole run). INCONCLUSIVE and "does not decrease" results now say when the errors are already near round-off and coarser resolutions are needed.
- **`loaders.run_script(..., inputs=[...])`** answers `input()` prompts in order; a prompt with no answer left raises EOFError instead of waiting.
- **Butcher tables: linear order, stage order, stability** (`physverify.butcher`), after a maintainer of a Runge-Kutta library asked to test their tables in CI. `linear_order` is the order on y' = λy (where R(z) matches e^z), which a Dahlquist convergence test measures and which can be higher than the order: a real table labelled order 3 was order 2 with linear order 3. `stage_order` (C(q) and B(q)), `stability_function`, `r_infinity`, `a_stability_margin` (the E-polynomial on the imaginary axis plus the poles of R) and `is_stiffly_accurate`. `check_tableau` takes `claimed_linear`, `claimed_stage`, `a_stable`, `l_stable` and `stiffly_accurate`, and notes when the linear order exceeds the order. Tested against Gauss, Radau IIA, SDIRK, the trapezoid rule and RK4 (`tests/test_butcher_properties.py`).
- **`check_tableau(A, b, c)` fails when the row sums of A differ from c** (it was only a note). The order conditions use A and b only, so a wrong node, which shifts the stage times on non-autonomous problems, was invisible to them.
- **`check_tableau`** says when a failed order is only a matter of coefficients typed with too few digits (a Ralston table typed to 8 digits).

- **SKIP status.** `requires("shapely")` or `raise SkipCheck(reason)` inside a check reports SKIP: neither a pass nor a failure, counted separately in every report, and a pytest skip under the plugin. A check that returned PASS with "not run" when an optional dependency was missing had been counted as a pass (J351).
- **Time budget per check.** `Check(..., budget_s=...)` or `physverify run --budget SECONDS`. Order studies stop adding resolutions when the next one would overrun the budget and fit what they have, saying so in the message; a check still running at twice its budget is reported INCONCLUSIVE and the later checks still run. Slow pure-Python codes had used up a 900 s container limit and lost their later checks (J261, J154).
- **`studies.trajectory_order_study`.** An order study from whole trajectories compared at one fixed time. It fails when a run has no sample at that time (a loop over `int(t_end / h)` steps stops one step short, which made an order-4 method look first order, J348) and notes when the time is a whole number of periods, where phase errors can cancel (a symplectic Euler showed order 2, J155).
- **`studies.coverage_check`.** Frequentist coverage of an inference code by an exact binomial test, with the truth drawn from a required prior sampler: drawing it from a narrower range than the analysis prior gave a spurious coverage of 0.865 for a 0.68 interval (J399).
- **Sandbox: writable copy and Python 3.14 shim.** `sandbox.py run` now copies the clone to a writable `/tmp/repo` (`$PHYSVERIFY_REPO`) for each run and reports files the code writes into its own directory as a portability note (J012 wrote a cache into its package; J265 wrote into a folder that did not exist); `--read-only-repo` keeps the old read-only mount. `--py314-shim` adds `from __future__ import annotations` to each file of the copy, for code written for Python 3.14's lazy annotations (J320, J343).

- **Major tag `v0`.** A workflow moves `v0` to each new release, so `uses: rcgiri-physics/physverify@v0` follows the newest 0.x version; `@v0.4.0` and other full versions stay fixed.
- **Dependabot** opens a pull request each month when an action used by `action.yml` or the workflows has a new version.

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
