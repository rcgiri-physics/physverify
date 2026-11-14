# Results on real code

## Seeded bugs

To test physverify itself, 37 bugs were added one at a time to five small solvers (projectile, double pendulum, planet orbit, heat equation, shock tube):

- **35 of 37** bugs were caught; plain "compare with one answer" tests caught 27.
- **No false alarms** on the bug-free versions.
- For the Monte Carlo checks, all 21 seeded bugs were caught, with no false alarms.

The bugs and the checks were written by the same person, so these numbers show the tool works as designed. They are not a promise about bugs in other people's code. The tables are in [Technical details](technical.md).

## Public repositories

Public Python physics repositories from GitHub were run in a locked-down container from October 2026: no network, the repository read-only, nothing from it run on the author's computer. Every FAIL was checked by hand before it was called a bug.

| Sample | How it was chosen | Tested | Confirmed bugs |
|---|---|---|---|
| Batches 1-4 | 40 drawn at random from physics topic searches | 20 of 40 | 9 bugs in 6 repositories |
| Batch 5 | the 60 newest small repositories whose README says the work is complete | 32 of 60 | 6 bugs in 5 repositories |
| Batch 6 | 20 picked because they are quick to test | 16 of 20 | 1 bug |
| Batch 7 | 450 recently active small repositories from 61 topic searches, by stars | 182 of 450 | at least one confirmed defect in 41 |
| Batch 8 | 60 popular, maintained computational-physics libraries (by stars and use), October 2026 | 60 of 60 | a report posted to 15 (17 reports) |
| Batch 9 (daily sessions, from 2026-10-26) | repositories of people who replied to earlier reports, their other projects and listed physics projects; a few earlier repositories tested again in depth | 266 of 396 | a report posted to 104 (121 reports) |

Only batches 1-4 are random; batches 8 and 9 were chosen on purpose and say nothing about physics code in general. Most untested repositories were not numerical solvers (neural networks, apps and games, analysis tools, finance) or could not be installed in the sandbox. For batches 8 and 9 the last column counts reports posted to the authors by 2026-11-08 (most are defects; a few are questions or documentation points), not every finding.

Examples of what was found:

- Runge-Kutta coefficient tables labelled with a higher order than they have.
- Backward time-stepping that is only first-order accurate.
- A measured energy that counts the magnetic-field term twice.
- Boundary values applied after the linear solve instead of inside it; an insulated wall that leaks heat; a grid spacing off by one interval.
- A Kepler solver that fails for negative angles.
- MHD shock jump ratios that break the Rankine-Hugoniot conditions; a reactor period for negative reactivity off by a factor of several thousand; a pressure solver that stops after one sweep.

The adapters written to test these codes were themselves wrong about 28 times before checking (a wrong constant, too-coarse steps, a wrong sign convention). These mistakes are recorded too, and each lesson became a check or a clearer message in physverify.

### What found each bug

Of the 74 defects reported to authors, 14 were found by a physverify check as such (an order study, Butcher order conditions, a conservation check), 11 by simply running the code, 37 by the reference written in the test script for that repository, and 12 by reading the code and then confirming with a run. So most of the finding was done by the person writing the test, with physverify running it. The new `physverify scan`, which needs no script, recovers 18 of the 74, and when the cloned repositories were scanned again it found 7 new defects, each then confirmed by a run.

| `physverify scan` version (all on 2026-10-23) | Of the 74 found with no script | New defects (confirmed by a run) |
|---|---|---|
| First version | 2 | 0 |
| After the first triage | 3 | 4 grid mismatches (3 confirmed) |
| Runge-Kutta stages written as code | 6 | 7 |
| Tables in constructors and classes | 9 | 7 |
| Phase 1 static checks (names, removed APIs, literals, exact constants, units) | 18 | 7 (and static marks in about 80 repositories, not yet confirmed by runs) | How often each check applies and what it finds there: [per-feature results](https://github.com/rcgiri-physics/physverify/blob/main/results/corpus/FEATURES.md). Details: [which found what](https://github.com/rcgiri-physics/physverify/blob/main/results/corpus/FINDINGS_BY_METHOD.md) and [the rescan](https://github.com/rcgiri-physics/physverify/blob/main/results/corpus/RESCAN_2026-10.md).

### AI review, confirmed by runs (100 repositories, 2026-11)

A pilot on 20 repositories (2026-11-08) grew into a study on 100: 50 with a defect reported earlier and 50 tested clean, each reviewed by five AI models with one fixed prompt and scanned with `physverify scan`. On the clean 50, 119 claims were each checked by a run: 40 changed a result (33 distinct defects in 19 repositories), 51 were real but minor, 10 were wrong and 18 could not be settled. Against the 67 earlier defects the models named 36 to 49 and `scan` 11. Details and the verdict table: [Checking an AI code review](ai-review.md).

So reading finds more candidates than static rules, and running against a reference decides which are real. This is why the [roadmap](roadmap.md) puts confirming suspected defects first. By 2026-11-08, 194 reports had been posted to authors in 174 repositories; the breakdown by method above covers the first 74, listed one row per defect in the [ledger](https://github.com/rcgiri-physics/physverify/blob/main/results/corpus/LEDGER.md).

!!! note "Not a bug rate"
    These counts describe the repositories that were drawn. They are not a bug rate for physics code in general.

Authors are told about a finding before their project is named, so repositories are listed by ID. Until they can be named, others cannot rerun these results themselves; the seeded-bug benchmark above, by contrast, is fully reproducible with `python scripts/reproduce_all.py`. Lists: [batches 1-6](https://github.com/rcgiri-physics/physverify/blob/main/results/corpus/SUMMARY.md) and [batch 7](https://github.com/rcgiri-physics/physverify/blob/main/results/corpus/BATCH7.md). The testing and write-ups were done with help from an AI assistant; every number comes from running the code.
