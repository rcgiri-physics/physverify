---
title: Held-out measurement plan
---

# Held-out measurement plan

Written and committed on 2026-11-27, before any of the data below is collected (issue #30). Changes to
this plan after the data is seen are listed at the end, with the date and the reason.

## Why

`physverify scan` recovers 18 of the 74 defects reported in the corpus study, but its rules were written
while looking at those same repositories. That number says how well the rules fit the sample they were
tuned on, not how well they work on new code. This plan measures the scan once on repositories that were
never used to write or tune a rule.

## Frozen version

The measurement uses **physverify 0.10.0** exactly as released on PyPI, installed into a fresh virtual
environment. No rule, threshold or message is changed between the first and the last repository. A defect
found by the measurement may lead to a rule change afterwards; it is reported against 0.10.0.

## Selection rule

1. Source: public GitHub repositories found with the search `language:Python` plus one of the topic words
   `simulation`, `physics`, `numerical`, `ode`, `pde`, `monte-carlo`, `molecular-dynamics`, `cfd`.
2. Created or last pushed after 2026-11-27, so that none can have been seen while the rules were written.
3. Not in any list of repositories tested, scanned or screened for the corpus study (checked by
   owner/name against those lists before the repository is looked at).
4. At least one Python file that integrates an equation in time or space (a time loop, an ODE or PDE
   step, a Monte Carlo update), judged from the file list and README only, before the code is read.
5. Not a fork, not a course template copied many times, at most 2 repositories per owner.
6. Taken in the order the search returns them until **60** repositories qualify. Repositories that fail a
   rule are recorded with the rule they failed.

## What is measured

For each repository: run `physverify scan` (static only, no `--run`) and record every finding.

- Each finding is checked by hand against the physics, and a suspected defect is confirmed by a run that
  compares with a reference written from the physics (`physverify confirm`) before it is counted.
- **Precision:** confirmed defects / findings, per rule and overall.
- **Findings per repository**, and the share of repositories with no finding.
- Recall cannot be measured without knowing every defect, so it is estimated only on a subsample: for
  **10** repositories chosen at random (seeded with the date), the code is also tested by hand as in the
  corpus study, and the defects found that way give the share the scan finds.

Counts are given within this sample only; no general bug rate is stated.

## Seeded bugs written by someone else

Bugs written by another person for `benchmark/pvbench/problems/` (see CONTRIBUTING) are run through the
full benchmark at the frozen version and reported apart from the author's 37, with the name of the person
who wrote them if they agree.

## Report

`results/heldout/`: the list of repositories considered and why each was kept or left out, the scan
output, the hand checks, and a summary table. Repositories are named publicly only after their maintainers
confirm a defect, as in the corpus study.

## Changes to this plan

None yet.
