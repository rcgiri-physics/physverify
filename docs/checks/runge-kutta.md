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

Looking for a method's coefficients? [runge-kutta-catalog](https://github.com/rcgiri-physics/runge-kutta-catalog) ([doi:10.5281/zenodo.24412889](https://doi.org/10.5281/zenodo.24412889)) lists 823 Runge-Kutta and 88 Rosenbrock tables from open-source libraries, each checked with these functions, with the method's first published source where it was compared.

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

Some codes store the error weights b - embedded instead (the local error is h * sum e_i k_i). Pass those as `error_weights=`: they must sum to 0, and a set that sums to 1 means the embedded solution was stored where its difference from `b` was needed, so the "error" is a whole step and the step-size controller takes far too small steps (found in one library in 2026).

## IMEX and additive (ARK) pairs

`check_additive([A_E, A_I], [b_E, b_I], [c_E, c_I], claimed=p)` checks the order of the pair, coupling conditions included: b of the root's part times Phi(t) must equal 1/gamma(t) for every rooted tree up to order p with every colouring of its vertices by the parts (Kennedy and Carpenter 2003, Appl. Numer. Math. 44, sec. 2). Checking each part with `check_tableau` misses the mixed trees: two different fourth-order methods on the same nodes have order 4 each and only order 2 as a pair. The message says whether the parts alone or only the coupling fall short. Parts with different nodes c (from `cs`, or from the row sums when `cs` is not given) are reported: the conditions are complete for an autonomous problem, but when each part evaluates f at its own time t + c h further conditions apply, which are not checked.

## Dense output

`check_dense_output(A, b_of_theta, claimed=q)` checks a continuous extension y0 + h sum b_i(theta) k_i: for every tree up to order q and theta in [0, 1], sum b_i(theta) Phi_i(t) = theta^|t| / gamma(t) (Hairer, Norsett and Wanner I, sec. II.6). `b_of_theta` is a function of theta; for one point value, such as the midpoint some codes feed into an interpolating polynomial, pass the weights and `thetas=[0.5]`. Values between steps are only as accurate as this order: a midpoint value of order 1 in a third-order solver made its outputs 4e4 times the tolerance. It is checked at sampled points, by default theta = 0, 0.1, ..., 1 (both endpoints included), and the message lists them; pass `thetas=` for others. `dense_order` returns the number. A fixed weight vector needs `thetas=[theta]`; weights over an extra FSAL stage, as SciPy stores `RK45.P`, need `b=`, the step's weights.

## Rosenbrock and W-methods

`check_rosenbrock(alpha, gamma, b, claimed=p)` checks a Rosenbrock method (I - h gamma_ii J) k_i = h f(y + sum alpha_ij k_j) + h J sum gamma_ij k_j, with `gamma` the full lower-triangular matrix including the diagonal. With the exact Jacobian the conditions are the Runge-Kutta ones with alpha + Gamma on the edge below a vertex with one child (Hairer and Wanner II, sec. IV.7). With `w_method=True` the order holds for any matrix in place of J: each single-child edge is marked alpha or Gamma, every marking of every subtree counts (1, 2, 5, 13, 37 conditions at orders 1-5, `w_condition_count`), the unmarked one must give 1/gamma(t) and every other 0. `embedded=` needs `claimed_embedded=`. `c=` and `d=`, when a code stores the stage times and the coefficients of h df/dt, must equal the row sums of alpha and Gamma: the order conditions are for autonomous problems and cannot see them, and Boost.odeint's `rosenbrock4` stores d4 with the wrong sign, which drops non-autonomous problems to first order. R(inf) and the A-stability margin come from the Runge-Kutta method (alpha + Gamma, b). `rosenbrock_residuals` returns the residuals. Tables stored in Hairer's transformed form (A = alpha Gamma^-1, C = diag(1/gamma) - Gamma^-1, m = b Gamma^-1) convert back with Gamma = (diag(1/gamma) - C)^-1.

## Lower-level functions

`tableau_order`, `linear_order`, `symplectic_residual`, `stage_order`, `stability_function`, `r_infinity`, `a_stability_margin` and `is_stiffly_accurate` in `physverify.butcher` return the numbers themselves.

## Not yet covered

Stiff-order and stage-order conditions of IMEX pairs, the time conditions of pairs with different nodes, and stiff (B-convergence) conditions of Rosenbrock methods; see the [Roadmap](../roadmap.md).
