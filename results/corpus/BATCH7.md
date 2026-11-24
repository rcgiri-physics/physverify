# physverify on other people's code: batch 7

Status: development batch (October 2026), like batches 1 to 6 ([SUMMARY.md](SUMMARY.md)). Repositories are identified by an ID (J001 to J450), not by name, for the same reason: authors are told about a finding before their project is named. Per-repository records (URL, commit, adapter, every check result) are kept and can be shared on request.

The testing and the write-ups were done with help from an AI assistant (Claude Code). Every finding below was reproduced by running the code in the sandbox and checked against the code and, where relevant, the literature before being called a bug.

## How the repositories were chosen

450 public GitHub repositories from 61 physics topic searches: Python, under 2.5 MB, pushed since 2026-06-01, at least one star, not a fork, not archived, a physics keyword in the name or description; homework, course, tutorial and game repositories dropped; none from an earlier batch; ordered by stars, then size. This is not a random sample. From 2026-10-21, repositories that need JAX, CoolProp or long Monte Carlo runs were skipped to keep each test short. The counts below describe these 450 repositories only; they are not a bug rate for physics code in general.

Testing was the same as for the earlier batches: a locked-down container (no network, the repository read-only, nothing from it run on the host), an adapter per repository written from the physics, and every FAIL adjudicated before being counted.

## Funnel

| | Batch 7 |
|---|---|
| In the queue | 450 |
| Out of scope (neural networks, apps and dashboards, data analysis, games, data structures, proofs, non-physics) | 203 |
| Skipped (heavy dependency stacks, GPU only, external data or programs, the quick-only rule) | 54 |
| Not fetchable or not cloned, excluded, not tested | 11 |
| Tested | 182 |
| Tested, no defect found | 141 |
| Tested, at least one confirmed defect | 41 |

Three of the 41 (J147, J148, J149) are small scripts by one author with the same defect. Some defects are minor (a label, a documentation formula, a crash in an optional viewer); they are counted because the code does something other than what it says.

With batches 1 to 6, 250 repositories have now been tested.

## Repositories with a confirmed defect

| ID | Kind of code | Defect |
|---|---|---|
| J005 | Lattice tight-binding builder | Periodic hexagonal and honeycomb lattices crash for every size; one option silently ignores periodicity |
| J012 | Thermal field-theory functions | Spline versions raise for float or list input on NumPy 2 |
| J019 | Riemann solver (exact reference) | The gamma argument is overridden by 1.4; the pressure bisection never returns for strong shocks |
| J042 | ODE methods library | Three methods below their label: Heun stage at the wrong point (order 1.03), 3/8 rule missing a term (1.02), Bogacki-Shampine returns its 2nd-order solution |
| J077 | Optics / Zernike polynomials | The Noll index mapping is wrong for 40 of the first 100 modes |
| J130 | Black-hole ray tracer | Rays with a turning point lose part of the bending angle (endpoint singularity not handled) |
| J133 | Thin-film optics | The p-polarisation reflection has the wrong sign at exactly normal incidence; a module the code imports is missing |
| J147-J149 | Astronomy scripts (one author) | A stray literal `\n` makes each file fail to parse |
| J155 | ODE integrators with a convergence-study GUI | The study compares arrays one step apart and shows slopes 1.73 / 1.76 instead of 1 / 2 |
| J156 | Hydrogen orbitals by shooting | A damping factor applied after shooting distorts every orbital (2p peaks at 2.4 instead of 4 bohr) |
| J157 | FDTD (Yee) | The result viewer crashes, so no result can be shown |
| J159 | Projectile motion | A 1 s time step: printed height 7.1 m where the exact value is 2.6 m |
| J192 | Reactor diffusion and point kinetics | For negative reactivity the asymptotic period is Λ/ρ (-0.02 s) instead of the inhour root (-134 s at -100 pcm) |
| J216 | Black-hole ringdown | The "Regge-Wheeler" potential is the scalar one: the ringdown is the scalar mode, not the gravitational one; the r*(r) inversion fails on the shipped grid |
| J220 | Relativistic particle pusher | The reported acceleration is 5 times the true dv/dt for a parallel force |
| J222 | 1D quantum solver | The tunneling "period" is half the period |
| J224 | Ising Monte Carlo | The Wolff cluster update tests each frontier site once instead of each bond (magnetisation z = -117 against exact enumeration); the energy counts every bond twice |
| J253 | CFD / heat-transfer validation suite | The documented test command fails (wrong source path) |
| J264 | Lorenz attractor | The tests import a name that does not exist |
| J265 | Nuclear many-body (IMSRG) | Crashes on the first save from a fresh clone (output folder missing) |
| J277 | Bouncing ball | The wall clamp keeps the overshoot velocity: an elastic ball gains height every bounce |
| J288 | Modified black-hole shadow | Photon-sphere and shadow formulas disagree with the code's own metric for nonzero coupling |
| J290 | Finite elements | Does not run as committed (missing imports, circular reads, missing notebook) |
| J294 | Kane-Mele / topological bands | The spin-orbit term vanishes at K: gap 0 instead of 1.039, spin Chern number 0 |
| J298 | Wave and Schrödinger packets | The wave equation's start step sends 99% of the pulse the wrong way |
| J318 | Double pendulum | The second equation divides by cos(θ1 - θ2), which is singular when the rods are perpendicular |
| J348 | White dwarfs and Kepler orbits | Two values of G in one Kepler model: a bound orbit gets positive energy |
| J383 | MHD shock relations | Perpendicular and oblique compression and pressure ratios do not satisfy the Rankine-Hugoniot conditions |
| J384 | Smoothed-particle gravity | The self term is excluded by a comparison that fails at rounding level |
| J385 | Particle-mesh gravity | The written accelerations have the wrong sign |
| J386 | Manufactured-solution PDE demo | The manufactured source does not correspond to the stated exact solution |
| J400 | Gravitational lens PSF | One branch of the telescope-averaged PSF is π/2 too small |
| J408 | Double pendulum (rods) | The lower rod's gravity torque uses the wrong angle |
| J409 | Rigid bodies with drag | Drag at zero speed is inf x 0 = NaN, so a body starting at rest turns NaN on the first step |
| J416 | Incompressible fluid solver | The pressure iteration stops after one sweep, leaving 99.7% of the divergence |
| J420 | Rocket nozzle and CAD | The CAD generator crashes on a typo |
| J427 | Lattice Boltzmann | The bad-density guard checks a stale global variable |
| J439 | Matched filtering | Two normalisations missing (matched-filter output 0.128 instead of 1 for white noise; noise PSD) |
| J442 | Double pendulum (Hamiltonian) | dT/db has a factor 2 too much; the "symplectic" leapfrog is first order for this Hamiltonian |

## Mistakes on our side

Adapter mistakes were again found before reporting and are not counted as bugs. The commonest: a reference written for a slightly different problem (for example a normalised versus an unnormalised correlation function, a cold-plasma formula remembered with the wrong Mach number, a shear-wave decay fitted from an equilibrium start without skipping its start-up transient); an absolute tolerance on the finest grid that failed while the observed order was exactly as claimed; fixed-step loops written as `int(t_end / h)` steps, which stop one step early; and a coverage test whose true parameters were drawn from a narrower range than the analysis prior. Each FAIL was checked before it was reported.

## What physverify gained from this

Each item has a test in `tests/`, in the file named after the check (until 2026-11-23 all were in `tests/test_batch7_lessons.py`):

- `physverify smoke PATH`: compiles each script and runs it with a time limit, stdin closed and plotting off, and reports parse errors, crashes, scripts that wait for input and NaN warnings (J147-J149, J156, J157, J159, J265, J290). It runs the code: trusted code or the sandbox only.
- `physverify references` lists the exact references. New ones: Morse levels and turning-point width (J222, J414), Schwarzschild quasinormal frequencies for scalar and gravitational fields (J216), the Kerr ISCO (J116), exact Schwarzschild light deflection (J243), the inhour asymptotic period for either sign of reactivity (J192).
- `studies.damped_sinusoid_fit`: a two-pole Prony fit of a ringdown in a window chosen after the direct pulse (J216).
- `check_order` accepts `tol=` (an adapter that wrote it failed with a TypeError after its whole run), and says when the errors are already near round-off and coarser resolutions are needed.
- `loaders.run_script(..., inputs=[...])` answers `input()` prompts (J156, J159).
- `check_tableau` says when a failed order is only a matter of coefficients typed with too few digits (J042).
