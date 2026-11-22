"""1D Euler equations of gas dynamics: Sod's shock tube and a smooth density wave.

The solver is a first-order finite-volume scheme with the Rusanov (local
Lax-Friedrichs) flux, explicit Euler in time with CFL number 0.5, and copied
(transmissive) boundary cells or periodic boundaries.

Checks:

reference  Sod's problem against the exact Riemann solution (Toro, ch. 4). With
           shocks and a contact discontinuity a first-order scheme converges in
           L1 at about order 1/2 to 1, so the expected order is 0.5 with a wide
           band ([0.3, 1.0]).
reference  a density wave carried at constant velocity and pressure, which is an
           exact smooth solution: order 1 on a periodic domain.
reference  a small-amplitude acoustic wave about rest (linear acoustics): order 1, periodic.
           With u = 0 only the sound speed gives the scheme its dissipation.
reference  a small acoustic pulse sent out through the right end: afterwards the exact
           solution is the uniform rest state, so at most 1% of the pulse may remain.
invariant  discrete conservation, at t = 0.05. Before any wave reaches the ends the fluxes
           through the ends are known exactly (only the pressure term, p_L - p_R,
           moves momentum), so the totals of mass, momentum and energy must match
           to round-off. This is exact for any grid, like the patch checks.
"""

from __future__ import annotations

import math

import numpy as np

from physverify.checks import FAIL, PASS, Check, Result
from physverify.order import check_exact, check_order
from ._common import BugInfo, families

NAME = "sod"
GAMMA = 1.4
CFL = 0.5
T_END = 0.2
LEFT = (1.0, 0.0, 1.0)  # density, velocity, pressure
RIGHT = (0.125, 0.0, 0.1)
X0 = 0.5
SOD_CELLS = (100, 200, 400, 800, 1600)
WAVE_CELLS = (50, 100, 200, 400, 800)
WAVE_T_END = 0.25
CONSERVATION_CELLS = (50, 100, 200)
# A first-order explicit scheme moves information one cell per step, about 0.84 of the domain
# by t = 0.2 at CFL 0.5, so numerical diffusion would reach the ends. By t = 0.05 it has
# moved about 0.21 from the diaphragm, and the end cells are still exactly the initial states.
CONSERVATION_T_END = 0.05
# Small-amplitude acoustics about rest (rho0 = p0 = 1, c0 = sqrt(gamma)). The linearized Euler equations give
# right-going simple waves rho' = eps f(x - c0 t), u' = c0 rho', p' = c0^2 rho' (Toro, sect. 2.3 / LeVeque,
# Finite Volume Methods, ch. 14); the nonlinear correction is O(eps^2), far below the scheme's error here.
ACOUSTIC_EPS = 1e-6
ACOUSTIC_C0 = math.sqrt(GAMMA)
ACOUSTIC_CELLS = (50, 100, 200, 400, 800)
ACOUSTIC_T_END = 0.25
PULSE_CELLS = (50, 100, 200)
PULSE_X0, PULSE_WIDTH = 0.7, 0.05
PULSE_T_END = 0.6 / ACOUSTIC_C0  # the pulse centre is then 0.3 past the right end, every part of it outside
# A copied (transmissive) end lets a smooth outgoing pulse leave almost entirely: about 2e-4 of it is left on
# 50 cells and less on finer grids. A reflecting end keeps all of it, so 1% separates the two with a wide margin.
PULSE_LEFT_TOL = 0.01

BUGS = {
    "gamma_wrong": BugInfo(
        "the flux computes pressure with gamma = 5/3 while the initial data use 1.4",
        families("reference"),
        "wrong wave speeds and plateaus in Sod's problem; the smooth wave has uniform pressure, so it may not see it",
    ),
    "nonconservative_momentum": BugInfo(
        "velocity is updated in primitive form (u_t + u u_x + p_x / rho = 0) instead of conserving momentum",
        families("invariant"),
        "momentum not conserved. Predicted before running: the Sod reference check too, through a wrong "
        "shock speed. Observed: its order falls from 0.63 to 0.43, still inside the wide band a "
        "discontinuous solution needs, so only the conservation check flags it",
    ),
    "wave_speed_without_sound": BugInfo(
        "the Rusanov dissipation uses |u| instead of |u| + c",
        families("reference"),
        "predicted before running: oscillations at the discontinuities, flagged by the Sod reference "
        "check. Observed: on Sod's problem the scheme stayed stable and was slightly more accurate (less "
        "dissipation). An acoustic wave in a fluid at rest (u = 0) exposes it: the dissipation vanishes, "
        "the scheme becomes central differences with forward Euler, which is unstable, and the error grows",
    ),
    "last_step_not_clipped": BugInfo(
        "the last time step is not shortened to end exactly at t_end",
        families("invariant"),
        "an O(dt) time error, the same order as the scheme's own, so the order studies pass; "
        "the conservation check uses the intended time and sees the extra momentum",
    ),
    "reflective_boundary": BugInfo(
        "the boundary cells reflect (velocity negated) instead of letting waves out",
        families("reference"),
        "nothing in Sod's problem, where no wave reaches a boundary before t_end. An acoustic pulse sent "
        "out through the open end exposes it: the reflected pulse stays in the domain",
    ),
}


# --- exact Riemann solver (Toro, Riemann Solvers and Numerical Methods for Fluid Dynamics, ch. 4) ---


def _sound(rho, p, gamma=GAMMA):
    return math.sqrt(gamma * p / rho)


def _f_and_df(p, rho_k, p_k, gamma):
    c_k = _sound(rho_k, p_k, gamma)
    if p > p_k:  # shock
        a = 2.0 / ((gamma + 1.0) * rho_k)
        b = (gamma - 1.0) / (gamma + 1.0) * p_k
        q = math.sqrt(a / (p + b))
        return (p - p_k) * q, q * (1.0 - 0.5 * (p - p_k) / (p + b))
    ratio = p / p_k  # rarefaction
    f = 2.0 * c_k / (gamma - 1.0) * (ratio ** ((gamma - 1.0) / (2.0 * gamma)) - 1.0)
    df = ratio ** (-(gamma + 1.0) / (2.0 * gamma)) / (rho_k * c_k)
    return f, df


def star_state(left=LEFT, right=RIGHT, gamma=GAMMA):
    """Pressure and velocity between the two outer waves, by Newton iteration."""
    rl, ul, pl = left
    rr, ur, pr = right
    p = max(1e-10, 0.5 * (pl + pr))
    for _ in range(100):
        fl, dfl = _f_and_df(p, rl, pl, gamma)
        fr, dfr = _f_and_df(p, rr, pr, gamma)
        step = (fl + fr + ur - ul) / (dfl + dfr)
        p_new = max(1e-10, p - step)
        if abs(p_new - p) <= 1e-14 * (p_new + p):
            p = p_new
            break
        p = p_new
    fl, _ = _f_and_df(p, rl, pl, gamma)
    fr, _ = _f_and_df(p, rr, pr, gamma)
    return p, 0.5 * (ul + ur) + 0.5 * (fr - fl)


def sample(s, left=LEFT, right=RIGHT, gamma=GAMMA, star=None):
    """(density, velocity, pressure) of the exact solution at x/t = s."""
    rl, ul, pl = left
    rr, ur, pr = right
    cl, cr = _sound(rl, pl, gamma), _sound(rr, pr, gamma)
    ps, us = star or star_state(left, right, gamma)
    g6 = (gamma - 1.0) / (gamma + 1.0)
    if s <= us:
        if ps > pl:
            shock = ul - cl * math.sqrt((gamma + 1.0) / (2.0 * gamma) * ps / pl + (gamma - 1.0) / (2.0 * gamma))
            if s <= shock:
                return rl, ul, pl
            return rl * (ps / pl + g6) / (g6 * ps / pl + 1.0), us, ps
        if s <= ul - cl:
            return rl, ul, pl
        c_star = cl * (ps / pl) ** ((gamma - 1.0) / (2.0 * gamma))
        if s > us - c_star:
            return rl * (ps / pl) ** (1.0 / gamma), us, ps
        u = 2.0 / (gamma + 1.0) * (cl + 0.5 * (gamma - 1.0) * ul + s)
        c = 2.0 / (gamma + 1.0) * (cl + 0.5 * (gamma - 1.0) * (ul - s))
        return rl * (c / cl) ** (2.0 / (gamma - 1.0)), u, pl * (c / cl) ** (2.0 * gamma / (gamma - 1.0))
    if ps > pr:
        shock = ur + cr * math.sqrt((gamma + 1.0) / (2.0 * gamma) * ps / pr + (gamma - 1.0) / (2.0 * gamma))
        if s >= shock:
            return rr, ur, pr
        return rr * (ps / pr + g6) / (g6 * ps / pr + 1.0), us, ps
    if s >= ur + cr:
        return rr, ur, pr
    c_star = cr * (ps / pr) ** ((gamma - 1.0) / (2.0 * gamma))
    if s <= us + c_star:
        return rr * (ps / pr) ** (1.0 / gamma), us, ps
    u = 2.0 / (gamma + 1.0) * (-cr + 0.5 * (gamma - 1.0) * ur + s)
    c = 2.0 / (gamma + 1.0) * (cr - 0.5 * (gamma - 1.0) * (ur - s))
    return rr * (c / cr) ** (2.0 / (gamma - 1.0)), u, pr * (c / cr) ** (2.0 * gamma / (gamma - 1.0))


def exact_sod(x, t, left=LEFT, right=RIGHT, x0=X0, gamma=GAMMA):
    star = star_state(left, right, gamma)
    return np.array([sample((xi - x0) / t, left, right, gamma, star) for xi in x]).T


# --- the solver under test ---


def conserved(rho, u, p, gamma=GAMMA):
    return np.array([rho, rho * u, p / (gamma - 1.0) + 0.5 * rho * u * u])


def solve(n_cells, bugs, init, t_end, periodic=False):
    """Advance cell averages on [0, 1] to t_end. Returns cell centres, final U, and the time reached."""
    gamma_flux = 5.0 / 3.0 if "gamma_wrong" in bugs else GAMMA
    dx = 1.0 / n_cells
    x = (np.arange(n_cells) + 0.5) * dx
    U = conserved(*init(x))
    t = 0.0
    with np.errstate(all="ignore"):
        while t < t_end:
            if periodic:
                G = np.concatenate([U[:, -1:], U, U[:, :1]], axis=1)
            else:
                G = np.concatenate([U[:, :1], U, U[:, -1:]], axis=1)
                if "reflective_boundary" in bugs:
                    G[1, 0], G[1, -1] = -G[1, 0], -G[1, -1]
            rho, mom, E = G
            u = mom / rho
            p = (gamma_flux - 1.0) * (E - 0.5 * rho * u * u)
            c = np.sqrt(gamma_flux * np.abs(p) / rho)
            speed = np.max(np.abs(u) + c)
            if not np.isfinite(speed) or speed <= 0.0:
                return x, np.full_like(U, np.nan), t
            dt = CFL * dx / speed
            if t + dt > t_end and "last_step_not_clipped" not in bugs:
                dt = t_end - t
            F = np.array([mom, mom * u + p, (E + p) * u])
            wave = np.abs(u) if "wave_speed_without_sound" in bugs else np.abs(u) + c
            a = np.maximum(wave[:-1], wave[1:])
            flux = 0.5 * (F[:, :-1] + F[:, 1:]) - 0.5 * a * (G[:, 1:] - G[:, :-1])
            U_new = U - dt / dx * (flux[:, 1:] - flux[:, :-1])
            if "nonconservative_momentum" in bugs:
                # u_t + u u_x + p_x / rho = 0, with the same Rusanov-type dissipation on u
                ui = u[1:-1]
                du = 0.5 * (u[2:] - u[:-2])
                dp = 0.5 * (p[2:] - p[:-2])
                u_new = ui - dt / dx * (ui * du + dp / rho[1:-1]) + 0.5 * dt / dx * a.max() * (u[2:] - 2 * ui + u[:-2])
                U_new[1] = U_new[0] * u_new
            U = U_new
            t += dt
    return x, U, t


def primitive(U, gamma=GAMMA):
    rho, mom, E = U
    u = mom / rho
    return rho, u, (gamma - 1.0) * (E - 0.5 * rho * u * u)


def sod_init(x):
    left = x < X0
    rho = np.where(left, LEFT[0], RIGHT[0])
    u = np.where(left, LEFT[1], RIGHT[1])
    p = np.where(left, LEFT[2], RIGHT[2])
    return rho, u, p


def wave_init(x, t=0.0):
    return 1.0 + 0.2 * np.sin(2.0 * math.pi * (x - t)), np.ones_like(x), np.ones_like(x)


def _acoustic(f):
    """Right-going linear acoustic wave with density perturbation f (an array), about rest."""
    rho = ACOUSTIC_EPS * f
    return 1.0 + rho, ACOUSTIC_C0 * rho, 1.0 + ACOUSTIC_C0 ** 2 * rho


def acoustic_wave_init(x, t=0.0):
    return _acoustic(np.sin(2.0 * math.pi * (x - ACOUSTIC_C0 * t)))


def acoustic_pulse_init(x):
    return _acoustic(np.exp(-((x - PULSE_X0) / PULSE_WIDTH) ** 2))


def _l1(a, b):
    with np.errstate(all="ignore"):
        return float(np.mean(np.abs(a - b)))


def checks(bugs=frozenset()) -> list[Check]:
    def run_sod():
        hs, errs = [], []
        for n in SOD_CELLS:
            x, U, _ = solve(n, bugs, sod_init, T_END)
            hs.append(1.0 / n)
            errs.append(_l1(U[0], exact_sod(x, T_END)[0]))
        return check_order(hs, errs, 0.5, tol_low=0.2, tol_high=0.5)

    def run_wave():
        hs, errs = [], []
        for n in WAVE_CELLS:
            x, U, _ = solve(n, bugs, wave_init, WAVE_T_END, periodic=True)
            hs.append(1.0 / n)
            errs.append(_l1(U[0], wave_init(x, WAVE_T_END)[0]))
        return check_order(hs, errs, 1.0)

    def run_conservation():
        # Fluxes through the ends stay those of the initial states until a wave arrives:
        # mass and energy fluxes are zero (u = 0), the momentum flux is the pressure.
        expected_change = np.array([0.0, -(RIGHT[2] - LEFT[2]) * CONSERVATION_T_END, 0.0])
        hs, errs = [], []
        for n in CONSERVATION_CELLS:
            x, U, _ = solve(n, bugs, sod_init, CONSERVATION_T_END)
            total0 = conserved(*sod_init(x)).sum(axis=1) / n
            with np.errstate(all="ignore"):
                errs.append(float(np.max(np.abs(U.sum(axis=1) / n - total0 - expected_change))))
            hs.append(1.0 / n)
        return check_exact(hs, errs, floor=1e-11)

    def run_acoustic_wave():
        # the fluid is at rest, so all dissipation must come from the sound speed
        hs, errs = [], []
        for n in ACOUSTIC_CELLS:
            x, U, _ = solve(n, bugs, acoustic_wave_init, ACOUSTIC_T_END, periodic=True)
            hs.append(1.0 / n)
            errs.append(_l1(U[0], acoustic_wave_init(x, ACOUSTIC_T_END)[0]) / ACOUSTIC_EPS)
        return check_order(hs, errs, 1.0)

    def run_pulse_exit():
        worst = 0.0
        for n in PULSE_CELLS:
            x, U, _ = solve(n, bugs, acoustic_pulse_init, PULSE_T_END)
            initial = _l1(acoustic_pulse_init(x)[0], 1.0)
            left = _l1(U[0], 1.0) / initial
            worst = max(worst, left) if np.isfinite(left) else float("inf")
        if worst <= PULSE_LEFT_TOL:
            return Result(PASS, f"after the pulse left through the open end, at most {worst:.2g} of it remained"
                                f" (limit {PULSE_LEFT_TOL:g}) on {PULSE_CELLS[0]} to {PULSE_CELLS[-1]} cells")
        return Result(FAIL, f"{worst:.3g} of an outgoing acoustic pulse is still in the domain after it should have"
                            f" left through the open end (limit {PULSE_LEFT_TOL:g}): the boundary reflects or the"
                            " solution is unstable")

    return [
        Check("reference", "Sod shock tube, density L1", run_sod),
        Check("reference", "smooth density wave, periodic", run_wave),
        Check("reference", "acoustic wave about rest, periodic", run_acoustic_wave),
        Check("reference", "acoustic pulse leaving through an open end", run_pulse_exit),
        Check("invariant", "discrete conservation of mass, momentum, energy", run_conservation),
    ]


SMOKE_CELLS = 400
SMOKE_RTOL = 0.05  # an L1 density error of a few percent is typical for a first-order scheme here


def smoke_checks(bugs=frozenset()) -> list[Check]:
    """A plain test: Sod's density on 400 cells within 5% (L1, relative to the mean density)."""

    def run():
        x, U, _ = solve(SMOKE_CELLS, bugs, sod_init, T_END)
        exact = exact_sod(x, T_END)[0]
        rel = _l1(U[0], exact) / float(np.mean(exact))
        return _within(rel, SMOKE_RTOL)

    return [Check("smoke", "Sod density on 400 cells", run)]


def _within(rel, tol):
    if np.isfinite(rel) and rel <= tol:
        return Result(PASS, f"relative L1 error {rel:.3g} within {tol:g}")
    return Result(FAIL, f"relative L1 error {rel:.3g} exceeds {tol:g}")
