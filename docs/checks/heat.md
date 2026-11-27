# 2D and 3D heat equation

`physverify.heat` checks a solver of u_t = kappa * laplacian(u) + f on the unit square or cube, with
Dirichlet, zero-flux Neumann (insulated) or periodic boundaries.

| Function | What it checks |
|---|---|
| `check_laplacian(apply, dim, bc)` | the discrete Laplacian `apply(u, h)` converges at the claimed order, at boundary nodes too |
| `check_heat_order(solve, dim, bc)` | the whole solver `solve(problem, n_steps)` converges to a manufactured solution |
| `check_source_balance(solve, dim)` | a uniform source in an insulated box raises the mean of u by exactly q t |
| `heat_problem(dim, bc, n)` | the manufactured problem on one grid, as given to `solve` |

The manufactured solution is a sum of two products of cosines with time factors 1 + 0.5 sin 3t and e^-t,
so its Laplacian and source are written by hand, independently of any solver. Its wave numbers make it
satisfy the boundary condition: generic for Dirichlet, cos(m pi x) for zero flux, period 1 for periodic.

Each message says where the largest error is on the finest grid: a corner, an edge, a face (3D) or the
interior. That is where 2D and 3D codes most often go wrong: a corner not updated, or a Neumann ghost value
taken from the wrong neighbour.

```python
import numpy as np
from physverify.heat import check_heat_order

def solve(problem, n_steps):          # your solver, wrapped
    p = problem
    dt = p.t_end / n_steps
    u = p.u0.copy()
    for k in range(n_steps):
        u = my_step(u, p.h, dt, p.kappa, p.source(k * dt))
        if p.bc == "dirichlet":
            u = np.where(p.on_boundary, p.boundary((k + 1) * dt), u)
    return u

print(check_heat_order(solve, 2, "dirichlet"))
```

## Time step

By default the number of steps grows like n^2 (dt = 0.1 h^2 / kappa, stable for explicit Euler in 2D and
3D), so a solver second order in space shows order 2 in h whatever its time order. That hides a wrong
source time: test the time order separately, for example with `steps=lambda n: n` on an implicit or
Crank-Nicolson solver and the order it then claims in h.

## What it does not cover

Non-uniform grids, Robin or mixed boundary conditions, and non-rectangular domains. The wave and
advection-diffusion equations are not covered yet.
