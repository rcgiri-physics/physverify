# Troubleshooting

When a check fails, the bug may be in your code, but it may also be in the spec or the adapter. When physverify was run on public physics repositories, the adapters written for them were wrong about 28 times before checking, so look at these first.

## Is it my code or my spec?

1. **Run `physverify demo`.** If it does not show 4 of 4 passed and then 0 of 4, the installation is the problem.
2. **Read the message, not only the status.** Each verdict says what was measured and what was expected, and often what to try next.
3. **Check the reference equations against the physics,** not against your code: signs, factors of 2, units. A wrong reference makes a correct code FAIL; a reference copied from the code makes a wrong code PASS (see [What a PASS means](assumptions.md)).
4. **Check the adapter.** It must add `source(t)` exactly where the solver evaluates the right-hand side, at the same times (stage times for Runge-Kutta), and take exactly `n_steps` steps from 0 to `t_end`.
5. **Change one thing and rerun.** If a check flips when you change the spec but not the solver, the spec was the problem.

## Common messages

| Message | Usual cause | What to try |
|---|---|---|
| observed order a bit below the expected one, pairwise orders still rising | Steps too coarse (pre-asymptotic) | Finer steps, larger `ns` |
| observed order higher than expected | The method converges faster on this problem, or the claimed order is too low | Check the claim; a smooth or symmetric test case can show super-convergence |
| error does not decrease with resolution | A real bug, or a wrong constant or sign in the reference, or comparing at the wrong time | Compare the reference with the physics; see [pitfalls](pitfalls.md) |
| the error is the same at every resolution | Something independent of the step: a wrong constant, a reference for a different problem, a potential cutoff | Check constants and the problem set-up |
| INCONCLUSIVE, fewer than 2 resolutions above the noise floor | Errors already at round-off | Coarser steps, or a longer `t_end` |
| INCONCLUSIVE, all step sizes are the same / must be positive | `h` computed wrongly in a hand-written study | Print the step sizes |
| ERROR | The solver or adapter raised an exception | The message has the exception; often a shape mismatch between `source(t)` and the state |
| patch check FAIL on a correct code | The method cannot reproduce that solution exactly (not an explicit Runge-Kutta method, or a nonlinear term) | Remove the patch check; see [patch test theory](patch.md) |
| SKIP | An optional package (for example SymPy) is missing | Install it, or ignore |

## Mistakes recorded in practice

From the adapters written for public repositories (details in [results/corpus/SUMMARY.md](https://github.com/rcgiri-physics/physverify/blob/main/results/corpus/SUMMARY.md)):

- a sign convention that differed from the course the code was written for;
- a constant copied wrongly from the paper;
- an expected order set too low (the code converged faster) or too high;
- steps too coarse for the asymptotic range;
- a comparison point at a singular corner of the domain;
- an unweighted error norm where the code's own results used a weighted one;
- an energy tolerance set without a reason;
- a measurement after a whole orbit, where the error happens to cancel.

Each one was found before anything was reported, and each became a test in `tests/test_corpus_lessons.py` or a clearer message.

## Reference mistakes when testing libraries

Testing 20 widely used libraries (astronomy, meteorology, optics, fluids, units, particle data and others) gave about 25 first-run failures, and every one was a mistake in the adapter, not in the library. They fall into a few groups worth checking before you suspect the code:

| What went wrong | Example | What to do |
|---|---|---|
| Units of the returned value | A particle mass compared in GeV, returned in MeV; a spectral radiance per metre compared with one per nanometre | Print the value with its units from the documentation before comparing |
| Frame or origin of a coordinate | A ray position measured from the image plane, compared with a distance from the lens; geometric altitude passed where the standard atmosphere is tabulated in geopotential altitude | Find where zero is for every coordinate you compare |
| A convention or standard the library follows on purpose | The four-decimal sRGB matrices of IEC 61966-2-1, which are not exact inverses; CIE's rounded c₂ = 1.4388e-2; the ISO British thermal unit; gauss as a Gaussian-system unit | Look for the standard the code cites; a difference at the level of its rounding is not a bug |
| A model that does not reduce to the limit you assumed | The Klucher sky model does not give the horizontal irradiance on a flat panel; an asymptotic matrix-element ratio checked away from its limit | Check the limit in the model's own paper |
| The reference formula itself | A Bragg-mirror reflectance with the admittance inverted; an ideal (van't Hoff) osmotic pressure for a real solution with osmotic coefficient 0.97 | Derive it a second way, or check it on a case with a known answer |
| A remembered constant | A clear-sky constant of 0.057 where the published form uses 0.059 | Look the number up; do not rely on memory |
| Python operator precedence | `(a ^ b) ^ c - d` parses as `(a ^ b) ^ (c - d)` | Parenthesise outer products and bitwise operators |
| The tool used for the comparison | A finite-difference grid too coarse to locate a peak; a comparison helper that converted complex values to float | Test the comparison on a case you can do by hand |
| Old constants the library vendors | CODATA 2014 values kept so results stay reproducible | Record it as a note; a 1e-6 difference is a convention, not a bug |

## A suspicion from reading code is not a bug until a run confirms it

Code review finds candidates quickly, but in the same study two of the strongest suspicions from reading turned out wrong when run: a claimed missing term in a thermodynamic derivative agreed with finite differences to 1e-10, and a claimed energy error had the opposite sign to the one predicted. Before reporting anything found by reading, run the function and compare it with an independent computation, for example with `check_derivative`, `check_roundtrip` or `check_agree` (see [Identities and round trips](checks/identities.md)). Report the measured numbers, not the reasoning.

## Still stuck?

Open an issue with your spec and the output ([bug report template](https://github.com/rcgiri-physics/physverify/issues/new?template=bug_report.md)). Questions about whether a result is right are welcome too.

## "physverify: note: the reference ... uses ..."

`physverify run` read the spec before running it and found a function whose name says it is a reference (`exact`, `reference`, `analytic`, `expected`, `*_ref`) using a module the spec imports as the code under test. A reference computed with the solver passes even when the solver is wrong. Derive it from the physics, or, if the use is safe (a table of constants, a unit), say so in a comment; the note does not change the verdict.
