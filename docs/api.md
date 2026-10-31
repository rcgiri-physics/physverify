# API overview

The functions most specs need. Each has a docstring with the details: `help(physverify.studies.reference_study)` and so on.

## Building checks

| Name | What it does |
|---|---|
| `Check(family, label, run, budget_s=None)` | One runnable check; `run()` returns a `Result`. |
| `Result(status, message)` | `.ok` (PASS or EXACT), `.failed` (FAIL, ERROR or INCONCLUSIVE). |
| `OrderResult` | A `Result` with `expected`, `fitted`, `hs` and `errors`. |
| `requires("pkg")`, `SkipCheck` | Report SKIP when an optional package is missing. |
| `ode_checks(label, integrate, ...)` | The standard bundle for an ODE solver. |

## Order studies (`physverify`, `physverify.studies`, `physverify.mms`)

| Name | What it does |
|---|---|
| `ManufacturedODE(u, rhs_ref)` | A manufactured solution and its source term. |
| `mms_order_study(integrate, mms, t_end, ns, order)` | Error at `t_end` against the manufactured solution. |
| `mms_trajectory_study(...)` | Largest error over the whole run. |
| `backward_mms_study(...)` | The same, integrating from `t_end` back to 0. |
| `reference_study(integrate, rhs_ref, y0, t_end, ns, order)` | Against a fine RK4 reference. |
| `invariant_study(integrate, quantity, y0, t_end, ns, order)` | Drift of a conserved quantity. |
| `patch_study(integrate, rhs_ref, y0, slope, t_end, ns)` | A linear solution reproduced to round-off. |
| `trajectory_order_study(runs, exact, t_compare, order, period=None)` | From whole trajectories, at one fixed time. |
| `check_order(hs, errors, expected, atol=None)` | The verdict from step sizes and errors; `atol` adds an accuracy requirement on the finest grid, reported apart from the order. |
| `check_exact(hs, errors)` | The verdict when every error should be at round-off. |

## Other checks (`physverify.studies`)

| Name | What it does |
|---|---|
| `balance_check(measure, expected, resolutions)` | An exact budget at every resolution. |
| `time_grid_check(times_of_run, t_start, t_stop, ns)` | The run ends at `t_stop` after exactly n steps. |
| `size_sweep_check(run_at_size, sizes)` | The code runs for odd and even sizes. |
| `coverage_check(simulate, interval, prior_sampler, level=...)` | Coverage of stated intervals. |
| `damped_sinusoid_fit(t, y, t_start, t_stop)` | Complex frequency of a ringdown. |
| `decay_rate(t, y, t_skip=None)` | Exponential decay rate, skipping the start-up transient (found automatically when `t_skip` is not given). |
| `residual_check(solve, residual, tols)` | An iterative solver's residual follows the tolerance it was asked for. |

## Identities and round trips (`physverify.identities`)

| Name | What it does |
|---|---|
| `check_agree(a, b, inputs, rtol, atol)` | Two code paths give the same answer. |
| `check_roundtrip(forward, inverse, inputs)` | `inverse(forward(x)) == x`. |
| `check_derivative(f, df, points, order=1)` | An analytic derivative against finite differences. |
| `check_identity([(label, lhs, rhs), ...])` | Identities computed from the physics. |
| `check_unitary(M)` | `M^H M = I`. |
| `fd_derivative`, `laplacian_fd` | Finite-difference helpers. |
| `vary_one(test, defaults, changes)` | A test that passes at the defaults still passes with each parameter changed on its own. |
| `check_scale(got, ref)` | The output is 1 times the reference; names the factor when it is not. |
| `check_vec_convention(S, f, X)` | Row- or column-major vectorisation of a superoperator. |

See [Identities and round trips](checks/identities.md) and [Hidden defaults, scale, stencils and fluxes](checks/defaults-scale-stencils.md).

## Stencils and fluxes (`physverify.stencils`, `physverify.fluxes`)

| Name | What it does |
|---|---|
| `check_stencil(offsets, weights, deriv, claimed=None, divisor=1)` | Consistency, scale and order of a finite-difference stencil from its Taylor moments. |
| `stencil_moments`, `stencil_order` | The moments and the order on their own. |
| `check_flux(flux, physical, states, upwind_pairs=(), downwind_pairs=(), mirror=None)` | Consistency, upwinding and mirror symmetry of a numerical flux. |

## Runge-Kutta tables (`physverify.butcher`)

`check_tableau`, `tableau_order`, `order_residuals`, `linear_order`, `stage_order`, `stability_function`, `stability_polynomials`, `r_infinity`, `a_stability_margin`, `is_stiffly_accurate`. See [Runge-Kutta tables](checks/runge-kutta.md).

## Loading code (`physverify.loaders`)

| Name | What it does |
|---|---|
| `load_module_from_path(path, stubs=None)` | Import a file as a module. |
| `load_definitions_from_path(path, stubs=None)` | Only its functions and classes, without running the script. |
| `load_repaired(name, path, fix)`, `repairs_note(module)` | Import a file after a recorded repair, so a PASS is reported as a PASS on repaired code. |
| `extract_functions(path, names, namespace=None)` | Named functions plus the same-file helpers they use, for a package that will not import. |
| `run_script(path, argv=(), inputs=None)` | Run a whole script; returns (globals, printed text). |
| `stub_modules({...})` | Stand-ins for imports the tested code does not use. |

## Exact references (`physverify.references`)

Listed by `physverify references`; see [Exact references](checks/exact-references.md).

## Reports (`physverify.report`)

`run_checks(checks, budget_s=None)`, `to_text`, `to_json`, `to_markdown`, `to_html`, `summary`.

## What is public, and the rule for changes

The public API is:

- the names in `physverify.__all__` (`Check`, `Result`, `OrderResult`, `SkipCheck`, `requires`, `ManufacturedODE`, `mms_order_study`, `zero_source`, `check_order`, `check_exact`, `fit_order`, `pairwise_orders`, `ode_checks`, `invariant_study`, `patch_study`, `reference_study`);
- the functions listed on this page in `physverify.studies`, `physverify.butcher`, `physverify.identities`, `physverify.loaders` and `physverify.references`;
- the command line (`physverify run`, `init`, `demo`, `smoke`, `references`) and its exit codes: 0 when no check fails, 1 when one does, 2 when a spec cannot be loaded or defines no checks;
- the JSON output below.

Before version 1.0, a release may change the public API, but every such change is listed under **Changed** in the [changelog](changelog.md) with what to do instead. New fields in the JSON output are not breaking changes; removing or renaming one is, and raises `schema_version`.

## JSON output (`physverify run --json`)

`schema_version` is 1.

| Field | Meaning |
|---|---|
| `schema_version` | Version of this layout. |
| `physverify` | Version of physverify that wrote the file. |
| `source` | The spec file(s). |
| `summary` | `total`, `ok`, `not_ok`, `skipped`, and `by_status` (count per status). |
| `checks` | One record per check, below. |
| `note` | What a PASS means: these checks found nothing wrong; it does not prove the simulation correct. |

Each record in `checks`:

| Field | Meaning |
|---|---|
| `family`, `label` | The kind of check and its name. |
| `status` | PASS, FAIL, EXACT, INCONCLUSIVE, ERROR or SKIP. |
| `ok` | True for PASS and EXACT. |
| `message` | The verdict in words. |
| `seconds` | Run time. |
| `claim` | What property this family tests. |
| `expected_order`, `observed_order`, `h`, `error` | Order studies only (`null` where not finite). |
| `acceptance` | Order studies only: the rule a PASS had to meet, for example "fitted order within [1.7, 3] on errors above 1e-12". |
