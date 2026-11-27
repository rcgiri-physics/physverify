# physverify — code verification for numerical simulation

[![tests](https://github.com/rcgiri-physics/physverify/actions/workflows/ci.yml/badge.svg)](https://github.com/rcgiri-physics/physverify/actions/workflows/ci.yml) [![PyPI](https://img.shields.io/pypi/v/physverify)](https://pypi.org/project/physverify/) [![Python](https://img.shields.io/pypi/pyversions/physverify)](https://pypi.org/project/physverify/) [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23534512.svg)](https://doi.org/10.5281/zenodo.23534512) [![Docs](https://img.shields.io/badge/docs-site-blue)](https://rcgiri-physics.github.io/physverify/)

**Test whether simulation code behaves as the mathematics predicts.** Check convergence order, agreement with exact or manufactured solutions, conservation laws, and time-integration coefficients.

A simulation can run, give plausible numbers and still be wrong: a sign slip, a missing factor of 2, one coefficient copied with a digit dropped. Comparing with one stored answer rarely shows it, because nobody knows the exact answer for a real simulation. The mathematics still predicts things you can test: the error must shrink at the method's order, a manufactured solution must come back, an insulated domain must keep its heat, a Runge–Kutta table must satisfy its order conditions. physverify runs those tests and says in plain words what was tested and what came out: PASS, FAIL, EXACT or INCONCLUSIVE, with the numbers.

Its strongest coverage is ODE time integration; PDEs are covered in selected cases (1D heat and transport). It needs only NumPy and runs from Python, the command line, pytest or GitHub Actions. Current release: 0.10.0 (v0.10.0); actively developed, feedback welcome.

## Try it

```bash
pip install physverify
physverify demo
```

The demo checks a correct damped-oscillator solver (all checks pass), then the same solver with the damping 10% too large. The broken one still gives a smooth, plausible curve, and every check fails:

![Error against step size: the correct solver follows the slope-2 line, the broken one levels off](https://raw.githubusercontent.com/rcgiri-physics/physverify/main/docs/images/convergence.svg)

New to this? [Start here](https://rcgiri-physics.github.io/physverify/start-here/) takes about ten minutes.

## Verify your simulation code

Write the reference from the physics (a textbook, a paper, the project's README), never from the code under test; otherwise a bug in the code is copied into the reference and the check passes.

**Convergence order, as a pytest test.** Run the solver at a few step sizes, measure the error against an exact solution, and check the order:

```python
import numpy as np
from physverify import check_order

def midpoint_error(n):                    # y' = -y, y(0) = 1, exact y(1) = exp(-1)
    h, y = 1.0 / n, 1.0
    for _ in range(n):
        y = y + h * -(y + h / 2 * -y)
    return abs(y - np.exp(-1.0))

def test_midpoint_is_second_order():
    ns = [10, 20, 40, 80]
    result = check_order([1 / n for n in ns], [midpoint_error(n) for n in ns], expected=2)
    assert result.status == "PASS", result.message    # "observed order 2.03 (expected 2)"
```

**A Runge–Kutta table, from the coefficients alone** (no solver needed):

```python
from physverify.butcher import check_tableau

A = [[0, 0, 0, 0], [1/2, 0, 0, 0], [0, 1/2, 0, 0], [0, 0, 1, 0]]
print(check_tableau(A, b=[1/6, 1/3, 1/3, 1/6], c=[0, 1/2, 1/2, 1], claimed=4))
# PASS: order 4 confirmed by the order conditions
```

Change the last row of `A` to `[0, 0, 0.9, 0]` and the verdict is FAIL: the table satisfies the order conditions only up to order 1. The same module checks embedded pairs, stability claims, dense output (`check_dense_output`), IMEX order and coupling conditions (`check_additive`) and Rosenbrock and W-methods (`check_rosenbrock`).

**A whole solver, from a spec.** `physverify init verify_solver.py --solver mysolver --order 4` writes a starter spec for a fixed-step ODE solver. Fill in the right-hand side from the physics, then run `physverify run verify_solver.py` or `pytest verify_solver.py`. The starter spec runs manufactured-solution, reference-solution and exact-patch checks; add a `quantity` function (an energy, a mass) to check conservation as well.

**On every push.** A failed check fails the job, like a broken unit test ([CI guide](https://rcgiri-physics.github.io/physverify/ci/)):

```yaml
      - uses: rcgiri-physics/physverify@v0.10.0
        with:
          specs: tests/verify_*.py
```

## What it checks

| Check | The question it answers |
|---|---|
| [Order of convergence](https://rcgiri-physics.github.io/physverify/checks/order/) | Does the error shrink as fast as the method promises? |
| [Manufactured solutions](https://rcgiri-physics.github.io/physverify/checks/manufactured-solutions/) | Does the code solve *these* equations, source terms and all? |
| [Reference and exact solutions](https://rcgiri-physics.github.io/physverify/checks/exact-references/) | Does it agree with a closed-form result or an independent, more accurate solution? |
| [Conservation and budgets](https://rcgiri-physics.github.io/physverify/checks/conservation/) | Is energy kept? Does heat leak through an insulated wall? |
| [Exact patch tests](https://rcgiri-physics.github.io/physverify/checks/patch/) | Does it reproduce a solution it should get to round-off? |
| [Time-integration coefficients](https://rcgiri-physics.github.io/physverify/checks/runge-kutta/) | Do the Runge–Kutta, IMEX or Rosenbrock coefficients have the order their name says? |
| [Statistics](https://rcgiri-physics.github.io/physverify/checks/statistics/) | Do the error bars mean what they say? Is a Monte Carlo sampler correct? |

Every example in the documentation is a small script in [`docs/examples/`](https://github.com/rcgiri-physics/physverify/tree/main/docs/examples), and the output shown is what it printed. [Recipes](https://rcgiri-physics.github.io/physverify/recipes/) · [What a PASS means](https://rcgiri-physics.github.io/physverify/assumptions/) · [Troubleshooting](https://rcgiri-physics.github.io/physverify/troubleshooting/) · [API](https://rcgiri-physics.github.io/physverify/api/)

## With an AI coding assistant

An assistant reading code on its own makes many claims, and reading cannot tell the right ones from the wrong ones. Of 119 claims five AI reviewers made about repositories that earlier testing had found clean, check runs showed 40 changed a result, 51 were real but minor and 10 were wrong; 18 stayed unsettled even after a check was attempted. A run against a reference from the physics is what separates them, when it can be built. Paste this into Claude Code, Codex, Cursor, Copilot or any assistant that can run commands, in the project's folder:

```text
Verify the numerical code in this project with physverify (pip install physverify; rules in
https://github.com/rcgiri-physics/physverify/blob/main/AGENTS.md).
1. Find the solvers and integrators and what they claim: the equations, the order of accuracy,
   what is conserved, the coefficient tables and where they come from.
2. Write each reference from the physics (README, paper, textbook), never from the code under
   test, and tell me where every equation came from.
3. The tests run this project's code. Run it only if I trust the project; otherwise use the
   physverify sandbox (sandbox/README.md in the physverify repository) and ask me first.
4. Test each claim as a pytest test in tests/: check_order for convergence order, an exact or
   manufactured solution for the answer itself, physverify.butcher for coefficient tables,
   a conservation check for what must be kept.
5. When a check fails, suspect the test first (units, signs, time origin, step counts; see
   docs/troubleshooting.md). Call it a bug only when a check fails against an independent reference.
6. Do not change the solver. Report what was tested, what was not, and what each PASS covers.
```

[AGENTS.md](https://github.com/rcgiri-physics/physverify/blob/main/AGENTS.md) gives an assistant the rules and a table of which check answers which question. To let an assistant call the checks itself, `physverify mcp` is a local MCP server (`run_checks` runs a project's `verify_*.py` specs); add it to your client's MCP settings ([guide](https://rcgiri-physics.github.io/physverify/agent/), also in the [official MCP registry](https://registry.modelcontextprotocol.io) as `io.github.rcgiri-physics/physverify`):

```json
{
  "mcpServers": {
    "physverify": { "command": "physverify", "args": ["mcp"] }
  }
}
```

The checks run your project's Python code on your computer, so use them on projects you trust, or inside the [sandbox](https://github.com/rcgiri-physics/physverify/tree/main/sandbox).

## Runge–Kutta table census

Coefficient tables are copied by hand from papers into code, and one wrong digit can lower a method's order with no visible sign: adaptive step control hides it, and a test on y′ = λy often cannot see it. In November 2026, `physverify.butcher` (including the Rosenbrock, IMEX and dense-output checks added in 0.9.0) was run on 847 Runge–Kutta tables (explicit, implicit, IMEX and low-storage) from 34 libraries, and then on the Rosenbrock and W-method tables of every Rosenbrock code a GitHub search found. NodePy agreed on all 680 passing tables it was run on, and 344 tables were compared with their first published source.

- 791 of the 847 tables pass and 39 fail; each failure was reviewed by hand, and more than half are defects (the others are by design, harmless or still open).
- Most defects show only when f depends on t (a stage at the wrong time, a missing ∂f/∂t term) or only in the error estimate, so a test on y′ = λy passes. Test with a time-dependent problem too.
- 23 defect reports were sent to the libraries: 5 confirmed by the maintainers, 2 with fixes in review, 16 waiting for a reply. A library is named here only after its maintainers confirm.

[The census page](https://rcgiri-physics.github.io/physverify/census/) has the method, the outcomes and what was not covered. The tables themselves are published as a separate dataset, [runge-kutta-catalog](https://github.com/rcgiri-physics/runge-kutta-catalog) ([doi:10.5281/zenodo.24412889](https://doi.org/10.5281/zenodo.24412889)): every table with its library, version and source, the methods compared with their first published sources, 88 Rosenbrock tables, and scripts that re-check each one with physverify. The counts hold for these libraries only; they are not an error rate for numerical software.

## Confirmed by maintainers

Three examples. [The full record](https://rcgiri-physics.github.io/physverify/confirmed/) lists every confirmed report, each with a link to the maintainer's response or the fix.

- **[qmat](https://github.com/Parallel-in-Time/qmat/issues/23):** three Runge–Kutta schemes were labelled one order higher than they have. The maintainers corrected them and now check their tables with `physverify.butcher` in their own tests ([PR #24](https://github.com/Parallel-in-Time/qmat/pull/24)).
- **[OrdinaryDiffEq.jl](https://github.com/SciML/OrdinaryDiffEq.jl/issues/5001):** one node of the 12th-order Feagin table was stored as 2 instead of 0.2, so on a time-dependent problem the method converged at first order. A maintainer confirmed it, and it is fixed ([PR #5002](https://github.com/SciML/OrdinaryDiffEq.jl/pull/5002)).
- **[SUNDIALS](https://github.com/LLNL/sundials/issues/1083):** in the symplectic `SPRKStep` integrator, a time-dependent force made every table first order. A maintainer reproduced it independently and proposed the fix ([response](https://github.com/llnl/sundials/issues/1083#issuecomment-7022495963)).

These show that the defects were real; they are not a bug rate for physics code.

## How well it works

- **Seeded bugs:** of 37 bugs added one at a time to five small solvers, the checks flagged all 37 (two of them only after checks were added for those two; plain "compare with one answer" tests: 27), with no false alarms. The same person wrote the bugs and the checks, so this shows the tool works as designed, not how it does on other code. `python scripts/reproduce_all.py` regenerates the tables.
- **AI review claims on 100 repositories (2026-11):** five AI reviewers reviewed 100 public physics repositories. On the 50 that earlier testing had found clean, 119 review claims were each checked by a run: 40 changed a result, 51 were real but minor, 10 were wrong and 18 could not be settled. Counts hold for this sample only; the labels come from two automated checkers following written rules ([preprint, doi:10.5281/zenodo.24224433](https://doi.org/10.5281/zenodo.24224433)).
- **Earlier testing of public repositories (October 2026):** of the first 74 defects reported to authors, 14 were found by a physverify check as such, 11 by running the code at all, and the rest by each repository's test script or by reading ([ledger](https://github.com/rcgiri-physics/physverify/blob/main/results/corpus/LEDGER.md), [results](https://rcgiri-physics.github.io/physverify/results/)).

## Also included

- `physverify confirm` records one suspected defect, its reference and the run that settles it, with a fixed verdict rule ([guide](https://rcgiri-physics.github.io/physverify/confirm/)).
- `physverify scan PATH` reads source code without running it and flags a fixed set of patterns worth a closer look; a clean scan means only that those patterns were not found ([command line](https://rcgiri-physics.github.io/physverify/running/cli/)).
- `physverify references` lists exact reference solutions, and the [sandbox](https://github.com/rcgiri-physics/physverify/tree/main/sandbox) runs code you did not write without network access.

## Limits

Strongest for ODE time integration; PDE checks cover selected 1D cases so far. Your code needs a way to add a source term for manufactured solutions, or a small wrapper that can itself be wrong. A PASS means these checks found nothing wrong; it does not prove the simulation correct, and it is only as independent as the reference you wrote: see [What a PASS means](https://rcgiri-physics.github.io/physverify/assumptions/).

## Contributing, citing, licence

Feedback is the most useful contribution: try physverify on a solver you know and tell us what was flagged, what was missed and where you got stuck ([trial report](https://github.com/rcgiri-physics/physverify/issues/new?template=trial_report.md)). Questions, bug reports and small documentation fixes are all welcome; see [CONTRIBUTING.md](https://github.com/rcgiri-physics/physverify/blob/main/CONTRIBUTING.md), the [code of conduct](https://github.com/rcgiri-physics/physverify/blob/main/CODE_OF_CONDUCT.md), [SUPPORT.md](https://github.com/rcgiri-physics/physverify/blob/main/SUPPORT.md) and [SECURITY.md](https://github.com/rcgiri-physics/physverify/blob/main/SECURITY.md) on running untrusted code.

To cite, use [doi:10.5281/zenodo.23534512](https://doi.org/10.5281/zenodo.23534512) or [CITATION.cff](https://github.com/rcgiri-physics/physverify/blob/main/CITATION.cff). Changes: [CHANGELOG.md](https://github.com/rcgiri-physics/physverify/blob/main/CHANGELOG.md); plans: [ROADMAP.md](https://github.com/rcgiri-physics/physverify/blob/main/ROADMAP.md). The methods are standard and other tools do parts of this, some better (NodePy for Runge–Kutta analysis, MASA for manufactured solutions); see [related work and credits](https://rcgiri-physics.github.io/physverify/related-work/). MIT licence, copyright (c) 2026 Ram Chandra Giri.

<!-- mcp-name: io.github.rcgiri-physics/physverify -->
