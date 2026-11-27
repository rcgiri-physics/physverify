"""2D and 3D heat equation: manufactured solutions, an order study of the whole solver, and a check of
the discrete Laplacian that says where the error is largest (corner, edge, face or interior).

The equation is u_t = kappa * laplacian(u) + f on the unit square or cube. The manufactured solution is
the sum of two products of cosines,

    u = A(t) prod_i cos(k_i x_i + phi_i) + B(t) prod_i cos(k'_i x_i + phi'_i),   A = 1 + 0.5 sin 3t,  B = e^-t,

so laplacian(u) = -|k|^2 (first term) - |k'|^2 (second term) exactly, and f = u_t - kappa laplacian(u)
follows by hand (method of manufactured solutions; Roache, Verification and Validation in Computational
Science and Engineering, 1998; Salari and Knupp, SAND2000-1444). A(t) is not exponential, so a solver
that evaluates the source at the wrong time is seen. The wave numbers are chosen per boundary type:

- "dirichlet": generic k and phi, values on the boundary taken from u;
- "neumann": k_i = m_i pi and phi = 0, so the normal derivative is zero on every face (insulated walls);
- "periodic": k_i = 2 pi m_i, so u has period 1 in every direction.

Grids are node grids with spacing h = 1/n: x_j = j h for j = 0..n (Dirichlet, Neumann) or j = 0..n-1
(periodic, the node at x = 1 is the node at 0). Arrays use numpy's "ij" indexing, axis i for x_i.

Corners and edges are where 2D and 3D codes most often go wrong (a corner not updated, a Neumann ghost
value taken from the wrong neighbour), so the checks report the kind of node where the error is largest.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from .checks import FAIL, INCONCLUSIVE, PASS, Result
from .order import check_order

BOUNDARIES = ("dirichlet", "neumann", "periodic")
_DIRICHLET = (np.array([1.3, 0.9, 1.1]), np.array([0.2, 0.5, 0.1]), np.array([2.1, 1.7, 0.8]), np.array([0.6, 0.3, 0.9]))
_NEUMANN = (np.array([1.0, 2.0, 1.0]), np.zeros(3), np.array([2.0, 1.0, 2.0]), np.zeros(3))  # times pi
_PERIODIC = (np.array([1.0, 1.0, 2.0]), np.array([0.3, 0.7, 0.2]), np.array([2.0, 1.0, 1.0]), np.array([0.1, 0.4, 0.5]))


def _modes(dim: int, bc: str):
    if bc == "dirichlet":
        k1, p1, k2, p2 = _DIRICHLET
    elif bc == "neumann":
        k1, p1, k2, p2 = _NEUMANN
        k1, k2 = math.pi * k1, math.pi * k2
    elif bc == "periodic":
        k1, p1, k2, p2 = _PERIODIC
        k1, k2 = 2 * math.pi * k1, 2 * math.pi * k2
    else:
        raise ValueError(f"bc must be one of {', '.join(BOUNDARIES)}, not {bc!r}")
    return k1[:dim], p1[:dim], k2[:dim], p2[:dim]


@dataclass
class HeatProblem:
    """One manufactured problem on one grid; this is what a solver adapter is given.

    grid: tuple of coordinate arrays (numpy.meshgrid, indexing "ij"); u0: u at t = 0 on the grid;
    exact(t), source(t), laplacian(t): arrays on the grid; boundary(t): exact values on the grid (for
    Dirichlet solvers, which take the boundary nodes from it); on_boundary: bool mask of the boundary nodes
    (all False for periodic)."""

    dim: int
    bc: str
    n: int
    h: float
    kappa: float
    t_end: float
    grid: tuple
    u0: np.ndarray
    exact: Callable[[float], np.ndarray]
    source: Callable[[float], np.ndarray]
    laplacian: Callable[[float], np.ndarray]
    boundary: Callable[[float], np.ndarray]
    on_boundary: np.ndarray


def heat_problem(dim: int, bc: str, n: int, *, kappa: float = 1.0, t_end: float = 0.1) -> HeatProblem:
    """The manufactured problem for `dim` = 2 or 3 and boundary type `bc` on a grid with n intervals."""
    if dim not in (2, 3):
        raise ValueError(f"dim must be 2 or 3, not {dim}")
    if n < 2:
        raise ValueError(f"n must be at least 2, not {n}")
    k1, p1, k2, p2 = _modes(dim, bc)
    h = 1.0 / n
    nodes = np.arange(n) * h if bc == "periodic" else np.arange(n + 1) * h
    grid = tuple(np.meshgrid(*([nodes] * dim), indexing="ij"))
    m1 = np.prod([np.cos(k1[i] * grid[i] + p1[i]) for i in range(dim)], axis=0)
    m2 = np.prod([np.cos(k2[i] * grid[i] + p2[i]) for i in range(dim)], axis=0)
    s1, s2 = float(k1 @ k1), float(k2 @ k2)

    def a(t):
        return 1.0 + 0.5 * math.sin(3.0 * t)

    def b(t):
        return math.exp(-t)

    def exact(t):
        return a(t) * m1 + b(t) * m2

    def lap(t):
        return -s1 * a(t) * m1 - s2 * b(t) * m2

    def source(t):  # u_t - kappa lap(u), with A' = 1.5 cos 3t and B' = -e^-t
        return 1.5 * math.cos(3.0 * t) * m1 - b(t) * m2 - kappa * lap(t)

    mask = np.zeros(grid[0].shape, dtype=bool)
    if bc != "periodic":
        for axis in range(dim):
            idx = [slice(None)] * dim
            for end in (0, -1):
                idx[axis] = end
                mask[tuple(idx)] = True
    return HeatProblem(dim, bc, n, h, kappa, t_end, grid, exact(0.0), exact, source, lap, exact, mask)


def node_kind(index, shape, bc: str) -> str:
    """'corner', 'edge', 'face' or 'interior' for a node, by how many of its coordinates are on the boundary.

    In 2D a node with one coordinate on the boundary is on an 'edge' (the side of the square), with two a
    'corner'; in 3D one is a 'face', two an 'edge', three a 'corner'. Periodic grids have no boundary."""
    if bc == "periodic":
        return "interior"
    on = sum(i in (0, s - 1) for i, s in zip(index, shape))
    names = {2: ("interior", "edge", "corner"), 3: ("interior", "face", "edge", "corner")}[len(shape)]
    return names[on]


def _where(err: np.ndarray, bc: str) -> str:
    idx = np.unravel_index(int(np.argmax(err)), err.shape)
    kind = node_kind(idx, err.shape, bc)
    return f"{'an' if kind[0] in 'aeiou' else 'a'} {kind} node {tuple(int(i) for i in idx)}"


def _finite_or_fail(arr, what):
    a = np.asarray(arr, dtype=float)
    if not np.all(np.isfinite(a)):
        return None, Result(FAIL, f"{what} has NaN or inf values")
    return a, None


def check_laplacian(apply, dim: int, bc: str, *, ns=(8, 16, 32), order: float = 2.0, tol: float | None = None,
                    t: float = 0.0) -> Result:
    """Does `apply(u, h)` approximate the Laplacian at the claimed order, on boundary nodes too?

    `apply` gets u on a node grid (see `heat_problem`) and returns the discrete Laplacian on the same grid.
    For Dirichlet only the interior nodes are compared (boundary values are fixed, not evolved); for zero-flux
    Neumann every node is compared, so a wrong ghost value at a face, edge or corner is seen; for periodic every
    node. The message names the kind of node with the largest error on the finest grid."""
    hs, errors, where = [], [], ""
    for n in ns:
        p = heat_problem(dim, bc, n)
        u = p.exact(t)
        try:
            got = apply(u.copy(), p.h)
        except Exception as exc:
            return Result(FAIL, f"apply(u, h) raised {type(exc).__name__}: {exc} on a {dim}D {bc} grid with n = {n}")
        got, bad = _finite_or_fail(got, f"the Laplacian on n = {n}")
        if bad:
            return bad
        if got.shape != u.shape:
            return Result(FAIL, f"apply returned shape {got.shape} for a grid of shape {u.shape} (n = {n})")
        err = np.abs(got - p.laplacian(t))
        if bc == "dirichlet":
            err = np.where(p.on_boundary, 0.0, err)
        hs.append(p.h)
        errors.append(float(err.max()))
        where = _where(err, bc)
    r = check_order(hs, errors, expected=order, tol=tol)
    return Result(r.status, f"{dim}D {bc} Laplacian against the exact Laplacian of the manufactured solution:"
                            f" {r.message}; largest error on the finest grid at {where}")


def check_heat_order(solve, dim: int, bc: str, *, ns=(8, 16, 32), order: float = 2.0, tol: float | None = None,
                     kappa: float = 1.0, t_end: float = 0.1, steps=None) -> Result:
    """Does the whole solver converge at the claimed order to the manufactured solution?

    `solve(problem, n_steps)` gets a HeatProblem and the number of time steps and returns u at t_end on the
    grid. By default n_steps grows like n^2 (dt = 0.1 h^2 / kappa, inside the stability limit h^2 / (2 d kappa) of
    explicit Euler in d = 2 or 3 dimensions), so a solver second order in space and first order in time shows order 2 in h. For an
    implicit or Crank-Nicolson solver pass `steps=lambda n: n` (dt proportional to h) and the order it then
    has in h. All nodes are compared; the message names where the largest error is on the finest grid."""
    if steps is None:
        def steps(n):
            return max(1, math.ceil(t_end * kappa / (0.1 / n**2)))
    hs, errors, where = [], [], ""
    for n in ns:
        p = heat_problem(dim, bc, n, kappa=kappa, t_end=t_end)
        n_steps = int(steps(n))
        try:
            got = solve(p, n_steps)
        except Exception as exc:
            return Result(FAIL, f"solve raised {type(exc).__name__}: {exc} on a {dim}D {bc} grid with n = {n}")
        got, bad = _finite_or_fail(got, f"the solution on n = {n}")
        if bad:
            return bad
        if got.shape != p.u0.shape:
            return Result(FAIL, f"solve returned shape {got.shape} for a grid of shape {p.u0.shape} (n = {n})")
        err = np.abs(got - p.exact(t_end))
        hs.append(p.h)
        errors.append(float(err.max()))
        where = _where(err, bc)
    r = check_order(hs, errors, expected=order, tol=tol)
    return Result(r.status, f"{dim}D {bc} heat equation, manufactured solution, dt from steps(n):"
                            f" {r.message}; largest error on the finest grid at {where}")


def check_source_balance(solve, dim: int, *, n: int = 8, q: float = 1.0, kappa: float = 1.0, t_end: float = 0.1,
                         n_steps: int = 50, rtol: float = 1e-8) -> Result:
    """Uniform source q in an insulated box (zero-flux Neumann): the mean of u must grow by exactly q t_end.

    The discrete version holds for any conservative scheme with trapezoid weights at boundary nodes, whatever
    the grid; a scheme that loses heat through an insulated wall or corner fails. `solve` is called as in
    `check_heat_order`, with u0 = 0 and source q. The mean uses the trapezoid rule (half weight on faces,
    less on edges and corners), the weights under which the usual ghost-point Neumann scheme conserves heat."""
    base = heat_problem(dim, "neumann", n, kappa=kappa, t_end=t_end)
    zero = np.zeros_like(base.u0)
    p = HeatProblem(dim, "neumann", n, base.h, kappa, t_end, base.grid, zero, lambda t: zero + q * t,
                    lambda t: zero + q, lambda t: zero, lambda t: zero + q * t, base.on_boundary)
    try:
        got = solve(p, n_steps)
    except Exception as exc:
        return Result(FAIL, f"solve raised {type(exc).__name__}: {exc}")
    got, bad = _finite_or_fail(got, "the solution")
    if bad:
        return bad
    w = np.ones(got.shape)
    for axis in range(dim):
        idx = [slice(None)] * dim
        for end in (0, -1):
            idx[axis] = end
            w[tuple(idx)] *= 0.5
    mean = float((w * got).sum() / w.sum())
    expected = q * t_end
    if expected == 0:
        return Result(INCONCLUSIVE, "q * t_end is zero, so the balance tests nothing")
    rel = abs(mean - expected) / abs(expected)
    msg = (f"uniform source {q:g} in an insulated {dim}D box: mean of u {mean:.10g}, expected q t = {expected:.10g}"
           f" (relative difference {rel:.2g})")
    return Result(PASS if rel <= rtol else FAIL, msg)
