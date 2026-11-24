"""Probe `edges`: zero, negative and odd-size inputs give no silent NaN (PV902)."""

from __future__ import annotations

from ..probing.common import _STATE_NAME, _divisors, _finite, _short
from ..stages.common import NOTE, Finding


def _probe_edges(f, args, y0, out, rel):
    import numpy as np

    if not _finite(y0):
        return
    divisors = _divisors(f.node)
    for p, v in args.items():
        if isinstance(v, bool) or not isinstance(v, (int, float, np.ndarray, np.integer, np.floating)):
            continue
        if isinstance(v, (int, np.integer)):
            tries = [("an odd value", int(v) + 1 if int(v) % 2 == 0 else int(v) + 2),
                     ("an even value", int(v) + 1 if int(v) % 2 else int(v) + 2)]
        elif _STATE_NAME.match(p):
            # coordinates, velocities and angles may be zero or negative whatever the documentation says
            tries = [] if p in divisors else [("zero", np.zeros_like(v) if isinstance(v, np.ndarray) else 0.0)]
            tries.append(("a negative value", -np.abs(v) if isinstance(v, np.ndarray) else -abs(float(v)) or -0.7))
        elif not isinstance(v, np.ndarray) and p not in divisors:
            tries = [("zero", 0.0)]
        else:
            continue
        for what, x in tries:
            try:
                y, _ = f.call({**args, p: x})
            except Exception:  # noqa: BLE001 - refusing an input is allowed; a silent NaN is the concern
                continue
            if y is not None and not _finite(y):
                out.append(Finding("edges", NOTE, rel, f.node.lineno,
                                   f"{f.name}: with {p} = {what} ({_short(x)}) and the other inputs unchanged, the result"
                                   " has NaN or infinite values without an error; check that the documentation excludes this input", rule="PV902"))
                break
