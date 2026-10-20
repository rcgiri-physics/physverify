# physverify

**A tool that checks whether a physics simulation is solving the right equations correctly, not just running without errors.**

Status: early version (0.3.1). It has been tried on 68 public physics repositories (see below), but nobody besides the author has used it yet, so feedback is very welcome.

## The problem it addresses

A simulation can run, produce nice plots and still be wrong: a minus sign in the wrong place, a factor of 2 missing, a time step that is off by one. Ordinary tests often miss these, because nobody knows the "right answer" for a real simulation to compare against.

## How it works, in plain words

physverify uses a few standard ideas from numerical analysis:

1. **Make up an answer, then check the code finds it.** Pick a smooth function, work out what extra push (a "source term") would make it an exact solution, give that push to your code, and see if your code reproduces the function. This is called the *Method of Manufactured Solutions*.
2. **Check the error shrinks at the right speed.** If your method is supposed to be 4th order, halving the time step should make the error about 16 times smaller. If it only gets 2 times smaller, something is wrong, even if the error looked small.
3. **Check conserved quantities and budgets.** Energy, mass or momentum should stay constant (or drift in a predictable way), and heat added through a wall or a source should match what went in, exactly, on every grid.
4. **Check known special cases.** For example, a projectile with no air resistance has a range you can write down by hand.
5. **Exact "patch" tests.** Some solutions should be reproduced to computer precision. This catches small bugs that the other checks let through.
6. **Algebraic checks on the method itself.** For a Runge-Kutta method, whether the coefficients really have the order they claim can be settled exactly, with no test problem (the "order conditions").

Each check reports **PASS**, **FAIL**, **EXACT** or **INCONCLUSIVE**.

There is also a separate set of checks for random (Monte Carlo) simulations, using the 2D Ising model as the example.

## Does it actually catch bugs?

To test it, 37 bugs were added one at a time to five small solvers (projectile, double pendulum, planet orbit, heat equation, shock tube):

- **35 of 37** bugs were caught. Plain "compare with one answer" tests caught 27.
- **0 false alarms** on the bug-free versions.
- The 2 missed bugs are explained in the [technical details](https://github.com/rcgiri-physics/physverify/blob/main/docs/technical.md).

For the Monte Carlo checks, all 21 seeded bugs were caught with no false alarms.

The bugs and the checks were written by the same person, so these numbers show the tool works as designed. They are not a promise about bugs in other people's code.

## Trying it on other people's code

To see what it does on code it was not written for, public Python physics repositories from GitHub were run in a locked-down container (October 2026): no network, the repository read-only, nothing from it run on the author's computer. 40 were drawn at random from topic searches (batches 1 to 4); another 60 were the newest small repositories whose README says the work is complete (batch 5), and 20 more were picked because they are quick to test (batch 6); batches 5 and 6 are not random.

- **68 of the 120 could be tested.** Most of the others were not numerical solvers (neural networks, apps and games, analysis tools, finance), one needed a recent NVIDIA GPU, and a few need more set-up.
- **16 confirmed bugs in 12 of the 68.** For example: a measured energy that counts the magnetic-field term twice; backward time-stepping that is only first-order accurate; Runge-Kutta coefficient tables labelled with a higher order than they have; a spectral derivative that crashes for an odd number of grid points; boundary values applied after the linear solve instead of inside it; an insulated wall that leaks heat; a grid spacing off by one interval; a Kepler solver that fails for negative angles.
- **The rest had no confirmed bug.** Most passed every check that applied, often to 1e-13 or better.
- **Our own adapters were wrong about 28 times** before checking (a wrong constant, too-coarse steps, a wrong sign convention, and so on). Every FAIL was checked by hand before being called a bug, and these mistakes are recorded, not hidden.

These counts describe the repositories that were drawn; they are not a bug rate for physics code in general.

Each lesson became a new check or a clearer message in physverify. The testing and write-ups were done with help from an AI assistant; every number comes from running the code. Authors are told about a finding before their project is named, so the repositories are listed by ID: [results/corpus/SUMMARY.md](https://github.com/rcgiri-physics/physverify/blob/main/results/corpus/SUMMARY.md).

## Try it

You need Python 3.10 or newer.

```bash
pip install physverify
```

The example below lives in the repository, so clone it to follow along:

```bash
git clone https://github.com/rcgiri-physics/physverify.git
cd physverify
physverify run examples/verify_damped_oscillator.py
```

You should see a list of checks, all passing. Now open `examples/damped_oscillator.py`, change the damping by 10%, and run the same command again: the checks fail.

To check your own code you write a short "spec" file. It tells physverify two things: the equations your code is meant to solve (written independently of your code), and how to run your code. [examples/verify_damped_oscillator.py](https://github.com/rcgiri-physics/physverify/blob/main/examples/verify_damped_oscillator.py) is a complete example to copy.

To start a spec for your own ODE solver, let physverify write one:

```bash
physverify init verify_solver.py --solver mysolver --order 4
```

Then fill in the two places marked TODO: the equations, written from the physics, and a starting state.

Other ways to run it:

```bash
physverify run my_spec.py --html report.html   # a web page with convergence plots
physverify run my_spec.py --json -             # machine-readable output
pytest my_spec.py                              # each check becomes a pytest test
```

## Run it on every push

Add physverify to your GitHub Actions workflow. The job fails when a check fails, just like a broken unit test:

```yaml
      - uses: actions/checkout@v4
      - uses: rcgiri-physics/physverify@v0.3.1
        with:
          specs: tests/verify_*.py
          install: -e .
```

The results table appears on the run's summary page. [docs/ci.md](https://github.com/rcgiri-physics/physverify/blob/main/docs/ci.md) covers the options, pre-commit and pytest.

## What it can and cannot do

- Works best for ordinary differential equations (orbits, pendulums, projectiles).
- Partial differential equations: only 1D examples so far (heat equation, shock tube).
- Your code needs a way to accept an extra source term, or a small wrapper ("adapter") around it. The wrapper can itself contain mistakes.
- Passing all checks does not prove the code is correct, only that these tests found nothing wrong.

## More

- [results/corpus/SUMMARY.md](https://github.com/rcgiri-physics/physverify/blob/main/results/corpus/SUMMARY.md): the 120 public repositories, what was tested and what was found.
- [sandbox/README.md](https://github.com/rcgiri-physics/physverify/blob/main/sandbox/README.md): the locked-down container used to run other people's code.
- [results/own_work/SUMMARY.md](https://github.com/rcgiri-physics/physverify/blob/main/results/own_work/SUMMARY.md): results on four of the author's own public physics projects (two real bugs found and fixed).
- [docs/technical.md](https://github.com/rcgiri-physics/physverify/blob/main/docs/technical.md): full details, benchmark tables, limits and related work.
- [docs/patch.md](https://github.com/rcgiri-physics/physverify/blob/main/docs/patch.md): what the exact "patch" checks assume.
- [docs/ising.md](https://github.com/rcgiri-physics/physverify/blob/main/docs/ising.md): checks for Monte Carlo codes.
- [docs/ci.md](https://github.com/rcgiri-physics/physverify/blob/main/docs/ci.md): `physverify init`, the GitHub Action, pre-commit and pytest.
- [docs/agent.md](https://github.com/rcgiri-physics/physverify/blob/main/docs/agent.md): using it with an AI coding assistant.
- [CHANGELOG.md](https://github.com/rcgiri-physics/physverify/blob/main/CHANGELOG.md)

Run the project's own tests with `pip install -e .[dev]` then `python -m pytest -q` (about 1.5 minutes).

## Citing

If physverify helps your work, please cite it: GitHub's "Cite this repository" button uses [CITATION.cff](https://github.com/rcgiri-physics/physverify/blob/main/CITATION.cff).

## Licence

MIT. Copyright (c) 2026 Ram Chandra Giri.
