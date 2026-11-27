# Survivors reviewed by hand (2026-11-27, physverify 0.10.0.dev, issue #101)

32 changes survived (summary.md). Each was read against the code; they fall into four groups.

| Group | Count | Changes |
|---|---|---|
| In the seeded-bug branch of `a if "bug" in bugs else b`: the line runs, that branch never does | 20 | projectile 94 (3); pendulum 96, 98; kepler 65 (2), 66, 71, 73; heat1d 131, 136 (2), 137, 146 (3); sod 189 (3) |
| No effect at these parameter values | 2 | pendulum 97 (`(m1 + m2) * L1` with L1 = 1); kepler 70 (`+ eps2` with eps2 = 0) |
| A guard or comparison whose boundary case never occurs | 5 | projectile 158 (2, the 100 s landing limit), 161 (`< 0` to `<= 0`); sod 207, 210 |
| A different scheme that is still consistent and stable, so it converges at the same order | 5 | heat1d 132 (smaller time step); sod 205 (time step); sod 215 (10% more Rusanov dissipation); sod 191 (2, cell centres moved, with the exact solution evaluated at the same points) |

The first three groups cannot change what these specs compute: 27 of the 32 are equivalent for these specs.
Not counting them, the specs catch 122 of the 154 changes on lines they run, and 122 of 127 that can change
the result.

The last group is a real limit of order-of-convergence checks: a scheme that differs by a consistent term
(more dissipation, another stable time step) still converges at its order, to the same solution. Only an
accuracy requirement at a fixed resolution (`check_order(..., atol=...)`) or a comparison with a
known-good error constant would see it. That is a choice for each spec, not a defect of the checks.

Possible improvement of `mutate` (not done): treat the branch of a conditional expression that never ran
as NOT RUN. Line tracing cannot see it; branch events in `sys.monitoring` (Python 3.12+) could.
