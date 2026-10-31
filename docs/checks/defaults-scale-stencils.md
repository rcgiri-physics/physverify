# Hidden defaults, scale, stencils and fluxes

**Question:** does a check that passes at the example values still pass when the example is less special, and are the pieces of a solver (its stencils, its fluxes, the size of its output) right on their own?

These helpers come from the daily corpus sessions of October 2026. Of the bugs confirmed there, most passed every check at the values the examples use and appeared only when one parameter left them, and several more were the right shape at the wrong size. Each helper returns a `Result`, like the [identities](identities.md); wrap one in `Check("limit", label, lambda: ...)` to run it with the other checks.

| Function | What it checks | Pattern it came from (corpus ids) |
|---|---|---|
| `identities.vary_one(test, defaults, changes)` | a test that passes at the defaults still passes with each parameter changed on its own | a y-derivative scaled with Lx (seen only for Lx != Ly), a Neumann row that dropped its boundary value (only for g != 0), a p-polarisation path, square grids that hid an indexing slip (L174, L177, L178, L179, L182, L193, L210) |
| `identities.check_scale(got, ref)` | the output is 1 times the reference, not k times; names k when it is 2, pi, sqrt 2, ... | a missing 1/(2 dx), a missing time step, a factor 1/2 in an inertia (L177, L182, L191, L193) |
| `stencils.check_stencil(offsets, weights, deriv, claimed=)` | a finite-difference table is consistent, has scale 1 and the claimed order, from its Taylor moments | an "8th-order" table of order 6 (L220); tables in L177, L186, L202 |
| `fluxes.check_flux(flux, physical, states, upwind_pairs=, mirror=)` | a numerical flux is consistent, upwind for supersonic flow and mirror-symmetric | a Roe flux that broke upwinding, an HLLE flux built for the wrong fluid (L221) |
| `identities.check_vec_convention(S, f, X)` | which vectorisation (row- or column-major) a superoperator follows | a Liouvillian built for one order and reshaped with the other (L204) |
| `references.zernike_osa(n, m, rho, theta)` | the Zernike polynomial in the OSA/ANSI normalisation, for orthonormality checks | a sqrt(n + 1) normalisation used for every m (L208) |

## Vary one parameter at a time

```python
import numpy as np
from physverify.identities import vary_one

def test(Lx, Ly, n):
    y = np.arange(n) * Ly / n
    f = np.sin(2 * np.pi * y / Ly)
    got = my_solver.d_dy(f, Lx=Lx, Ly=Ly, n=n)          # the code under test
    return got, 2 * np.pi / Ly * np.cos(2 * np.pi * y / Ly)  # reference from calculus

print(vary_one(test, {"Lx": 1.0, "Ly": 1.0, "n": 256}, {"Lx": 2.0, "Ly": [2.0, 3.0]}, rtol=1e-3, atol=1e-3))
```

The test returns a `Result`, a bool, or a `(got, reference)` pair. Choose the changes from what the examples keep special: an aspect ratio of 1, equal grid sizes, zero boundary data, one polarisation, vacuum, a symmetric shape, a lossless medium.

## The size of the answer

`check_scale(got, ref)` fits one factor k and the correlation. A correlation near 1 with k != 1 says the shape is right and the size is not: compare k with the grid spacing, the time step and the sampling rate of the run. A low correlation says the shape is wrong, and a plain comparison is the better check.

## Stencils

```python
from physverify.stencils import check_stencil
check_stencil([-2, -1, 0, 1, 2], [1, -8, 0, 8, -1], deriv=1, divisor=12, claimed=4)   # PASS, order 4
check_stencil([-1, 1], [-1, 1], deriv=1)    # FAIL: 2 times the first derivative (the 1/2 is missing)
```

Integer and `Fraction` weights are checked exactly. The moments are those of LeVeque, *Finite Difference Methods for ODEs and PDEs*, sec. 1.5.

## Numerical fluxes

Write the physical flux from the equations, pick a few states, and build supersonic pairs from the sound speed (|u| well above c on both sides). Consistency F(W, W) = f(W) holds for every consistent flux; upwinding F(WL, WR) = f(WL) for supersonic flow to the right holds for Roe, HLL and HLLC, but not for Rusanov (local Lax-Friedrichs), so pass `upwind_pairs` only for fluxes that claim it (Toro, *Riemann Solvers and Numerical Methods for Fluid Dynamics*, ch. 10-11).

## What these checks cannot tell you

`vary_one` tries only the changes you list. `check_scale` cannot see an error that changes the shape and the size together. A stencil with the right moments can still be applied at the wrong points or with the wrong spacing, and a flux with all three properties can still be wrong between the supersonic limits; an order study on the whole solver remains the main evidence.
