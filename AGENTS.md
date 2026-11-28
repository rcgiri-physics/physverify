# Notes for AI coding assistants

This file is for an AI assistant (Claude Code, Codex, Cursor, Copilot and others) that is asked either to **check a project with physverify** or to **change physverify itself**. People are welcome to read it too.

## Checking someone's project with physverify

physverify is code verification for numerical simulation: it tests whether code behaves as the mathematics predicts. Reading code produces many claims and cannot tell the right ones from the wrong ones (in one study of 119 AI review claims, check runs showed 10 were wrong, and 18 stayed unsettled even after a check was attempted). Call something a bug only when a check fails against an independent reference; when no such check can be built, say the claim is open.

1. Install into a virtual environment: `python -m venv .pv && . .pv/bin/activate && pip install physverify` (on Windows `.pv\Scripts\Activate.ps1`).
2. Find what the code claims: the equations, the order of accuracy, what is conserved, the coefficient tables and their sources.
3. Write the reference from the physics: the README, the paper, a textbook. Never derive it from the code under test, or a bug in the code is copied into the reference and the check passes. Say where each equation came from.
4. Pick the check that answers the question, and write it as a pytest test the project can keep:

   | Question | Check |
   |---|---|
   | Does the error shrink at the claimed order? | `check_order(hs, errors, expected=p)` on errors you measured |
   | Does a fixed-step ODE solver solve these equations? | a spec from `physverify init`, run with `physverify run` or pytest; add `quantity=` for conservation |
   | Do Runge-Kutta coefficients have the claimed order? | `physverify.butcher.check_tableau(A, b, c, claimed=p)` |
   | Does it match a closed-form result? | `physverify references` lists exact solutions |
   | Is energy, mass or heat kept? | the conservation and budget checks in `docs/checks/conservation.md` |

   Always include a problem where f depends on t (for example y' = y cos t): a wrong stage time or a missing df/dt term is invisible on y' = lambda y.
5. `physverify run`, `physverify smoke`, `confirm` and the hook **run** the code. Use them only on code the user trusts, or inside the container in `sandbox/` (see `sandbox/README.md`). `physverify scan PATH` reads without running and can point at places worth testing, but a clean scan says little.
6. When a check fails, suspect the test first: units, sign conventions, time origin, the step counts, CODATA edition. `docs/troubleshooting.md` and `docs/pitfalls.md` list the mistakes that were made most often. In the corpus study, adapters written with an AI assistant were wrong about 28 times before they were right.
7. Report what was tested and what was not. A PASS is a bounded claim (`docs/assumptions.md`).
8. Do not post issues, comments or pull requests on other people's projects without the user's explicit approval of the exact text.

Useful entry points: `physverify demo`, `physverify init` (a starter spec), `physverify references` (exact solutions), `docs/recipes.md`, `examples/verify_damped_oscillator.py`.

## Working on physverify itself

- Install with `pip install -e ".[dev]"` and run `python -m pytest -q` before and after a change. Slow tests are marked `slow`.
- `tests/test_seeded_bugs.py` and `tests/test_figures.py` compare with committed files in `results/`; if a change alters them on purpose, run `python scripts/reproduce_all.py` and commit the new files.
- `tests/test_docs_examples.py` re-runs `docs/examples/` and compares with `docs/examples/output/`.
- The installed package (`src/physverify/`) holds only the checks and uses only NumPy at import time; the benchmark lives in `benchmark/pvbench/` and is not installed.
- Keep the scope in `ROADMAP.md`: deepen ODE/PDE time integration, convergence and conservation before adding new families. Statistical checks need a measured false-alarm rate.
- Every message a check prints should say what was tested, in plain words. Match the style of the surrounding code: short docstrings that say where a rule came from.
- Never state a general bug rate for physics code from the corpus results; give counts within the stated sample only.
- Plain commit messages; follow `CONTRIBUTING.md`.
