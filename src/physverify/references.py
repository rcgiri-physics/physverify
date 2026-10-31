"""Exact reference solutions that testing public codes needed again and again.

Each one was written by hand in several adapters before it moved here (repository IDs as in
results/corpus/SUMMARY.md). All are numpy-only and vectorised where that is natural.
"""

from __future__ import annotations

import math

import numpy as np

# --- statistical mechanics ---------------------------------------------------------------------------


def ising2d_exact(L: int, T: float, J: float = 1.0, h: float = 0.0) -> dict:
    """Exact thermal averages of the periodic L x L Ising model by enumerating all 2^(L*L) states.

    H = -J sum_<ij> s_i s_j - h sum_i s_i, k_B = 1. Returns per-site <e>, <|m|>, <m^2>, <m^4>, the
    specific heat per site and Z. Practical up to L = 4 (65536 states); used for D04, H06, H55.
    """
    n = L * L
    if n > 20:
        raise ValueError("enumeration is limited to L*L <= 20 sites (L <= 4)")
    states = ((np.arange(2**n)[:, None] >> np.arange(n)) & 1) * 2 - 1
    s = states.reshape(-1, L, L)
    bonds = np.sum(s * np.roll(s, 1, axis=1), axis=(1, 2)) + np.sum(s * np.roll(s, 1, axis=2), axis=(1, 2))
    M = s.sum(axis=(1, 2))
    E = -J * bonds - h * M
    w = np.exp(-(E - E.min()) / T)
    Z = w.sum()
    avg = lambda q: float(np.sum(w * q) / Z)  # noqa: E731
    e, e2 = avg(E) / n, avg(E**2) / n**2
    return {"e": e, "m_abs": avg(np.abs(M)) / n, "m2": avg(M**2) / n**2, "m4": avg(M**4) / n**4,
            "c": n * (e2 - e * e) / T**2, "Z": float(Z * np.exp(-E.min() / T))}


def langevin(x):
    """L(x) = coth x - 1/x, with the series near 0."""
    x = np.asarray(x, dtype=float)
    small = np.abs(x) < 1e-3
    safe = np.where(small, 1.0, x)
    return np.where(small, x / 3 - x**3 / 45, 1 / np.tanh(safe) - 1 / safe)


def heisenberg_open_chain(N: int, J: float, T: float) -> dict:
    """Classical unit-vector Heisenberg chain with open ends, H = -J sum S_i.S_{i+1}: exact per-site
    energy and specific heat (each bond is independent). Used for H64."""
    b = J / T
    e = -(N - 1) * J * float(langevin(b)) / N
    c = (N - 1) / N * (1 - b * b / math.sinh(b) ** 2)
    return {"e": e, "c": c}


# --- diffusion and transport -------------------------------------------------------------------------


def heat_sine_mode(x, t, L: float = 1.0, kappa: float = 1.0, mode: int = 1):
    """u_t = kappa u_xx on [0, L], u = 0 at both ends, u(x, 0) = sin(mode pi x / L)."""
    k = mode * np.pi / L
    return np.exp(-kappa * k * k * t) * np.sin(k * np.asarray(x, dtype=float))


def advection_diffusion_gaussian(x, t, x0: float, sigma0: float, v: float = 0.0, D: float = 0.0):
    """Gaussian of peak 1 and width sigma0 at x0, carried at speed v and spread by D on the whole line:
    sigma^2 = sigma0^2 + 2 D t, peak sigma0/sigma. Used for H25."""
    s = math.sqrt(sigma0**2 + 2 * D * t)
    return sigma0 / s * np.exp(-((np.asarray(x, dtype=float) - x0 - v * t) ** 2) / (2 * s * s))


def semi_infinite_step(x, t, alpha: float, T0: float, Ts: float):
    """Semi-infinite solid at T0, surface held at Ts from t = 0: T = Ts + (T0 - Ts) erf(x / 2 sqrt(alpha t))."""
    x = np.asarray(x, dtype=float)
    return Ts + (T0 - Ts) * np.vectorize(math.erf)(x / (2 * math.sqrt(alpha * t)))


# --- mechanics ---------------------------------------------------------------------------------------


def double_pendulum_acc(th1, w1, th2, w2, m1, m2, l1, l2, g=9.81):
    """Angular accelerations of a double pendulum (point masses, massless rods, angles from the downward
    vertical), from the Lagrangian mass matrix. Used for D01, E01, H03, H27."""
    d = th1 - th2
    M = np.array([[(m1 + m2) * l1**2, m2 * l1 * l2 * np.cos(d)], [m2 * l1 * l2 * np.cos(d), m2 * l2**2]])
    r = np.array([-m2 * l1 * l2 * w2**2 * np.sin(d) - (m1 + m2) * g * l1 * np.sin(th1),
                  m2 * l1 * l2 * w1**2 * np.sin(d) - m2 * g * l2 * np.sin(th2)])
    return np.linalg.solve(M, r)


def double_pendulum_energy(th1, w1, th2, w2, m1, m2, l1, l2, g=9.81):
    v1sq = (l1 * w1) ** 2
    v2sq = v1sq + (l2 * w2) ** 2 + 2 * l1 * l2 * w1 * w2 * np.cos(th1 - th2)
    return 0.5 * m1 * v1sq + 0.5 * m2 * v2sq - (m1 + m2) * g * l1 * np.cos(th1) - m2 * g * l2 * np.cos(th2)


def cantilever_tip(P: float, L: float, E: float, I: float) -> tuple[float, float]:
    """Euler-Bernoulli cantilever with an end load: tip deflection P L^3/(3EI) and rotation P L^2/(2EI)."""
    return P * L**3 / (3 * E * I), P * L**2 / (2 * E * I)


# --- quantum mechanics -------------------------------------------------------------------------------


def infinite_well_energy(n, W: float, hbar: float = 1.0, m: float = 1.0):
    """E_n = n^2 pi^2 hbar^2 / (2 m W^2), n = 1, 2, ... Used for H19."""
    n = np.asarray(n, dtype=float)
    return n * n * np.pi**2 * hbar**2 / (2 * m * W * W)


def barrier_transmission(E, V: float, a: float, hbar: float = 1.0, m: float = 1.0):
    """Transmission probability through a square barrier of height V and width a (E != V). Used for H40."""
    E = np.asarray(E, dtype=float)
    k = np.sqrt(2 * m * np.abs(V - E)) / hbar * a
    s2 = np.where(E < V, np.sinh(k) ** 2, np.sin(k) ** 2)
    return 1 / (1 + V * V * s2 / (4 * E * np.abs(V - E)))


def tfim_open_ground_energy(N: int, J: float, h: float) -> float:
    """Ground energy of the open transverse-field Ising chain H = J sum Z_i Z_{i+1} + h sum X_i, from the
    free-fermion (Jordan-Wigner, Bogoliubov-de Gennes) solution; the sign of J does not matter. Used for H22."""
    A = np.zeros((N, N))
    B = np.zeros((N, N))
    np.fill_diagonal(A, 2 * h)
    for i in range(N - 1):
        A[i, i + 1] = A[i + 1, i] = J
        B[i, i + 1], B[i + 1, i] = J, -J
    eps = np.linalg.eigvalsh(np.block([[A, B], [-B, -A]]))
    return float(-0.5 * np.sum(eps[eps > 0]))


# --- molecules ---------------------------------------------------------------------------------------


def morse_levels(v, omega_e: float, omega_e_x_e: float):
    """Morse vibrational levels above the potential minimum, G(v) = w_e (v + 1/2) - w_e x_e (v + 1/2)^2, exact for the
    potential D (1 - exp(-a (r - r_e)))^2 with D = w_e^2 / (4 w_e x_e). Used for J222, J414."""
    x = np.asarray(v, dtype=float) + 0.5
    return omega_e * x - omega_e_x_e * x * x


def morse_turning_width(E, D: float, a: float):
    """r_max - r_min of the Morse potential D (1 - exp(-a (r - r_e)))^2 at energy E (0 < E < D):
    (1/a) ln((1 + q)/(1 - q)) with q = sqrt(E/D). An RKR inversion reproduces this exactly from G(v) alone. Used for J414."""
    q = np.sqrt(np.asarray(E, dtype=float) / D)
    return np.log((1 + q) / (1 - q)) / a


# --- gravitation -------------------------------------------------------------------------------------


_QNM_FUNDAMENTAL = {  # (spin of the field, l): M omega for the n = 0 mode of a Schwarzschild black hole
    (0, 0): 0.11046 - 0.10490j, (0, 1): 0.29294 - 0.09766j, (0, 2): 0.48364 - 0.09677j,
    (2, 2): 0.37367 - 0.08896j, (2, 3): 0.59944 - 0.09270j,
}


def schwarzschild_qnm(l: int, s: int = 2) -> complex:
    """Fundamental (n = 0) quasinormal frequency M omega of a Schwarzschild black hole for a field of spin s
    (0 scalar, 2 gravitational) and multipole l; 5-digit literature values (Leaver 1985; Berti, Cardoso and
    Starinets 2009). A ringdown that matches s = 0 when the code claims gravitational waves points to the
    potential term (1 - s^2) 2M/r^3. Used for J216."""
    try:
        return _QNM_FUNDAMENTAL[(s, l)]
    except KeyError:
        raise ValueError(f"no tabulated mode for s = {s}, l = {l}; available: {sorted(_QNM_FUNDAMENTAL)}") from None


def kerr_isco(a: float, prograde: bool = True) -> float:
    """Radius of the innermost stable circular orbit of a Kerr black hole (Bardeen, Press and Teukolsky 1972), in
    units of M; a is the dimensionless spin, 0 <= a <= 1. Gives 6 at a = 0, and 1 or 9 at a = 1. Used for J116."""
    z1 = 1 + (1 - a * a) ** (1 / 3) * ((1 + a) ** (1 / 3) + (1 - a) ** (1 / 3))
    z2 = math.sqrt(3 * a * a + z1 * z1)
    root = math.sqrt((3 - z1) * (3 + z1 + 2 * z2))
    return 3 + z2 - root if prograde else 3 + z2 + root


def _bisect(f, lo: float, hi: float, iters: int = 200) -> float:
    flo = f(lo)
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if fm == 0 or hi - lo <= 1e-16 * max(1.0, abs(mid)):
            return mid
        if (fm < 0) == (flo < 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return 0.5 * (lo + hi)


def schwarzschild_deflection(b: float, nodes: int = 200) -> float:
    """Exact deflection angle (radians) of light with impact parameter b > 3 sqrt(3) M past a Schwarzschild black hole,
    G = c = M = 1: 2 int_0^{u0} du / sqrt(1/b^2 - u^2 + 2 u^3) - pi, u0 the turning point. The substitution
    u = u0 (1 - s^2) removes the endpoint singularity; Gauss-Legendre on s. Tends to 4/b. Used for J243."""
    if b <= 3 * math.sqrt(3):
        raise ValueError("b must exceed 3 sqrt(3): the photon is captured")
    g = lambda u: 1 / b**2 - u * u + 2 * u**3  # noqa: E731
    u0 = _bisect(g, 1e-15, 1 / 3)
    x, w = np.polynomial.legendre.leggauss(nodes)
    s_ = 0.5 * (x + 1)
    vals = 2 * u0 * s_ / np.sqrt(np.maximum(g(u0 * (1 - s_ * s_)), 1e-300))
    return float(2 * 0.5 * np.dot(w, vals) - math.pi)


# --- reactor physics ---------------------------------------------------------------------------------


def inhour_stable_period(rho: float, Lambda: float, beta_i, lambda_i) -> float:
    """Asymptotic (stable) reactor period in seconds from the inhour equation
    rho = w Lambda + sum_i w beta_i / (w + lambda_i): the largest root, positive for rho > 0 and in (-min lambda_i, 0)
    for rho < 0 (it tends to -1/min lambda_i, about -80 s for U-235, after a large negative step). Used for J192."""
    b = np.asarray(beta_i, dtype=float)
    lam = np.asarray(lambda_i, dtype=float)
    f = lambda w: rho - (w * Lambda + np.sum(w * b / (w + lam)))  # noqa: E731
    if rho == 0:
        return math.inf
    if rho > 0:
        hi = 1.0
        while f(hi) > 0:
            hi *= 10
        return 1 / _bisect(f, 1e-14, hi)
    return 1 / _bisect(f, -lam.min() * (1 - 1e-12), -1e-14)


# --- optics ------------------------------------------------------------------------------------------


def zernike_osa(n: int, m: int, rho, theta):
    """Zernike polynomial Z_n^m in the OSA/ANSI convention (ANSI Z80.28; Thibos et al. 2002): N R_n^|m|(rho)
    times cos(m theta) for m >= 0 and sin(|m| theta) for m < 0, with N = sqrt(2 (n + 1) / (1 + delta_m0)), so
    that the mean of Z^2 over the unit disk is 1. Noll's ordering uses the same normalisation. Two corpus repos
    needed it (L173 right, L208 normalised as sqrt(n + 1) for every m)."""
    am = abs(m)
    if n < 0 or am > n or (n - am) % 2:
        raise ValueError("Zernike indices need n >= |m| and n - |m| even")
    rho = np.asarray(rho, dtype=float)
    radial = sum((-1) ** k * math.factorial(n - k)
                 / (math.factorial(k) * math.factorial((n + am) // 2 - k) * math.factorial((n - am) // 2 - k))
                 * rho ** (n - 2 * k) for k in range((n - am) // 2 + 1))
    norm = math.sqrt(2 * (n + 1) / (1 + (m == 0)))
    return norm * radial * (np.cos(m * theta) if m >= 0 else np.sin(am * theta))


REFERENCES = {
    "ising2d_exact": "2D Ising energy, magnetisation, heat capacity by enumeration (L <= 4)",
    "heisenberg_open_chain": "classical Heisenberg open chain, energy per spin",
    "heat_sine_mode": "heat equation sine mode exp(-kappa (n pi / L)^2 t) sin(n pi x / L)",
    "advection_diffusion_gaussian": "moving, spreading Gaussian",
    "semi_infinite_step": "semi-infinite solid with a temperature step (erfc)",
    "double_pendulum_acc": "double pendulum angular accelerations (th1, w1, th2, w2 order)",
    "double_pendulum_energy": "double pendulum total energy",
    "cantilever_tip": "cantilever tip deflection and slope under an end load",
    "infinite_well_energy": "infinite square well levels",
    "barrier_transmission": "square-barrier transmission",
    "tfim_open_ground_energy": "open transverse-field Ising chain ground energy (free fermions)",
    "morse_levels": "Morse vibrational levels G(v)",
    "morse_turning_width": "Morse classical turning-point width at energy E",
    "schwarzschild_qnm": "Schwarzschild fundamental quasinormal frequencies (s = 0, 2)",
    "kerr_isco": "Kerr innermost stable circular orbit",
    "schwarzschild_deflection": "exact light deflection by a Schwarzschild black hole",
    "inhour_stable_period": "asymptotic reactor period from the inhour equation (either sign of rho)",
    "zernike_osa": "Zernike polynomial, OSA/ANSI normalisation (mean square 1 on the unit disk)",
}
