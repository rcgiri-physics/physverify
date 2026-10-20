"""`physverify init`: write a starter spec for a fixed-step ODE solver.

The spec it writes runs as soon as the user has written `reference_rhs` (the
equations, from the physics rather than from the solver) and a typical
initial state. Everything else (the manufactured solution, the step counts
for the claimed order, the exactness check) is filled in.
"""

from __future__ import annotations

from pathlib import Path

TEMPLATE = '''"""physverify spec for {module}.{function}, written by `physverify init`.

Fill in the two places marked TODO, then run:

    physverify run {spec_name}

{module}.{function} must have the form

    {function}(source, y0, t_end, n_steps) -> state at t_end

taking n_steps fixed steps from t = 0 and adding source(t), an array of
length {dim}, to the right-hand side wherever the solver evaluates it. If the
solver has no such hook, write a small wrapper in this file that adds one and
pass the wrapper to ode_checks instead.
"""

import numpy as np

import {module} as solver
from physverify import ManufacturedODE, ode_checks

DIM = {dim}
ORDER = {order!r}  # the order the solver claims: Euler 1, midpoint 2, RK4 4
T_END = {t_end!r}
NS = {ns!r}  # step counts for the order study


def reference_rhs(t, y):
    """TODO: dy/dt for the equations the solver is meant to solve.

    Write it from the physics (the paper, the textbook, your notes), not by
    copying the solver's code: a copied mistake passes every check.
    """
    raise NotImplementedError("write reference_rhs in {spec_name}")


# TODO: a typical initial state, used to compare the solver with an
# independent solution of reference_rhs.
Y0 = np.full(DIM, 0.5)


def manufactured(t):
    # Any smooth function will do; each component has its own frequency.
    # Use NumPy functions only: it is differentiated by complex step.
    k = np.arange(1, DIM + 1)
    return np.sin(0.7 * k * t + 0.3) + 0.1 * k


def checks():
    return ode_checks(
        "{module}.{function}",
        solver.{function},
        rhs_ref=reference_rhs,
        mms=ManufacturedODE(manufactured, reference_rhs),
        y0_free=Y0,
        t_end=T_END,
        ns=NS,
        order=ORDER,
        # Exactness check, valid for explicit Runge-Kutta methods (Euler,
        # midpoint, RK4, ...); remove it for other kinds of stepper.
        # See https://github.com/rcgiri-physics/physverify/blob/main/docs/patch.md
        patch=(np.full(DIM, 0.5), np.linspace(1.0, -0.5, DIM)),
    )
'''


def default_ns(order: float) -> tuple[int, ...]:
    """Step counts whose errors stay well above round-off for the claimed order."""
    if order >= 4:
        return (4, 8, 16, 32, 64)
    if order >= 3:
        return (8, 16, 32, 64, 128)
    return (10, 20, 40, 80, 160)


def render(spec_name: str, module: str, function: str, dim: int, order: float, t_end: float) -> str:
    if dim < 1:
        raise ValueError("dim must be at least 1")
    if order <= 0:
        raise ValueError("order must be positive")
    if not module.isidentifier() or not function.isidentifier():
        raise ValueError("module and function must be Python identifiers")
    return TEMPLATE.format(
        spec_name=spec_name,
        module=module,
        function=function,
        dim=dim,
        order=float(order),
        t_end=float(t_end),
        ns=default_ns(order),
    )


def write_spec(path, module: str, function: str, dim: int, order: float, t_end: float, *, force: bool = False) -> Path:
    path = Path(path)
    if path.exists() and not force:
        raise FileExistsError(f"{path} exists; use --force to overwrite it")
    path.write_text(render(path.name, module, function, dim, order, t_end), encoding="utf-8")
    return path
