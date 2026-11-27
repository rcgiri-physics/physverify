"""2D and 3D heat checks, on reference solvers written here from the textbook five- and seven-point schemes."""

import numpy as np
import pytest

from physverify.heat import (
    check_heat_order,
    check_laplacian,
    check_source_balance,
    heat_problem,
    node_kind,
)


def laplacian(u, h, bc, corner_bug=False):
    """Second-order central Laplacian. Neumann: mirror ghost nodes (u_-1 = u_1), periodic: wrap."""
    out = np.zeros_like(u)
    for axis in range(u.ndim):
        if bc == "periodic":
            out += (np.roll(u, 1, axis) - 2 * u + np.roll(u, -1, axis)) / h**2
        else:
            pad = np.pad(u, [(1, 1) if a == axis else (0, 0) for a in range(u.ndim)], mode="reflect")
            lo = np.take(pad, range(0, u.shape[axis]), axis)
            hi = np.take(pad, range(2, u.shape[axis] + 2), axis)
            out += (lo - 2 * u + hi) / h**2
    if corner_bug and bc == "neumann":  # a code that forgets the second direction at corners
        idx = tuple(0 for _ in range(u.ndim))
        out[idx] *= 0.5
    return out


def ftcs(problem, n_steps, corner_bug=False):
    """Explicit Euler in time, central in space."""
    p = problem
    dt = p.t_end / n_steps
    u = p.u0.copy()
    for k in range(n_steps):
        t = k * dt
        u = u + dt * (p.kappa * laplacian(u, p.h, p.bc, corner_bug) + p.source(t))
        if p.bc == "dirichlet":
            u = np.where(p.on_boundary, p.boundary(t + dt), u)
    return u


@pytest.mark.parametrize("dim", [2, 3])
@pytest.mark.parametrize("bc", ["dirichlet", "neumann", "periodic"])
def test_correct_laplacian_and_solver_pass(dim, bc):
    assert check_laplacian(lambda u, h: laplacian(u, h, bc), dim, bc).status == "PASS"
    ns = (6, 12, 24) if dim == 3 else (8, 16, 32)
    r = check_heat_order(ftcs, dim, bc, ns=ns)
    assert r.status == "PASS", r.message


def test_neumann_corner_bug_is_found_and_located():
    r = check_laplacian(lambda u, h: laplacian(u, h, "neumann", corner_bug=True), 2, "neumann")
    assert r.status == "FAIL" and "corner node (0, 0)" in r.message, r.message


def test_wrong_kappa_in_one_direction_fails():
    def bad(problem, n_steps):
        p = problem
        dt = p.t_end / n_steps
        u = p.u0.copy()
        for k in range(n_steps):
            lap = laplacian(u, p.h, p.bc)
            ux = (np.roll(u, 1, 0) - 2 * u + np.roll(u, -1, 0)) / p.h**2
            u = u + dt * (p.kappa * (lap + 0.1 * ux) + p.source(k * dt))
        return u
    assert check_heat_order(bad, 2, "periodic").status == "FAIL"


@pytest.mark.parametrize("dim", [2, 3])
def test_source_balance(dim):
    assert check_source_balance(ftcs, dim).status == "PASS"

    def leaky(problem, n_steps):
        u = ftcs(problem, n_steps)
        u[(0,) * dim] = 0.0  # heat lost at one corner
        return u
    assert check_source_balance(leaky, dim).status == "FAIL"


def test_node_kinds():
    assert node_kind((0, 0), (5, 5), "dirichlet") == "corner"
    assert node_kind((0, 2), (5, 5), "dirichlet") == "edge"
    assert node_kind((0, 2, 2), (5, 5, 5), "neumann") == "face"
    assert node_kind((0, 4, 2), (5, 5, 5), "neumann") == "edge"
    assert node_kind((0, 0), (5, 5), "periodic") == "interior"


def test_manufactured_solution_satisfies_its_boundary_condition():
    slopes = []  # the one-sided slope at x = 0 is O(h) when the normal derivative is zero
    for n in (32, 64):
        u = heat_problem(2, "neumann", n).exact(0.3)
        slopes.append(np.abs(u[1] - u[0]).max() * n)
    assert 1.8 < slopes[0] / slopes[1] < 2.2
    q = heat_problem(3, "periodic", 16)
    assert q.u0.shape == (16, 16, 16) and not q.on_boundary.any()
    with pytest.raises(ValueError):
        heat_problem(2, "robin", 8)
