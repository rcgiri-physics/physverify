# physverify

[![tests](https://github.com/rcgiri-physics/physverify/actions/workflows/ci.yml/badge.svg)](https://github.com/rcgiri-physics/physverify/actions/workflows/ci.yml) [![PyPI](https://img.shields.io/pypi/v/physverify)](https://pypi.org/project/physverify/) [![Python](https://img.shields.io/pypi/pyversions/physverify)](https://pypi.org/project/physverify/) [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23534512.svg)](https://doi.org/10.5281/zenodo.23534512) [![Docs](https://img.shields.io/badge/docs-site-blue)](https://rcgiri-physics.github.io/physverify/)

**Checks that a simulation solves the equations it claims, at the order of accuracy it claims, not just that it runs.**

physverify is actively evolving (v0.7.0), welcoming contributions and test cases from the computational physics community. Status: under active development and maintenance, tested on a growing corpus of public physics codes; releases come at milestones. Scope: numerical solutions of ODEs and PDEs (time integration, convergence, conservation), plus a few Monte Carlo checks. It needs only NumPy.

![The check loop: your solver and an independent description of the physics go in; physverify runs the solver at several resolutions, measures the error and reports a verdict with a reason](https://raw.githubusercontent.com/rcgiri-physics/physverify/main/docs/images/check-loop.svg)

```bash
pip install physverify
physverify demo
```

The demo checks a correct solver (all checks pass), then the same solver with the damping 10% too large (all fail):

![Error against step size: the correct solver follows the slope-2 line, the broken one levels off](https://raw.githubusercontent.com/rcgiri-physics/physverify/main/docs/images/convergence.svg)

New to this? [Start here](https://rcgiri-physics.github.io/physverify/start-here/) walks through installation and a first check in about ten minutes, with a prompt to paste if you use an AI coding assistant.

## Use it on your own code

- **Any project, no set-up:** `physverify scan PATH` reads the code (it runs nothing) and flags Runge-Kutta methods that do not have their stated order (written as tables, as class attributes or as stages in code), grid spacings that do not match their grid, near-miss physical constants, and inverse function pairs worth a round-trip test.
- **An ODE solver:** `physverify init verify_solver.py --solver mysolver --order 4` writes a spec; fill in the equations (from the physics, not from your code) and run `physverify run verify_solver.py`.
- **A Runge-Kutta table:** `check_tableau(A, b, c, claimed=3)` from `physverify.butcher` checks its order, stage order and stability from the coefficients alone.
- **Errors you already have:** `check_order(hs, errors, expected=2)` gives PASS, FAIL or INCONCLUSIVE with a reason.

## Run it in CI

A failed check fails the job, like a broken unit test ([CI guide](https://rcgiri-physics.github.io/physverify/ci/): options, pre-commit, pytest):

```yaml
      - uses: rcgiri-physics/physverify@v0.7.0
        with:
          specs: tests/verify_*.py
```

[Getting started](https://rcgiri-physics.github.io/physverify/getting-started/) · [Recipes](https://rcgiri-physics.github.io/physverify/recipes/) · [What a PASS means](https://rcgiri-physics.github.io/physverify/assumptions/) · [Troubleshooting](https://rcgiri-physics.github.io/physverify/troubleshooting/) · [API](https://rcgiri-physics.github.io/physverify/api/)

## Does it catch bugs?

Of 37 bugs seeded into five small solvers, it flagged 35 (plain "compare with one answer" tests: 27), with no false alarms. The bugs and checks were written by the same person, so this shows the tool works as designed, not how it does on other people's code. On public physics repositories, 74 defects were reported to authors; 14 of them were found by a physverify check as such, 11 by simply running the code, and the rest by the per-repository test scripts or by reading the code. `physverify scan` alone, with no script, now finds 18 of the 74, up from 2 in its first version, and found 7 new defects in the same repositories ([which found what](https://github.com/rcgiri-physics/physverify/blob/main/results/corpus/FINDINGS_BY_METHOD.md)). The counts describe that sample only and are not a bug rate. Details: [results](https://rcgiri-physics.github.io/physverify/results/), and [results/README.md](https://github.com/rcgiri-physics/physverify/blob/main/results/README.md) to regenerate every table.

## Limits

Works best for ODEs; PDEs only in 1D so far. Your code needs a way to add a source term, or a small wrapper that can itself be wrong. A PASS means these checks found nothing wrong; it does not prove the simulation correct, and it is only as independent as the reference you wrote: see [What a PASS means](https://rcgiri-physics.github.io/physverify/assumptions/).

## Contributing, citing, licence

Help is welcome: a trial report on your own solver, seeded bugs written by someone other than the author, adapters, documentation. See [CONTRIBUTING.md](https://github.com/rcgiri-physics/physverify/blob/main/CONTRIBUTING.md), the [code of conduct](https://github.com/rcgiri-physics/physverify/blob/main/CODE_OF_CONDUCT.md), [SUPPORT.md](https://github.com/rcgiri-physics/physverify/blob/main/SUPPORT.md) for help, [SECURITY.md](https://github.com/rcgiri-physics/physverify/blob/main/SECURITY.md) on running untrusted code, and [AGENTS.md](https://github.com/rcgiri-physics/physverify/blob/main/AGENTS.md) for AI assistants. To cite, use [doi:10.5281/zenodo.23534512](https://doi.org/10.5281/zenodo.23534512) or [CITATION.cff](https://github.com/rcgiri-physics/physverify/blob/main/CITATION.cff). Changes: [CHANGELOG.md](https://github.com/rcgiri-physics/physverify/blob/main/CHANGELOG.md); plans: [ROADMAP.md](https://github.com/rcgiri-physics/physverify/blob/main/ROADMAP.md). The methods are standard and other tools do parts of this, some better (NodePy for Runge-Kutta analysis); see [related work and credits](https://rcgiri-physics.github.io/physverify/related-work/). MIT licence, copyright (c) 2026 Ram Chandra Giri.

<!-- mcp-name: io.github.rcgiri-physics/physverify -->
