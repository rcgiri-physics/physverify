# Sandbox for testing other people's code

Every external repository is treated as untrusted. `sandbox.py` runs it in a fresh container with these limits:

| Limit | Setting |
|---|---|
| Network | none (`--network=none`) during `run` |
| File system | root file system read-only; clone mounted read-only at `/repo-src` and copied to `/tmp/repo` for each run (`$PHYSVERIFY_REPO`; files the code writes there are reported as a portability note; `--read-only-repo` runs from a read-only `/repo` instead); only `/out` and a 512 MB `/tmp` are writable. `--py314-shim` adds `from __future__ import annotations` to each file of the copy, for code written for Python 3.14 |
| User | uid 10001, all capabilities dropped, `no-new-privileges`, no sudo |
| Resources | 2 CPUs, 2 GB memory (no swap), 256 processes, 1024 open files, 1 GB max file size |
| Time | 900 s per run (`PHYSVERIFY_TIME_LIMIT`), then the container is killed |
| Image | Python 3.12 slim pinned by digest, NumPy, SciPy, SymPy, Matplotlib (Agg), pytest, physverify; libX11 and libGL for wheels that link them |

The repository is cloned on the host with hooks, symlinks and LFS turned off and checked out at a fixed commit. Nothing from the repository runs on the host. Extra requirements, when needed, are installed by `deps` as wheels only (no `setup.py`) into a separate folder that is mounted read-only during `run`; `deps` is the only step with network access.

    python -I sandbox/sandbox.py build
    python -I sandbox/sandbox.py fetch D01 https://github.com/owner/repo <commit>
    python -I sandbox/sandbox.py deps  D01
    python -I sandbox/sandbox.py run   D01 path/to/adapter_script.py

The adapter script's folder is mounted read-only at `/work`, so shared helpers next to it can be imported.

`probe.py` checks the limits from inside; every line should print `OK`. In Git Bash, set `MSYS_NO_PATHCONV=1` so container paths are not rewritten.

## What the adapters taught us

Mistakes made while writing the first adapters, worth avoiding in the next ones:

- Use the code's own constants in the reference. One code used the Gaussian G = 39.4769 au³/(M☉ yr²), not 4π², so a textbook circular orbit was the wrong reference. `physverify.constants.scan` lists such values first.
- Compare at the requested end time, and check the time grid separately (`time_grid_check`). Taking the record nearest `t_end` hid an extra step.
- Before calling a low order a bug, refine. Large-amplitude problems can be pre-asymptotic at the usual step counts, and `check_order` now says when that looks likely.
- A Crank–Nicolson reference with a start that does not match the boundary condition rings; use a few backward Euler steps first (Rannacher start).
- When a sampler fails a statistical check, rerun it with an independently computed observable to tell a sampling bug from a measurement bug.
- Rebuild the image after changing physverify: the image holds a copy of `src/`, not a live mount.
- Taichi fields can be padded to a block size; read only the first N rows.
- With an unshifted pair potential, a pair crossing the cutoff changes the energy by V(r_c) whatever dt is. Choose starting positions with no pair near the cutoff, or the energy check measures the model, not the integrator.
- For Butcher tables, check the order conditions (`physverify.butcher`) before running order studies; they settle the question exactly.
- Corpus data location: set `PHYSVERIFY_CORPUS` (on the author's machine `G:\physverify-corpus`, to keep the C drive free).
- Fix the reference's convention before calling a mismatch a bug: a Thomas solver written for A x_{i-1} - C x_i + B x_{i+1} = F, a percolation test whose documented spanning means all four edges, a "protected fraction" defined by the symmetry algebra rather than its commutant.
- Do not put a convergence probe at a re-entrant corner: the exact solution is singular there (order 2/3 in 2D).
- A code that converges faster than expected is not a bug (a symmetric mode, midpoint sampling); write down the order you expect and why, and adjust only with a reason.
- Use the README's own error norm when checking a README's numbers (area-weighted, interior only, normalised).
- Budgets catch what convergence misses: an insulated wall, a source, a boundary flux. `studies.balance_check` asks for the exact budget at every resolution.
- Compiled code (C) is built and run in a `gcc` image with the same lock-down flags; nothing is compiled on the host.
- A source checkout lacks the `_version.py` that setuptools-scm or hatch-vcs writes at build time, so `import pkg` fails before any physics runs. The runner now writes a placeholder in the copy (and says so); `PHYSVERIFY_NO_VERSION_STUB=1` turns it off.
- When a repository needs a newer NumPy or SciPy than the pinned image (a dependency that requires numpy>=2.5), build the second image with `python -I sandbox/sandbox.py build --stack latest` and set `PHYSVERIFY_IMAGE=physverify-sandbox:latest-stack` for `deps` and `run`. Its packages go to `deps-latest-stack/<id>`, separate from the pinned image's.
- When a package will not import at all (a compiled extension that is not built, a GUI toolkit imported at the top), but the function under test is plain Python, load it with `physverify.loaders.extract_functions(path, ["name"])`: it takes the function and the same-file helpers it uses, and lists the imports it had to skip.
- A suspicion from reading code is not a finding until a run confirms it: two strong suspicions from code review were wrong when run (see the [troubleshooting page](../docs/troubleshooting.md)).
- A source checkout is not installed, so `importlib.metadata.version("pkg")` in `pkg/__init__.py` raises `PackageNotFoundError`. The runner puts a `sitecustomize` on the path that answers `0+source` for the repository's own distribution names (from `pyproject.toml`, `setup.cfg`, `setup.py`), only when the package is not installed, and says so; `PHYSVERIFY_NO_METADATA_SHIM=1` turns it off.
- A run killed with exit code 137 and no time-out was almost always stopped by the 2 GB memory limit; `sandbox.py` now says so. Store fewer frames or use a smaller grid.
- `sandbox.py deps --clean <id> ...` empties `deps/<id>` before installing: `pip --target` leaves files of an earlier version in place, so a downgrade does not take.
- PyTorch installs from the CPU wheel index: `sandbox.py deps <id> --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple torch` (the default CUDA wheel is too large for the install step).
- `/tmp` in the container is `noexec`, so a compiled extension copied into the repository copy fails to load ("failed to map segment"); load it from `/deps` instead.
- Installs: `PHYSVERIFY_DEPS_TIME_LIMIT` (default 2400 s). A half-finished install folder can import partly and fail later; delete `deps/<id>` and reinstall rather than patching it.
