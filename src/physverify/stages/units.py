"""Stage `units`: a physical-type table whose unit has another dimension than its name (PV701)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from .common import WARN, Finding, all_nodes

# --- units ------------------------------------------------------------------------------------------

# dimension as exponents of (m, kg, s, A, K, mol, cd)
_UNIT = {
    "m": (1, 0, 0, 0, 0, 0, 0), "kg": (0, 1, 0, 0, 0, 0, 0), "s": (0, 0, 1, 0, 0, 0, 0), "A": (0, 0, 0, 1, 0, 0, 0),
    "K": (0, 0, 0, 0, 1, 0, 0), "mol": (0, 0, 0, 0, 0, 1, 0), "cd": (0, 0, 0, 0, 0, 0, 1), "g": (0, 1, 0, 0, 0, 0, 0),
    "cm": (1, 0, 0, 0, 0, 0, 0), "km": (1, 0, 0, 0, 0, 0, 0), "rad": (0,) * 7, "sr": (0,) * 7,
    "N": (1, 1, -2, 0, 0, 0, 0), "J": (2, 1, -2, 0, 0, 0, 0), "W": (2, 1, -3, 0, 0, 0, 0), "Pa": (-1, 1, -2, 0, 0, 0, 0),
    "Hz": (0, 0, -1, 0, 0, 0, 0), "C": (0, 0, 1, 1, 0, 0, 0), "V": (2, 1, -3, -1, 0, 0, 0),
    "Ohm": (2, 1, -3, -2, 0, 0, 0), "ohm": (2, 1, -3, -2, 0, 0, 0), "F": (-2, -1, 4, 2, 0, 0, 0),
    "T": (0, 1, -2, -1, 0, 0, 0), "Wb": (2, 1, -2, -1, 0, 0, 0), "H": (2, 1, -2, -2, 0, 0, 0), "S": (-2, -1, 3, 2, 0, 0, 0),
    "erg": (2, 1, -2, 0, 0, 0, 0), "dyn": (1, 1, -2, 0, 0, 0, 0), "eV": (2, 1, -2, 0, 0, 0, 0),
}
# physical-type name -> dimension
_QUANTITY = {
    "length": "m", "mass": "kg", "time": "s", "electrical current": "A", "temperature": "K",
    "amount of substance": "mol", "luminous intensity": "cd", "area": "m2", "volume": "m3",
    "speed": "m s-1", "velocity": "m s-1", "acceleration": "m s-2", "frequency": "s-1", "wavenumber": "m-1",
    "force": "m kg s-2", "energy": "m2 kg s-2", "work": "m2 kg s-2", "torque": "m2 kg s-2", "power": "m2 kg s-3",
    "pressure": "m-1 kg s-2", "stress": "m-1 kg s-2", "momentum": "m kg s-1", "angular momentum": "m2 kg s-1",
    "action": "m2 kg s-1", "mass density": "m-3 kg", "surface tension": "kg s-2", "dynamic viscosity": "m-1 kg s-1",
    "kinematic viscosity": "m2 s-1", "diffusivity": "m2 s-1", "electrical charge": "s A",
    "electrical potential": "m2 kg s-3 A-1", "electrical resistance": "m2 kg s-3 A-2",
    "electrical capacitance": "m-2 kg-1 s4 A2", "magnetic flux": "m2 kg s-2 A-1",
    "magnetic flux density": "kg s-2 A-1", "inductance": "m2 kg s-2 A-2", "electrical conductance": "m-2 kg-1 s3 A2",
    "electrical field strength": "m kg s-3 A-1", "heat capacity": "m2 kg s-2 K-1", "entropy": "m2 kg s-2 K-1",
    "specific heat capacity": "m2 s-2 K-1", "thermal conductivity": "m kg s-3 K-1", "energy flux": "kg s-3",
    "irradiance": "kg s-3", "spectral flux density": "kg s-2", "molar mass": "kg mol-1", "molar volume": "m3 mol-1",
    "electrical dipole moment": "m s A", "compressibility": "m kg-1 s2", "jerk": "m s-3",
}
_BASE = ("m", "kg", "s", "A", "K", "mol", "cd")


def _dim_of_text(text: str):
    d = [0] * 7
    for part in text.split():
        m = re.fullmatch(r"(m|kg|s|A|K|mol|cd)(-?\d+)?", part)
        d[_BASE.index(m.group(1))] += int(m.group(2) or 1)
    return tuple(d)


_QDIM = {k: _dim_of_text(v) for k, v in _QUANTITY.items()}


def _dim(node):
    """Dimension of an expression of unit attributes (si.W * si.m**2 / si.Hz), or None."""
    if isinstance(node, ast.Attribute) and node.attr in _UNIT:
        return _UNIT[node.attr]
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Pow) and isinstance(node.right, (ast.Constant, ast.UnaryOp)):
            p = node.right.value if isinstance(node.right, ast.Constant) else (
                -node.right.operand.value if isinstance(node.right.op, ast.USub) and isinstance(node.right.operand, ast.Constant) else None)
            a = _dim(node.left)
            if a is None or not isinstance(p, (int, float)):
                return None
            return tuple(x * p for x in a)
        a, b = _dim(node.left), _dim(node.right)
        if a is None or b is None:
            return None
        if isinstance(node.op, ast.Mult):
            return tuple(x + y for x, y in zip(a, b))
        if isinstance(node.op, ast.Div):
            return tuple(x - y for x, y in zip(a, b))
    return None


def _show(d) -> str:
    return " ".join(f"{u}^{p:g}" if p != 1 else u for u, p in zip(_BASE, d) if p) or "dimensionless"


def scan_units(path: Path, tree, rel: str) -> list[Finding]:
    """(unit expression, "physical type") pairs whose dimensions disagree."""
    out = []
    for n in all_nodes(tree):
        if not (isinstance(n, ast.Tuple) and len(n.elts) >= 2 and isinstance(n.elts[0], (ast.BinOp, ast.Attribute))):
            continue
        names = n.elts[1:]
        texts = [e.value for e in names if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        if isinstance(names[0], (ast.Set, ast.List, ast.Tuple)):
            texts = [e.value for e in names[0].elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        d = _dim(n.elts[0])
        if d is None:
            continue
        for t in texts:
            q = _QDIM.get(t.lower())
            if q is not None and q != d:
                out.append(Finding("units", WARN, rel, n.lineno,
                                   f"{ast.unparse(n.elts[0])} has dimension {_show(d)}, but \"{t}\" has {_show(q)}", rule="PV701"))
    return out
