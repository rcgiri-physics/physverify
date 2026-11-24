"""Stage `pairs`: functions whose names say they are inverses, listed for a round-trip check (PV202)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from .common import NOTE, Finding, all_nodes

# --- inverse pairs --------------------------------------------------------------------------------

_PAIR = re.compile(r"^(?P<pre>.*?)(?P<x>[a-z0-9]+)(?P<sep>_to_|2)(?P<y>[a-z0-9]+)(?P<post>.*)$", re.I)


def scan_pairs(path: Path, tree, rel: str) -> list[Finding]:
    # test_x_to_y / test_y_to_x test an inverse pair; they are not converters to run
    funcs = {n.name: n.lineno for n in all_nodes(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("test")}
    found, seen = [], set()
    for fname, line in funcs.items():
        m = _PAIR.match(fname)
        if not m or m["x"].lower() == m["y"].lower():
            continue
        other = f"{m['pre']}{m['y']}{m['sep']}{m['x']}{m['post']}"
        if other in funcs and frozenset((fname, other)) not in seen:
            seen.add(frozenset((fname, other)))
            found.append(Finding("pairs", NOTE, rel, line,
                                 f"{fname} and {other} look like inverses: run"
                                 f" physverify.identities.check_roundtrip({fname}, {other}, inputs) on typical inputs", rule="PV202"))
    return found
