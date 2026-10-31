"""Exactness properties every numerical flux of a conservation law must have (Toro, Riemann Solvers and
Numerical Methods for Fluid Dynamics, 3rd ed., ch. 10-11; LeVeque, Finite Volume Methods, sec. 12.1):

- consistency  F(W, W) = f(W), the physical flux, for any state W
- upwinding    when every wave speed is positive on both sides, F(WL, WR) = f(WL) (all negative: f(WR));
               Roe, HLL, HLLC and Rusanov fluxes with exact wave-speed bounds satisfy it
- mirror       reflecting the normal velocity and swapping the sides gives F(R WR, R WL) = -R F(WL, WR),
               with R the reflection acting on the flux components

Each needs only the flux function and the physical flux written from the equations, not a solver run.
In the 2026-10 corpus sessions these checks found both bugs in one Euler solver: a Roe flux that broke
upwinding when density and tangential velocity both jumped, and an HLLE flux built for the wrong fluid.
"""

from __future__ import annotations

from typing import Callable, Iterable

import numpy as np

from .checks import FAIL, PASS, Result
from .identities import _verdict


def check_flux(flux: Callable, physical: Callable, states: Iterable, *, upwind_pairs: Iterable = (),
               downwind_pairs: Iterable = (), mirror: tuple | None = None, rtol: float = 1e-10,
               atol: float = 1e-12) -> Result:
    """Consistency, upwinding and (optionally) mirror symmetry of a numerical flux `flux(WL, WR)`.

    `physical(W)` is the exact flux written from the equations; `states` are the states W for the
    consistency check. `upwind_pairs` are (WL, WR) with all wave speeds positive on both sides (F must equal
    f(WL)) and `downwind_pairs` all negative (F must equal f(WR)); the caller builds them from the sound
    speed. `mirror = (reflect, signs)`: `reflect(W)` flips the normal velocity of a state and `signs` holds
    +1 or -1 per flux component (for the 1D Euler equations (-1, +1, -1): mass and energy fluxes change sign,
    the momentum flux does not); the check is F(reflect(WR), reflect(WL)) = signs * F(WL, WR), over all pairs.
    """
    states = list(states)
    if not states:
        raise ValueError("no states given")
    up, down = list(upwind_pairs), list(downwind_pairs)
    results = [("consistency F(W, W) = f(W)",
                _verdict("consistency", [(f"state {i}", flux(w, w), physical(w)) for i, w in enumerate(states)], rtol, atol))]
    if up:
        results.append(("upwinding F = f(WL) for flow to the right",
                        _verdict("upwinding", [(f"pair {i}", flux(a, b), physical(a)) for i, (a, b) in enumerate(up)], rtol, atol)))
    if down:
        results.append(("upwinding F = f(WR) for flow to the left",
                        _verdict("upwinding", [(f"pair {i}", flux(a, b), physical(b)) for i, (a, b) in enumerate(down)], rtol, atol)))
    if mirror is not None:
        reflect, signs = mirror
        signs = np.asarray(signs, dtype=float)
        pairs = up + down + list(zip(states, states[1:]))
        cases = [(f"pair {i}", flux(reflect(b), reflect(a)), signs * np.asarray(flux(a, b))) for i, (a, b) in enumerate(pairs)]
        results.append(("mirror symmetry", _verdict("mirror symmetry", cases, rtol, atol)))
    failed = [f"{name}: {r.message}" for name, r in results if not r.ok]
    if failed:
        return Result(FAIL, "; ".join(failed))
    return Result(PASS, "the numerical flux passes " + ", ".join(name for name, _r in results))
