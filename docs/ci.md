# Running physverify in CI

A spec file can run on every push, so that a change which breaks the physics fails the build the same way a broken unit test does. This page covers starting a spec (`physverify init`), the GitHub Action, pre-commit, and plain pytest.

## 1. Start a spec

For a fixed-step ODE solver:

```bash
physverify init verify_solver.py --solver mysolver --function integrate --dim 2 --order 4
```

This writes `verify_solver.py`. It needs two things from you, both marked TODO:

- `reference_rhs(t, y)`: the equations the solver is meant to solve, written from the physics, not copied from the solver. A copied mistake passes every check.
- `Y0`: a typical initial state.

The solver function must have the form `integrate(source, y0, t_end, n_steps)`, take fixed steps from t = 0, and add `source(t)` to the right-hand side wherever it evaluates it. If it has no such hook, write a small wrapper in the spec that adds one (see [`src/physverify/adapters/projectile_v2.py`](../src/physverify/adapters/projectile_v2.py)).

The spec checks the claimed order with a manufactured solution and against an independent solution of `reference_rhs`, and runs the exactness (`patch`) check, which holds for explicit Runge-Kutta methods; remove that check for other kinds of stepper. Until `reference_rhs` is written, every check reports ERROR.

For PDE codes, Monte Carlo codes and Runge-Kutta tables there is no template yet; start from the examples in [`examples/`](../examples) and [docs/technical.md](technical.md).

## 2. GitHub Actions

```yaml
# .github/workflows/physverify.yml
name: physverify
on: [push, pull_request]
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: rcgiri-physics/physverify@v0.3.1
        with:
          specs: tests/verify_*.py   # default: **/verify_*.py
          install: -e .              # your package and its dependencies
```

Which tag to use: `@v0.3.1` runs exactly that version until you change it. `@v0` always runs the newest 0.x release, so you get fixes (and new checks, which can turn a passing job red) without editing the workflow.

The job fails when any check is not PASS or EXACT, or when no spec matches. The result table appears on the run's summary page, and an HTML report with convergence plots is uploaded as an artifact.

Inputs:

| Input | Default | Meaning |
|---|---|---|
| `specs` | `**/verify_*.py` | Spec files or glob patterns, separated by spaces. |
| `install` | empty | Arguments for `pip install` for your own code, for example `-e .` or `-r requirements.txt`. |
| `python-version` | `3.12` | Python to set up. Empty uses the Python already on the runner, for example one your job set up with its own dependencies. |
| `version` | empty | physverify version from PyPI. Empty installs the copy at the action's ref, so `@v0.3.1` runs physverify 0.3.1. |
| `working-directory` | `.` | Folder to run in. |
| `html-report` | `physverify-report` | Name of the uploaded HTML report. Empty uploads nothing. |

The output `json` is the path of the JSON results file, for a later step that wants the numbers.

If your job already sets up an environment (conda, a compiled extension), set `python-version: ""` and run the action after that set-up. Or skip the action and run the command yourself:

```yaml
      - run: pip install physverify
      - run: physverify run "tests/verify_*.py" --markdown "$GITHUB_STEP_SUMMARY" --html physverify.html
```

## 3. pre-commit

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/rcgiri-physics/physverify
    rev: v0.3.1
    hooks:
      - id: physverify
        args: ["tests/verify_*.py"]
        additional_dependencies: [scipy]   # whatever your solver imports besides NumPy
```

pre-commit runs hooks in their own environment, so your solver's dependencies must be listed in `additional_dependencies`. The hook runs on every commit that changes a Python file, because a change to the solver matters as much as a change to the spec.

## 4. pytest

With physverify installed, pytest collects the checks in `verify_*.py` files as tests, so an existing pytest job runs them with no change:

```bash
pytest tests/verify_solver.py
```

## Command-line options used in CI

- `physverify run` exits 0 when every check passes, 1 when any does not, and 2 when a spec cannot be loaded or a pattern matches nothing.
- Glob patterns are expanded by physverify, so `"**/verify_*.py"` works the same in bash, PowerShell and cmd.
- `--markdown FILE` appends a result table to `FILE`; `--json FILE` and `--html FILE` write the other formats.
