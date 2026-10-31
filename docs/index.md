# physverify

**Check that a physics simulation solves the right equations, at the accuracy it claims, not just that it runs.**

A simulation can run, draw nice plots and still be wrong: a minus sign in the wrong place, a factor of 2 missing, a time step that is off by one. Ordinary tests often miss these, because nobody knows the exact answer for a real simulation. physverify uses standard ideas from numerical analysis to check such code anyway, and explains each result in plain words.

```bash
pip install physverify
physverify demo
```

![The check loop: your solver and an independent description of the physics go in; physverify runs it at several resolutions, measures the error and reports a verdict with a reason](images/check-loop.svg)

**Run it on every push:** add the [GitHub Action](ci.md) to your workflow; a failed check fails the job.

```yaml
      - uses: rcgiri-physics/physverify@v0.7.0
        with:
          specs: tests/verify_*.py
```

**Before trusting a PASS**, read [What a PASS means](assumptions.md): the checks are only as independent as the reference equations you write.

## What it checks

| Check | The question it answers | Example |
|---|---|---|
| [Manufactured solutions](checks/manufactured-solutions.md) | Does the code solve *these* equations? | A midpoint method with a half-step typo |
| [Order of convergence](checks/order.md) | Does the error shrink as fast as the method promises? | Hand in your own step sizes and errors |
| [Reference solutions](checks/reference.md) | Does it agree with an independent, more accurate solution? | A pendulum |
| [Conserved quantities and budgets](checks/conservation.md) | Is energy kept? Does heat leak through an insulated wall? | Velocity Verlet, a 1D heat solver |
| [Exact patch tests](checks/patch.md) | Does it reproduce a solution it should get exactly? | A stage evaluated at the wrong time |
| [Runge-Kutta tables](checks/runge-kutta.md) | Do the coefficients have the order and stability their name says? | A table labelled order 3 that is order 2 |
| [Exact references](checks/exact-references.md) | Does it match a known closed-form result? | Morse oscillator energy levels |
| [Statistics](checks/statistics.md) | Do the error bars mean what they say? Is a Monte Carlo sampler correct? | 68% intervals that cover 30% |

Every example on this site is a small script in [`docs/examples/`](https://github.com/rcgiri-physics/physverify/tree/main/docs/examples), and the output shown is what it printed.

## What a result looks like

```text
mms        PASS   midpoint damped oscillator: observed order 2.04 (expected 2)
reference  PASS   midpoint damped oscillator: observed order 2.01 (expected 2)
mms        PASS   midpoint damped oscillator (whole trajectory): observed order 2.02 (expected 2)
patch      EXACT  midpoint damped oscillator: reproduced to round-off (largest error 2.7e-15), as designed
4 of 4 checks passed
```

Each check reports **PASS**, **FAIL**, **EXACT** (reproduced to round-off), **INCONCLUSIVE** (the errors could not be measured; the message says why), **ERROR** (the code crashed) or **SKIP** (an optional package is missing).

## Does it work?

- On 37 bugs added one at a time to five small solvers, it caught 35, with no false alarms on the bug-free versions. The bugs and the checks were written by the same person, so this shows the tool works as designed; it is not a promise about other code.
- It was tried on 250 public physics repositories in a locked-down container and found confirmed bugs in some of them. The counts describe that sample only; see [Results on real code](results.md).

## Where to go next

- New here: [Getting started](getting-started.md), then [How it works](how-it-works.md).
- Have a solver to check: [Recipes](recipes.md).
- Want it on every push: [Continuous integration](ci.md).

## Citing

If physverify helps your work, please cite it: [doi:10.5281/zenodo.23534512](https://doi.org/10.5281/zenodo.23534512) (all versions; each release also has its own DOI on Zenodo).

physverify is actively evolving (version 0.7.0), welcoming contributions and test cases from the computational physics community. Status: under active development and maintenance, tested on a growing corpus of public physics codes; releases come at milestones. See [how to help](https://github.com/rcgiri-physics/physverify/blob/main/CONTRIBUTING.md) and [GitHub issues](https://github.com/rcgiri-physics/physverify/issues).
