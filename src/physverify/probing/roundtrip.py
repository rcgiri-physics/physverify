"""Probe `roundtrip`: functions named as inverses undo each other (PV904)."""

from __future__ import annotations

from ..probing.common import _as_array, _finite, _short
from ..stages.common import WARN, Finding
from ..stages.pairs import _PAIR


def _probe_roundtrips(fns, out, rel):
    import numpy as np

    for name, f in fns.items():
        m = _PAIR.match(name)
        if not m or m["x"].lower() == m["y"].lower():
            continue
        other = f"{m['pre']}{m['y']}{m['sep']}{m['x']}{m['post']}"
        g = fns.get(other)
        if g is None or name > other or len(f.params) - len(f.has_default) != 1 or len(g.params) - len(g.has_default) != 1:
            continue
        p = f.params[0]
        bad = None
        for x in (0.7, np.linspace(0.1, 1.0, 8)):
            try:
                y = f.fn(x)
                z = g.fn(y)
            except Exception:  # noqa: BLE001 - inputs outside the domain are not probed
                continue
            za, xa = _as_array(z), _as_array(x)
            if za is None or za.shape != xa.shape or not _finite(za):
                continue
            err = float(np.max(np.abs(za - xa)) / np.max(np.abs(xa)))
            if err > 1e-6:
                bad = (x, err)
                break
        if bad:
            out.append(Finding("roundtrip", WARN, rel, f.node.lineno,
                               f"{other}({name}({p})) differs from {p} by {bad[1]:.2g} (relative) for {p} = {_short(bad[0])};"
                               " the two names say they are inverses", rule="PV904"))
