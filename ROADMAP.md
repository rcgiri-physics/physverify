# Roadmap

What may come after 0.6.0. Release 0.5.0 (2026-10-24) added `physverify scan` with the Phase 1 static checks, and 0.6.0 (2026-10-26) the Phase 2 probes, `scan --run`; see the changelog. Next is Phase 3 of the scan plan below. Nothing here is promised or scheduled; the order is a rough guess at what would help users most. Suggestions are welcome as GitHub issues.


## Principles

- **Evidence before features.** Independent trial reports (see CONTRIBUTING.md) come before new check families.
- **Independence of the reference is the first concern.** Every recipe and template asks for equations written from the physics, and for a second, independent check.
- **A PASS is a bounded claim.** Every output says what was tested; [What a PASS means](docs/assumptions.md) says what was not.
- **Deepen before widening.** Numerical-method coverage grows only when it adds value for ODE/PDE time integration, convergence or conservation. Statistical (Monte Carlo) checks grow carefully: each new one with its false-alarm rate and power measured over repeated seeds.
- **Every published number is regenerable** with `python scripts/reproduce_all.py`, or says why not.

## Done in 0.5.0: the installed package holds only the checks

The benchmark and the single-repository adapters moved to `benchmark/pvbench/` (not installed). The AI-assistant parts (`physverify hook`, `physverify mcp`) stay in the package: they use only the standard library, so an extra would not make the install any smaller.

## Now: improve the tool, not the number of repositories tested

From 2026-10-23 no new corpus batches are planned. Of the 74 defects reported to authors, 14 were found by a physverify check as such and most of the rest by the test script written for each repository ([FINDINGS_BY_METHOD.md](results/corpus/FINDINGS_BY_METHOD.md)). Writing those scripts is the bottleneck, so the work now goes into checks that need no script, then into rescanning the repositories already tested: what is recovered, and what is a false alarm, within that sample only.

### Done: `physverify scan PATH` (static, runs nothing)

Near-miss constants, Runge-Kutta tables written as literals (order, row sums, error and embedded weights, claimed order from names), grid spacing against `linspace`, inverse-pair suggestions. See `docs/running/cli.md`.

### Plan: let `scan` find more of these defects on its own

Today `physverify scan` finds 18 of the 74 reported defects with no test script (9 before Phase 1). The other 65 were found by running the code (11), by a reference written for that repository (37), or by reading (12). Looking at each one, most fall into a few patterns that a general check could catch without knowing the physics. The plan adds those checks in order of defects per unit of work. Every target count below is a guess from the reports, not a result; each phase ends by measuring it.

**Phase 1: more static checks (runs nothing). Done 2026-10-23:** target about 8 more of the 74, result 9 more, for 6% more run time. Details and false alarms in [RESCAN_2026-10.md](results/corpus/RESCAN_2026-10.md).

| Check | Defects it targets |
|---|---|
| Names that are used but never defined, imports of modules that are not there, misspelt attributes (the pyflakes kind of check, without the dependency) | J420 (`wall_thicknesss`), J290 (missing imports), J157, J264 |
| APIs removed in NumPy 2 and SciPy (`np.NaN`, `np.float`, `array(..., copy=False)`, `scipy.misc`), so code that worked last year is flagged before it runs | D03, J012 |
| Suspicious literal arithmetic: `1e0 - 5` (meant `1e-5`), `x^2` on numbers, `1/2` in old integer contexts, a stray backslash at the end of a file | K17 cutoff, J147 |
| Constants against their exact definitions (astronomical unit, nautical mile, torr, the exact SI constants since 2019), and pairs of the same constant in two unit systems that disagree (h in J s and in erg s) | K51, K60 |
| A unit registry whose dimensions do not match the name (`surface tension` as J m^2) | K15 |

**Phase 2: probes that run the code, in the sandbox only (`physverify scan --run`; about two to three weeks).** Target: about 15 to 20 more. Each probe calls functions it finds with small inputs and needs no reference, only a rule that must hold. **Started 2026-10-25:** all eight probes below are in `physverify scan --run` (`src/physverify/probes.py`); the full corpus sweep in the sandbox finished 2026-10-26 (counts in [results/corpus/FEATURES.md](results/corpus/FEATURES.md)). It added only 1 of the 74 reported defects (J400), well short of the target: most of the others sit in modules that do not import in a bare clone (compiled extensions, missing packages), so installing each repository's dependencies in the sandbox is the next step. `--run` alone now runs only `smoke` and `branches`; the other six probes found no real defect and are opt-in (`--only`) until a sweep with dependencies installed shows they help. Known-answer and monotonicity are kept narrow (three operations, four named laws and stated directions), because conventions differ and most code states no direction:

| Probe | Rule | Defects it targets |
|---|---|---|
| Smoke run of every script and the project's own tests | it runs to the end; the tests import | J253, J264, J265, J147, J157 |
| Edge inputs: negative, zero, odd sizes, a body at rest | no crash and no NaN where the documentation allows the input | I12 (negative anomaly), J409 (NaN at rest), G10 (odd N), J005 |
| Dead arguments: change one argument and nothing changes | an argument the function takes must have an effect | J019 (gamma ignored), K21 (`P_delta` ignored), K16 (`mode` not passed on), K22 (`masses`) |
| Continuity at branch points: evaluate both sides of every `if x < a` boundary | a physical quantity does not jump where the code switches formula | J400 (jump at rho = d/2), J133 (sign flip at normal incidence), J192 (negative branch) |
| Siblings and options: two code paths that should agree (`MieQ` and `ScatteringFunction`, `min_*` and `max_*`, 2D and 3D) | the same answer for the same input | K55, K27 |
| Round trips for the inverse pairs the scan already lists | `inverse(forward(x)) == x` | J077-style mappings |
| Known-answer on random input: a sliding-window or binned function against a slow direct loop | the fast and slow versions agree | K18 (STA/LTA), K17 (InterRDF density) |
| Monotonicity where the physics fixes the direction (more absorption, shorter reverberation) | the sign of a derivative | K16 (`rt60_eyring`) |

**Phase 3: simulations without a spec (about three to four weeks).** Target: about 8 to 12 more.

- **Find the stepper and run it.** Functions that look like `step(state, dt)` or `solve(..., n_steps)`, run at three or more step sizes: self-convergence gives the order without an exact solution (D08 step past the end, H01 extra step, J159, J386), and an iterative solver whose residual does not follow its tolerance (J416, one Jacobi sweep).
- **Find an energy and watch it.** When the project defines `energy`, `hamiltonian` or `total_energy` next to a stepper, run both: the drift must shrink with the step at the stepper's order (J277 bounce gains energy, J408 wrong gravity term, J442 factor 2, J348 unbound orbit, J385 sign of the force, D04 field term counted twice).
- **Split systems and implicit stages** in the stage reader (position and velocity advanced side by side; DIRK stages), so the Runge-Kutta checks reach more steppers.

**Not reachable without knowing the physics.** About 20 of the 74 need a formula from the literature (a photon-sphere radius, a Regge-Wheeler potential, MHD jump conditions, a Kane-Mele term). For those the route stays a short spec, so the work there is to make specs easier: call-pattern discovery that writes a draft spec, and a declarative spec in `pyproject.toml` with the equations as text.

**How each phase is measured.**

1. Before writing a check, list the defects it is meant to catch (the tables above).
2. Run it on the whole cloned corpus (626 repositories, at the tested and the latest commits) and on the seeded-bug benchmark.
3. Check every WARN by hand; record recovered defects, new defects (confirmed by a run before any report) and false alarms.
4. Release the check only if its false alarms on this sample are few enough to read through, and say in the docs that the rules were tuned on it.
5. Update [FINDINGS_BY_METHOD.md](results/corpus/FINDINGS_BY_METHOD.md) and [RESCAN_2026-10.md](results/corpus/RESCAN_2026-10.md) with the new "found by scan alone" count.

If the targets hold, `scan` would find roughly 40 of the 74 on its own, against 18 today. Even then a clean scan will not mean correct code: the counts describe this sample only.

**Speed rule.** `physverify scan PATH` stays static (it reads the code and runs nothing), so it stays fast and safe on any code. Today a small repository takes under a second and a 200-file library about 30 s; the full corpus about 26 minutes per commit set.

- Phase 1 checks join the tree walks that already happen rather than adding their own; the expected cost is 10 to 30% more time. A check that adds more than that must say why.
- Phases 2 and 3 run the code, so they go behind `physverify scan PATH --run`, inside the sandbox for code that is not your own, with a time budget per probe (as `physverify run --budget`). A probe that runs out of time is reported as skipped, never as passed.
- Each phase reports its run time next to its detection count. A check that costs much more than it finds moves behind `--run` or is dropped.
- On the corpus, `--run` sweeps run in batches in the background, and later rescans run only for repositories with new commits.

### Test each feature on as many repositories as possible

Every check should be measured on every repository in the corpus where it applies, not only on the few where a bug was first found. For each feature:

1. **Find where it applies.** For example `check_tableau`: every repository with a Butcher table as literals, constructor keywords, class attributes or stages written as code (the scan's `tables` stage lists them; 63 tables and 47 steppers in the October rescan). For `check_order`: every repository with a stepper the scan can identify. For the statistics checks: every Monte Carlo sampler.
2. **Run the feature there,** at the tested and the latest commit, in the sandbox when it runs code.
3. **Report per feature:** how many repositories it applied to, how many it could actually run on, defects confirmed, false alarms, and run time, in [results/corpus/FEATURES.md](results/corpus/FEATURES.md), kept up to date as new repositories are added. Done for `check_tableau` and the scan stages (2026-10-24), and for the `scan --run` probes (2026-10-26).
4. **Grow the pool of repositories** for features that apply to few of them (implicit methods, Monte Carlo samplers, PDE solvers), from the untested candidate pool, with the selection rule written down first.

This shows how often each check is useful, not just that it can find a bug, and it gives each check its own false-alarm rate on real code.

### Also for `scan`

- **A declarative spec instead of Python.** A `[tool.physverify]` table in `pyproject.toml` naming the solver, its call pattern, the claimed order and the equations as text (turned into a reference with SymPy).
- **Finite-difference stencils in `scan`.** `physverify.stencils.check_stencil` now checks a table given to it; the next step is to find stencils written as literals in the source and check them without being asked.
- **More static rules, one case each so far:** an `einsum` that sums a tensor index over the tensor alone (`'..ij,..i->..i'`, almost always a typo for `..j`); `jnp.cross` on 2-vectors; `if array:` on a possibly empty array.
- **Fewer false negatives found by hand:** grid bounds written as numbers rather than names, Jupyter notebooks (read the code cells).
- **Use in CI:** rule IDs, `# pv: ignore[rule]` comments, a baseline file, SARIF output for GitHub code scanning, and a mode that scans only changed files.

## Reproducibility of the corpus results

- **Name the findings that are confirmed.** The corpus is anonymous, so its counts cannot be checked by others. Findings that the maintainer confirmed or that someone else reproduced will be listed by repository, commit, issue and one-line repro; the others stay anonymous.
- **A benchmark not written by the author.** Mutation testing on real solvers, next to the seeded bugs, and a held-out set of repositories never used to tune the scan rules.

## Must-have improvements

- **2D and 3D heat equation.** Manufactured solutions, an independent reference operator, order studies in space and time, and checks for Dirichlet, Neumann and periodic boundaries, including the corners and edges where 2D/3D codes most often go wrong. Then the same for the wave and advection-diffusion equations.
- **Whole PDE order studies from SymPy.** `physverify.symbolic` already derives source terms; the next step is to run the full study from an equation written as text.
- **IMEX / additive Runge-Kutta coupling conditions.** Check the conditions that link the explicit and implicit tables of an IMEX pair (bi-coloured trees), not only each table on its own. Also the order of embedded error estimators.
- **Stochastic checks that stop early.** Stop sampling as soon as the result is decisive, so slow Monte Carlo codes fit inside a time budget.
- **Uncertainty on the observed order.** Report the fitted order with a standard error (and the grid convergence index of Roache and Celik et al.), pick the points of the fit from the data instead of the last four, and estimate the round-off floor from the scatter, so a PASS states how sure it is.
- **Real tableaux in `check_tableau`.** Accept FSAL tables whose `A` is n by n-1 (as in SciPy's `RK45`), ship SciPy's `RK23`, `RK45` and `DOP853` tables, and add an argument for the order of the embedded error estimate.
- **Is the reference independent?** Warn when a spec's reference imports the module it checks or copies its constants; today nothing catches the mistake the docs warn about most.
- **Long-time behaviour.** A symplecticity check on the tableau (b_i a_ij + b_j a_ji = b_i b_j) and energy drift against time, to tell symplectic from dissipative integrators.
- **Units in comparisons.** Most adapter mistakes in batch 8 were units or coordinate origins. An optional units-aware comparison (via pint, when installed) that refuses to compare quantities of different dimension.

## Documentation website

Done: the site at https://rcgiri-physics.github.io/physverify/ has a page for each kind of check, each built around a small runnable example (most with a deliberate bug and the check that catches it), plus recipes, convergence-study pitfalls, the command line and an API overview. A test re-runs every example and fails if its output no longer matches the page.

Still to do:

- An API reference generated from the docstrings (mkdocstrings), in place of the hand-written overview.
- More recipes: a 1D heat code end to end, an inference code, a Monte Carlo sampler.
- Plots of convergence studies on the pages, made from the examples.

## Packaging and CI

- Test the oldest supported versions (Python 3.10, NumPy 1.24) in CI; add Ruff, a type check on the public API, and a coverage floor.
- A test that every version string (package, conda recipe, MCP registry entry, changelog) agrees.
- Submit the conda-forge recipe.

## Candidate checks from the daily corpus sessions (one case each so far)

Each was seen once in the October 2026 daily sessions. One case is not enough to build a check on; each is promoted when a second case turns up.

- **Short-run probe:** rewrite literal `tEnd`/`Nt` in a script's `main()` to small values, and set output intervals large rather than removing plot blocks, so `smoke` gets past single-file tutorial scripts that hit the time limit.
- **Time-dependent right-hand side** in a stepper probe (a driven oscillator with an exact solution): most tests use autonomous problems and miss wrong stage times.
- **Layering invariance:** splitting a homogeneous medium into identical layers must not change the answer (seismology, transfer-matrix optics, heat conduction).
- **Documented-units recipe:** integrate a spectral function and compare with its closed form (Planck's law against sigma T^4) in the units the docstring states.
- **Adjoint or Jacobian against finite differences** (with a check that the step is in the stable range); `identities.check_derivative` covers scalars, a recipe for vector models is the gap. It also tells d/d(sigma) from d/d(log sigma).
- **Source balance for heat solvers:** a uniform source in an insulated domain gives dT/dt = q/(rho c) for every solver option. Part of the 2D/3D heat family below.
- **Causality of a run difference** for wave solvers: total minus reference field is zero before the first arrival.
- **Lyapunov spectrum sum** equals the time-averaged trace of the Jacobian; **zero net flux** through a closed surface around a body in potential flow.
- **Range ends:** evaluate piecewise fits at their documented range limits and flag 0, NaN or an exception.
- **Truncated series inversion:** the round-trip error of an order-n inversion scales as a^(n+1); a recipe for perturbative codes.
- **Sandbox:** a legacy image (NumPy 1.26, SciPy 1.11, JAX 0.4.30) for repositories that need NumPy 1; `pip --prefix` installs for wheels that put files outside site-packages; a helper that registers empty parent packages for heavy optional imports.

## Later

- A small C/C++ and Fortran bridge (run a compiled solver through a command line or `ctypes` and read its output), since much physics code is not Python.
- Julia support through the same command-line route.
- A gallery of real bugs found (with the authors' permission), each with the check that found it.
