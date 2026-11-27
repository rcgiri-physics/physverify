# physverify mutate

A PASS means more when the same spec is shown to fail on broken code. `physverify mutate` breaks the solver
on purpose, one small change at a time, and runs your specs on each broken copy.

```
physverify mutate verify_solver.py --target solver.py
```

The changes made in the target file:

- every non-zero numeric constant scaled by 1.1, keyword defaults (`theta=0.5`) and keyword arguments included;
- `+` swapped with `-`, and `*` with `/`;
- `<` swapped with `<=`, and `>` with `>=` (an off-by-one in a loop or a stopping test);
- a constant index moved by one, away from zero (`y[0]` to `y[1]`, `y[-1]` to `y[-2]`);
- a unary minus dropped.

Changes that cannot alter the result are not made (`x * 1` to `x / 1`). Other constants inside an index or slice (`y[1:]`) or a `range(...)` call are left alone: changing them mostly gives an
`IndexError` or a shorter loop. Each change is reported as CAUGHT (a check failed, or the spec could not
run), TIMEOUT (counted as caught), NOT RUN (the specs never run that line, found by tracing the run on
the unchanged code, so the change is not tried) or SURVIVED (every check passed). The exit code is 0
when everything was caught and 1 otherwise; 2 when the specs do not pass on the unchanged code, since a mutation run then
says nothing.

**This runs the code under test** (trusted code or the sandbox only). The target file is changed in place
during the run and restored afterwards, also when the run is stopped with Ctrl-C. Keep it under version
control anyway.

`--json FILE` (or `--json -` for stdout) writes one record per change, with the counts, so that
mutation scores can be kept and compared.

## Reading the survivors

A survivor is either a gap in the specs or a change that does not alter what the code computes (an
equivalent mutant). Look at each one before calling it a gap. A NOT RUN line is a clearer case: no
test runs that code at all.

On `examples/damped_oscillator.py` the example spec catches 22 of 25 changes. The three survivors all
change the stage time in `rhs(t + 0.5 * h, mid)`. The oscillator's right-hand side does not depend on t,
so these changes do not alter the result for that problem, but they would for a forced one: the
spec only exercises the stage time through the source term. This is the reason AGENTS.md asks for a
problem where f depends on t.

## Prior work

Mutation testing of numerical code: R. Wu and D. Mitchell, *Mutant Accuracy Testing* (NSV 2019).
fineness (on PyPI) counts a check only after it has been shown that it can fail. See
[related work](related-work.md).
