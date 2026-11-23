# physverify: technical details

The full reference: check families, the seeded-bug benchmark, the Ising checks, limits and related work. For a plain introduction see the [README](../README.md).

## What it does

You describe the physics once, independently of the code under test (a reference right-hand side). physverify then runs five kinds of check:

| Family | What it does | What it can see |
|---|---|---|
| `mms` | Method of Manufactured Solutions. Picks a smooth function, derives the forcing that makes it an exact solution of the reference equations, runs your code with that forcing, and checks the error shrinks at the design order. | A wrong right-hand side anywhere in the state space you sample, and a stepper that is not the order it claims. |
| `reference` | Compares your code with a solution of the reference equations computed independently. | The same bugs, but only along the one trajectory you run. |
| `invariant` | Drift of a conserved quantity (energy, say) as the step shrinks. | Inconsistency between the equations of motion and the conserved quantity. |
| `limit` | A known limiting case: closed-form range, normal-mode frequencies. | Bugs in post-processing or in limits the other checks do not reach. |
| `patch` | A manufactured solution that lies inside the scheme's discrete solution space (for example cubic in x and linear in t for a three-point stencil with forward Euler), so a correct code reproduces it to round-off for any grid and step. | An error that is as small as the scheme's own truncation error and shrinks at the same rate, which every order-of-convergence check accepts. Available for every explicit Runge-Kutta ODE code (a solution linear in t) and for the heat solver; see [docs/patch.md](patch.md). |

Pass/fail rests on the observed order of convergence (`physverify.order.check_order`), which reports PASS, FAIL, EXACT (error at round-off, order not measurable) or INCONCLUSIVE. A check whose optional dependency is missing reports SKIP, which is neither a pass nor a failure.

## Try it

Only NumPy is needed (pytest to run the tests). Install from the folder, or run from source with `PYTHONPATH=src`:

```bash
pip install -e .            # add [symbolic] for the SymPy helpers, [dev] for the test dependencies
```

It is on PyPI: `pip install physverify`.

Write a spec file that defines `checks()`; [examples/verify_damped_oscillator.py](../examples/verify_damped_oscillator.py) checks the solver in [examples/damped_oscillator.py](../examples/damped_oscillator.py). You provide an independent reference right-hand side and an `integrate(source, y0, t_end, n_steps)` function that advances your code with an additive source term `source(t)`. Codes with no source hook can still be wrapped; see `benchmark/pvbench/adapters/projectile_v2.py` for one that has no time argument either.

Then any of:

```bash
physverify run examples/verify_damped_oscillator.py                 # text; exit code 1 if any check fails
physverify run examples/verify_damped_oscillator.py --json -        # JSON on stdout
physverify run examples/verify_damped_oscillator.py --html report.html   # self-contained page with convergence plots
pytest examples/verify_damped_oscillator.py                         # each check is a pytest test (plugin installed with the package)
```

Without installing, use `python -m physverify` for `physverify` and `pytest -p physverify.pytest_plugin` for pytest. Once the package is installed, plain `pytest` is enough; adding `-p physverify.pytest_plugin` as well makes pytest stop with "Plugin already registered". Change the damping in `examples/damped_oscillator.py` by 10% and every family flags it.

For an AI coding assistant there is a Claude Code hook (`physverify hook`, runs the checks after each edit and reports failures back) and a minimal MCP server (`physverify mcp`); see [docs/agent.md](agent.md).

The benchmark and the test suite:

```bash
python scripts/reproduce_all.py                 # the seeded-bug tables below, and the comparison with plain unit tests
python -m pytest -q                             # about 2 minutes
```

## Seeded-bug benchmark

37 bugs are injected one at a time into five small solvers: a projectile with drag, a double pendulum, the Kepler problem, the 1D heat equation and Sod's shock tube (1D Euler equations). Every check is run on each bug. The results are in four files:

- [results/detection_matrix.md](../results/detection_matrix.md): the full table.
- [results/bug_catalogue.md](../results/bug_catalogue.md): for each bug, the change, the expected symptom, the predicted checks and the observed checks.
- [results/detection_matrix_details.md](../results/detection_matrix_details.md): the message from every check.
- [results/heat1d_by_check.md](../results/heat1d_by_check.md): a separate table for the heat solver, whose checks refine the step and the grid in different ways.

| | Count |
|---|---|
| Bugs seeded | 37 |
| Flagged by at least one check | 37 |
| Missed by every check | 0 (the last two, in the Sod solver, were closed by checks added for them; see below) |
| False alarms on the 5 bug-free baselines | 0 |
| Flagged by `mms` / `reference` / `invariant` / `limit` / `patch` | 27 / 28 / 22 / 14 / 27 |
| Flagged by one family alone | `reference` 2, `invariant` 2, `limit` 2, `patch` 3, all others 0 |

**Reproducing it.** The checks are deterministic. `tests/test_seeded_bugs.py` reruns every check and requires that `detection_matrix.md` and `bug_catalogue.md` match the committed files exactly. Two commands regenerate the tables:

```bash
PYTHONPATH=src:benchmark python -m pvbench.matrix results/detection_matrix.md
PYTHONPATH=src:benchmark python -m pvbench.compare results/comparison.md
```

**Against ordinary tests.** [results/comparison.md](../results/comparison.md) runs the same 37 bugs through four strategies. "Plain tests" means one run per case, compared with a reference or a known value within a tolerance: 0.1% for the ODE problems, 1% for the heat solver, and 5% in L1 for Sod.

| Strategy | Bugs caught | False alarms | Runtime on the author's laptop |
|---|---|---|---|
| plain tests | 27 of 37 | 0 of 5 | 26 s |
| `reference` only | 28 of 37 | 0 of 5 | 42 s |
| `mms` only | 27 of 37 | 0 of 5 | 23 s |
| all five families | 37 of 37 | 0 of 5 | 76 s |

The plain tests missed ten bugs. Most only show on forced or backward-moving runs, are small (a 0.1% range error, gravitational softening), or keep the scheme's order. A tighter tolerance would catch more of them. The difficulty is choosing it: the order studies need no tolerance on the error itself, only on the order.

How to read this:

- **Same author.** The bugs and the checks were written by the same person (the author). The predicted detections and symptoms come from reasoning, not from tuning. This measures these 25 bugs. It is not an estimate of how many real-world bugs would be caught.
- **`mms` and `reference` overlap heavily.** `mms` sees two bugs that `reference` does not:
  - `quad_drag_abs_vx` is wrong only when the projectile moves backwards, and a single forward trajectory never reaches it.
  - `rk4_stage4_time` is visible only when the right-hand side depends on time, and the free pendulum does not.
- **`limit` catches two bugs nothing else does.** These are the landing point not being interpolated and the launch angle not being converted to radians. Both live in the code around the integrator, not in it.
- **`patch` catches three bugs alone.** Each one adds an error of the same order as the scheme's own, so every order-of-convergence check accepts it:
  - `heat1d/extra_time_step`
  - `heat1d/source_time_shift`
  - `projectile/euler_extra_step`
- **Not independent evidence.** The heat patch test was added after `extra_time_step` was the one miss in the first version of the table. The ODE patch test and the other two order-preserving bugs were added together, after the heat result. So these three detections are not independent evidence. They show that the mechanism works as designed. [docs/patch.md](patch.md) states exactly what the patch check assumes and proves.
- **Sod: two predictions were wrong, and two bugs were missed until checks were added for them.** The predictions and symptoms were written before the checks were run, and the catalogue records where they turned out wrong:
  - `nonconservative_momentum` was predicted to fail the Sod reference check. Its observed order fell from 0.63 to 0.43, still inside the wide band a discontinuous solution needs, so only the conservation check flags it.
  - `wave_speed_without_sound` (Rusanov dissipation without the sound speed) was predicted to oscillate. On Sod's problem it stayed stable and was slightly more accurate, so the first checks missed it. An acoustic wave in a fluid at rest now exposes it: with u = 0 the dissipation vanishes and the scheme is unstable.
  - `reflective_boundary` cannot show before a wave reaches a boundary, and none does in Sod's problem by the measurement time. An acoustic pulse sent out through the open end now exposes it.
  - These two checks were written after the two bugs were known to be missed, so like the patch tests above they are not independent evidence; they show that a problem chosen for the mechanism finds it.
- **Order studies on discontinuous solutions are weak.** Sod's L1 order is only known to lie between about 0.5 and 1. That band is too wide to catch a change from 0.63 to 0.43. The exact conservation check is the stronger test there.
- **A built-in blind spot, shown on purpose.** A manufactured solution built from the code's own right-hand side hides a wrong right-hand side. `tests/test_mms.py` demonstrates this.

## Stochastic codes: the 2D Ising model

Monte Carlo codes have no step size and give random output, so they need a different kind of check. `physverify.stochastic` implements the [design notes](https://github.com/rcgiri-physics/physverify/blob/main/docs/plan_ising.md); [docs/ising.md](ising.md) describes the interface and the checks.

- **Exact references.** These are complete enumeration (L up to 5), Kaufman's finite-torus partition function, and Onsager's infinite-lattice energy. The three routes were cross-checked against each other first: log Z agrees to about 1e-15, and the energies agree to 1e-11 away from T_c.
- **Checks.** Three are exact:
  - `bookkeeping`: tracked energy against the lattice;
  - `scripted_rng`: the code's sweeps against a trusted reference replaying the same random numbers;
  - `reproducibility`.

  Six are statistical, each with a false-alarm rate of 0.001: exact energy and \|m\| distributions, moments, the acceptance rule, symmetry, equilibration and reported error bars.
- **Seeded bugs.** There are 21 bugs plus one equivalent mutant over four algorithms: Metropolis, heat bath, checkerboard and Wolff. The predictions for the first 20 were committed before any bug was run; `field_counted_twice` was added later, after it turned up in a real code. All 21 bugs are flagged, and none of the 4 bug-free samplers fails. 76 predicted detections happened, 1 did not, and 11 happened unpredicted. See [results/ising_matrix.md](../results/ising_matrix.md) and [results/ising_scorecard.md](../results/ising_scorecard.md).
  - **Equivalent mutant.** It rejects moves with dE = 0, which keeps the correct distribution. The dynamics checks catch it and the distribution check does not, as intended. These two checks were extended to h = 0 after a unit test showed they could not see it in a field, so that detection is not blind.
- **Calibration** ([results/ising_calibration.md](../results/ising_calibration.md)). This uses 1000 bug-free replicate runs.
  - At check level, the FAIL rate at alpha = 0.05 is 1.8% to 3.2%.
  - Single comparisons are rejected 4.4% to 6.0% of the time at a nominal 5%. At T_c the rate is 5.95%, slightly above nominal, so error bars there are a little small.
  - Power curves show most bugs flagged from 10 sweeps per chain on. `sweep_skips_last_row` is the exception, at 60% to 75%.
- **Limits.** All of this is on small lattices (L = 4, one comparison at L = 8). The optional scaling check is not built, and a full matrix run takes about half an hour.

## Results on two real projects

Run read-only against `projectile-simulation` and `double-pendulum-simulation` (siblings of this folder; nothing is written into them, and `git status` is clean in both afterwards).

- `projectile_sim_v2.py` (`ProjectileV2`): in vacuum, linear and quadratic drag modes, for both RK4 and Euler, the code agrees with an independent reference at the claimed order (4 and 1). Vacuum energy drift also has the right order, the error over the whole trajectory converges at the same order, and every mode reproduces the linear `patch` solution to round-off. **One finding, now fixed:** the range read from the end of `simulate()` was only first order in dt, because the landing interpolation branch tested `int(fraction) != 0` and `fraction` was between -0.08 and 0 in the three cases run (dt = 0.1, 0.01, 0.001), so it never ran. With `dt=0.01`, `v0=30`, 45 degrees, the reported vacuum range was 91.641 m against an exact 91.743 m, an error of 0.10 m. The interior trajectory points were not affected. The fix (a few lines in `simulate()`, applied and committed in that repo on 2026-10-19) interpolates the landing point linearly; the observed order of the range is now 2.00 and the error at `dt=0.01` is 1.2e-4 m. `benchmark_scipy.py` could not be re-run here (it needs SciPy and matplotlib). Separately, the README gives the linear drag coefficient as 6*pi*eta*r while the code uses a fixed 0.01 N s/m; which one is intended is not for physverify to say.
- `mechanics.py` (double pendulum): `get_derivatives` matches an independent closed-form reference, `calculate_energy` is consistent with it, the linear `patch` solution is reproduced to round-off, and the small-oscillation frequencies match the closed form. `solvers.py` was not tested because it needs SciPy, which is not installed here.

## Helpers for testing other people's code

Adapters for public repositories kept needing the same few things; they now live in the package.

- `loaders.stub_modules({"sklearn.metrics": ["accuracy_score"], "flask": ["Flask"]})` installs stand-ins for imports the tested code path does not use. The stand-in names are placeholders: calling one returns another, and used as a decorator one returns the function unchanged, so `@app.route(...)` or `@jit` leaves the code usable. Modules that import for real are left alone.
- `loaders.run_script(path, argv=..., inputs=...)` runs a whole script (coursework, an exported notebook) with plotting switched off and returns its globals and what it printed; `inputs` answers its `input()` prompts in order.
- `loaders.load_definitions_from_path` loads only the functions of a script that runs a simulation at import; its `stubs` argument takes the same names or mapping.
- `references`: the 2D Ising model by exact enumeration up to 4x4, the classical Heisenberg chain, heat-equation modes, a moving and spreading Gaussian, the semi-infinite step solution, double-pendulum accelerations and energy, the cantilever tip, the infinite well, square-barrier transmission the open transverse-field Ising ground energy, Morse levels and turning-point width, Schwarzschild quasinormal frequencies (scalar and gravitational), the Kerr ISCO, exact Schwarzschild light deflection and the inhour asymptotic reactor period. Each is tested against an independent computation in `tests/test_references.py`; `physverify references` lists them.
- `studies.balance_check`: an exact budget at every resolution, with a hint when the mismatch shrinks (a scheme can converge and still not conserve).
- `studies.damped_sinusoid_fit(t, y, t_start, t_stop)`: the complex frequency of a ringdown or any damped oscillation (two-pole Prony fit, no starting guess).
- `butcher.check_tableau(A, b, c, claimed=p, claimed_linear=..., claimed_stage=..., a_stable=..., l_stable=..., stiffly_accurate=...)`: order conditions on rooted trees, linear order (where R(z) matches e^z; a Dahlquist test measures this one), stage order, A-stability (E-polynomial and poles of R), L-stability and stiff accuracy; row sums of A must equal c.
- `studies.trajectory_order_study(runs, exact, t_compare, p, period=...)`: order from whole trajectories at one fixed time; fails when a run has no sample there (the `int(t_end / h)` loop) and notes a whole number of periods.
- `studies.coverage_check(simulate, interval, prior_sampler, level=...)`: coverage of stated intervals by an exact binomial test, with the truth drawn from the analysis prior.
- `requires("module")` / `SkipCheck`: report SKIP (neither pass nor failure) when an optional dependency is missing. `Check(..., budget_s=...)` or `physverify run --budget SECONDS`: a per-check time budget; order studies stop adding resolutions that would overrun it.
- `physverify smoke PATH`: a first stage before any physics. Each script is compiled and run with a time limit, stdin closed and plotting off; parse errors, crashes, waits for input and NaN warnings are reported. It runs the code, so use it on trusted code or inside the sandbox.

## Known limits

- ODE systems get the full treatment. The PDE examples (`heat1d`, `sod`) are 1D. `physverify.symbolic` derives PDE source terms with SymPy (optional), and the tests use it to check the hand-derived heat sources; it does not yet run a whole PDE order study for you.
- The `patch` test needs a manufactured solution the scheme reproduces exactly. Finding one is easy for a three-point stencil with forward Euler and can be hard or impossible for other schemes. The "time-only" and "grid-only" studies isolate one kind of error only to leading order: the time-stepping error is itself smoothed by the discrete Laplacian, a cross term of order dt * dx^2 (visible as about 0.1% differences between grids in `tests/test_reference_problems.py`).
- The error floor in `check_order` is 1e-12, or 1e-13 times the solution's size if that is larger (`physverify.order.effective_floor`). Round-off grows with the number of steps too, so very long runs may need a larger floor.
- MMS needs a way to add a source term. Codes without one need a small adapter, and an adapter can itself be wrong.
- No claim is made that this finds bugs outside the cases shown here.

## Related work

Each part of physverify has earlier work behind it. Searched on 2026-10-19; I did not find a package that combines all five check families with a seeded-bug benchmark, but that is a search result, not proof that none exists.

- Salari and Knupp, [Code Verification by the Method of Manufactured Solutions](https://www.osti.gov/biblio/759450) (Sandia report SAND2000-1444, 2000). Describes MMS and a blind-test protocol for finding which coding mistakes it can and cannot expose. The seeded-bug benchmark here follows the same idea on a much smaller scale.
- Wu and Mitchell, [Mutant Accuracy Testing for Assessing the Implementation of Numerical Algorithms](https://www.cs.toronto.edu/~rwu/papers/wu2019mutation.pdf) (NSV at CAV, 2019). Tests numerical implementations, correct and with artificially introduced bugs, in MATLAB, by comparing a code's error with that of mutated versions of itself. Its oracle differs from the ones here, and it notes that convergence-rate checks depend on heuristic thresholds, which is the weakness `patch` is meant to address.
- [MASA](https://github.com/manufactured-solutions/MASA). A C++ library of manufactured solutions for PDE codes. It supplies solutions; it does not run a user's solver and report PASS/FAIL.
- [ExactPack](https://github.com/lanl/ExactPack) (Los Alamos). A Python package for code verification built on exact solutions of benchmark problems. It complements MMS, and its problems could serve as `reference` cases.
- [materials-simulation-skills](https://github.com/HeshamFS/materials-simulation-skills). Agent skills for simulation work, including a `benchmark-and-mms-planner` skill. From its skill description it is a planning aid, not a runner of checks on user code (only the description was read). It is the nearest thing found to the planned assistant hook.

For `patch`, no prior work was found. The name comes from finite-element patch tests, which also require a scheme to reproduce a simple field exactly, but I found no published test that uses a manufactured solution inside the scheme's discrete solution space to catch errors of the same order as the truncation error. I did not read the finite-element patch-test or "nearby problems" literature, so similar ideas may exist under other names.

## Layout

```
src/physverify/
  order.py          observed order, exactness, PASS/FAIL logic, scale-aware noise floor
  mms.py            manufactured solutions (complex-step derivative), final-state and whole-trajectory studies
  studies.py        reference, invariant, patch and plain-test checks; ode_checks bundle
  steppers.py       Euler, midpoint, RK4
  symbolic.py       SymPy-derived manufactured sources (optional)
  report.py         run checks; text, JSON and HTML output
  cli.py            the physverify command
  pytest_plugin.py  verify_*.py files as pytest tests
  agent.py          Claude Code hook and MCP server
  stochastic/       2D Ising: exact references, samplers with seeded bugs, statistical checks, calibration
  problems/         seeded-bug solvers: projectile, pendulum, kepler, heat1d, sod
  adapters/         read-only adapters for the two real projects
  matrix.py         the detection tables and bug catalogue
  compare.py        the families against plain tests
  butcher.py        Runge-Kutta order conditions on rooted trees; linear and stage order, R(z), A/L-stability
  method_bugs.py    seeded bugs in methods, from public repositories, with controls
  references.py     exact references reused across adapters (Ising enumeration, heat modes, pendulums, ...)
  loaders.py        load code from a path; stub_modules, run_script, load_definitions_from_path
  constants.py      literals close to, but not equal to, a physical constant
docs/               patch.md (what the exactness checks assume and prove), agent.md
examples/           a solver and its spec
tests/              about 140 tests, including the seeded-bug regression
```

## Next steps (not done)

- Try it on someone else's real solver. Nobody but the author has used it yet.
- A limit check for Sod (shock speed from the Rankine-Hugoniot conditions), and an exactness check for more PDE schemes.
- Larger Ising lattices and the optional scaling check (Binder-cumulant crossing); other stochastic models.

## Licence

MIT. Copyright (c) 2026 Ram Chandra Giri.
