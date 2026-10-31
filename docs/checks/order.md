# Order of convergence

**Question:** does the error shrink as fast as the method promises?

Every study on this site ends in `check_order(hs, errors, expected)`. If you already run your own convergence study, you can call it directly.

```python
--8<-- "docs/examples/check_order_direct.py"
```

Output:

```text
--8<-- "docs/examples/output/check_order_direct.txt"
```

## How the verdict is decided

- The observed order is fitted on the finest resolutions (`fit_points`, default 4) whose errors are above the round-off floor.
- **PASS** when it lies within `tol_low` below and `tol_high` above the expected order (defaults 0.3 and 1.0; `tol=` sets both). Higher than expected is allowed, because some problems superconverge.
- **EXACT** when every error is below the floor (default 1e-12, scaled by the solution's size): the code reproduced the solution, so the order cannot be measured.
- **INCONCLUSIVE** when fewer than two errors are above the floor. The message says so, and that coarser resolutions are needed.

## Choosing step sizes

- Use at least four resolutions, each twice the previous.
- Keep the finest error well above round-off (about 1e-11). For a 4th-order method that often means *coarser* steps than you would use in production.
- Count steps, do not test times: run exactly `n` steps of size `t_end / n`. See [Convergence-study pitfalls](../pitfalls.md).

## How sure is the fitted order?

`physverify.order.fit_order_error(hs, errors)` returns the fitted order with its standard error from the scatter about the line: 3.9 with 0.05 supports order 4, 3.9 with 0.6 supports nothing yet. For three solutions of a quantity on grids refined by a constant ratio, `gci(f_fine, f_medium, f_coarse, r)` gives the observed order, the Richardson extrapolate and the grid convergence index, a relative error band on the fine solution (Roache 1994; Celik et al., *J. Fluids Eng.* 130, 078001, 2008), and says when the convergence is oscillatory.
