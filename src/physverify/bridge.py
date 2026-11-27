"""Check a solver that is not written in Python (C, C++, Fortran, Julia) by running it as a command.

Much physics code is compiled. `command(template)` turns a program into a Python function: the arguments
are filled into the template, the program runs (no shell, so nothing in an argument is interpreted), and
every number it prints on stdout is read, Fortran exponents (1.0D+00) included. `command_integrate` wraps
such a program as an `integrate(source, y0, t_end, n_steps)` function, so the reference, invariant and
order studies run on it unchanged.

A compiled program cannot call a Python source term, so the manufactured-solution checks need the source
inside the program; `command_integrate` refuses a non-zero source rather than ignore it. Julia scripts go
through the same route (["julia", "solver.jl", ...]).

This runs the program: trusted code or the sandbox only.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable, Sequence

import numpy as np

_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eEdD][-+]?\d+)?|[-+]?(?:nan|inf(?:inity)?)\b", re.IGNORECASE)


def parse_numbers(text: str) -> np.ndarray:
    """Every number in `text`, in order; 1.5D+02 (Fortran) is read as 1.5e+02, and nan and inf are kept."""
    return np.array([float(t.replace("d", "e").replace("D", "e")) for t in _NUMBER.findall(text)], dtype=float)


def _args(template: Sequence[str], params: dict) -> list[str]:
    """Fill the template. An item that is exactly "{name}" with a sequence value becomes one argument per
    element; numbers are written with repr, so no digits are lost."""
    out = []
    for item in template:
        m = re.fullmatch(r"\{(\w+)\}", item)
        if m and m.group(1) in params and np.ndim(params[m.group(1)]) > 0:
            out += [repr(float(v)) for v in np.ravel(params[m.group(1)])]
            continue
        fmt = {k: (repr(float(v)) if isinstance(v, (float, np.floating)) else v) for k, v in params.items()}
        out.append(item.format(**fmt))
    return out


def command(template: Sequence[str], *, timeout: float = 60.0, cwd=None) -> Callable[..., np.ndarray]:
    """A function that runs the program in `template` with its keyword arguments filled in and returns the
    numbers it printed. Example: command(["./heat", "{n}", "{t_end}"])(n=32, t_end=0.1).

    A non-zero exit status, a time-out or output with no numbers raises RuntimeError with the end of stderr."""
    template = list(template)
    if not template:
        raise ValueError("the command template is empty")

    def run(**params) -> np.ndarray:
        args = _args(template, params)
        try:
            proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=cwd,
                                  stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"{' '.join(args)} did not finish within {timeout:g} s") from None
        except OSError as exc:
            raise RuntimeError(f"cannot run {args[0]}: {exc}") from None
        if proc.returncode != 0:
            raise RuntimeError(f"{' '.join(args)} exited with status {proc.returncode}: {proc.stderr[-500:].strip()}")
        values = parse_numbers(proc.stdout)
        if values.size == 0:
            raise RuntimeError(f"{' '.join(args)} printed no numbers on stdout")
        return values

    return run


def command_integrate(template: Sequence[str], *, timeout: float = 60.0, cwd=None, last: int | None = None):
    """`integrate(source, y0, t_end, n_steps)` for a program that takes {y0}, {t_end} and {n_steps} and prints
    the final state. With `last=d` only the last d numbers are kept (for a program that prints the whole
    trajectory or a header). A source that is not zero raises ValueError: the program cannot call it."""
    run = command(template, timeout=timeout, cwd=cwd)

    def integrate(source, y0, t_end, n_steps):
        probe = [np.max(np.abs(np.asarray(source(t), dtype=float))) for t in (0.0, 0.37 * t_end, t_end)]
        if any(v != 0 for v in probe):
            raise ValueError("a compiled program cannot call a Python source term; use the reference, invariant"
                             " or trajectory studies, or build the manufactured source into the program")
        y = run(y0=np.asarray(y0, dtype=float), t_end=float(t_end), n_steps=int(n_steps))
        return y[-last:] if last else y

    return integrate
