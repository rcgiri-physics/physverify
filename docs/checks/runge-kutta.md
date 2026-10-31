# Runge-Kutta tables

**Question:** do the coefficients of a Runge-Kutta method have the order and the stability properties the method claims?

This is pure algebra on the Butcher table (A, b, c): no test problem, no step sizes, no tolerance games. It is the check to run on a library of methods, for example in continuous integration.

```python
--8<-- "docs/examples/butcher_tables.py"
```

Output:

```text
--8<-- "docs/examples/output/butcher_tables.txt"
```

## What each part checks

| Argument | Property | How |
|---|---|---|
| `claimed` | Order: the error is O(h^(p+1)) per step on **any** smooth ODE | Butcher's order conditions, one per rooted tree with up to p vertices |
| `claimed_linear` | Linear order: the order on y' = lambda*y only | The stability function R(z) matches e^z up to z^p |
| `claimed_stage` | Stage order: how accurate the internal stages are | Simplifying assumptions C(q) and B(q); a low stage order causes order loss on stiff problems |
| `a_stable` | Stable for every decaying linear mode | \|R(z)\| <= 1 on the imaginary axis (an exact polynomial test) and no poles of R in the left half-plane |
| `l_stable` | A-stable, and very stiff modes are damped completely | A-stable and R(infinity) = 0 |
| `stiffly_accurate` | The step result is the last stage | b equals the last row of A |
| `c` given | The nodes are consistent | Each row sum of A equals c |

Each property is checked only when you state it, and a mismatch fails in either direction: claiming L-stability for the trapezoid rule fails, and so does claiming that an L-stable method is not.

## Why the linear order matters

A convergence test on y' = -y (the "Dahlquist" test equation) measures the **linear** order, which can be higher than the real order. The table above that claims order 3 is order 2 on general problems but order 3 on y' = -y, so a library whose only test is y' = -y would never notice. A public Runge-Kutta library had exactly this case; physverify found it by the order conditions, and the library now records both orders.

## Rounded coefficients

The default tolerance (1e-8) accepts coefficients typed with 9 or 10 digits. When a missing order is only a matter of too few digits, the message says so and suggests a tolerance to retry with.

## Real tables: FSAL, embedded weights, symplecticity

Codes store explicit tables in several shapes: SciPy's `RK45` keeps `A` as 6 x 5 and its error weights over a seventh (FSAL) stage. `check_tableau` pads such tables first (`square_tableau`), so they check as given. `embedded=` takes the weights of the embedded method (or SciPy-style error weights added to `b`), which must sum to 1, and `claimed_embedded=` checks their order. `symplectic=True` checks b_i a_ij + b_j a_ji = b_i b_j, which holds for the Gauss methods and for no explicit method (Hairer, Lubich and Wanner, *Geometric Numerical Integration*, Thm. VI.4.3).

`physverify.butcher.TABLES` holds RK4, Bogacki-Shampine 3(2), Dormand-Prince 5(4), the implicit midpoint rule and 2-stage Gauss with their orders, and `compare_tableau(A, b, "dormand_prince_5_4")` points to the first coefficient of a code's copy that differs from the published one, with or without the FSAL stage.

## Lower-level functions

`tableau_order`, `linear_order`, `symplectic_residual`, `stage_order`, `stability_function`, `r_infinity`, `a_stability_margin` and `is_stiffly_accurate` in `physverify.butcher` return the numbers themselves.

## Not yet covered

The extra conditions that link the explicit and implicit tables of an IMEX (additive) pair; see the [Roadmap](../roadmap.md).
