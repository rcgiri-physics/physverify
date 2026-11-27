"""Comparison with units: refuse to compare quantities of different dimension.

Most adapter mistakes in one corpus batch were units or origins: a result in km compared with a reference
in m, or an energy per mole with an energy per particle. `compare_quantities` compares two values that may
carry pint units (https://pint.readthedocs.io). With units on both sides it converts the value to the
reference's units first and FAILs when the dimensions differ; with units on one side only it FAILs too,
since a bare number cannot be checked against a unit. Plain numbers on both sides are compared as numbers,
as `close_result` does.

pint is optional: physverify imports it only when a value carries units, so code without pint is unaffected.
"""

from __future__ import annotations

import numpy as np

from .checks import FAIL, PASS, Result


def _has_units(x) -> bool:
    return hasattr(x, "units") and hasattr(x, "magnitude") and hasattr(x, "dimensionality")


def compare_quantities(value, expected, *, rtol: float = 1e-8, atol=0.0) -> Result:
    """PASS when `value` is within rtol (relative to the largest |expected|) plus atol of `expected`.

    Either may be a pint Quantity (scalar or array). `atol` may carry units too; a bare atol is taken in the
    reference's units. A difference in dimension, or units on one side only, is a FAIL that says which."""
    vu, eu = _has_units(value), _has_units(expected)
    if vu != eu:
        side, other = ("value", "reference") if vu else ("reference", "value")
        units = value.units if vu else expected.units
        return Result(FAIL, f"the {side} has units ({units:~}) and the {other} is a bare number; give both units,"
                            " or neither, so that a unit mistake cannot pass")
    unit_text = ""
    if vu:
        if value.dimensionality != expected.dimensionality:
            return Result(FAIL, f"different dimensions: the value is in {value.units:~} ({value.dimensionality}) and"
                                f" the reference in {expected.units:~} ({expected.dimensionality}); these cannot be"
                                " compared, so a unit or formula is wrong in the test or the code")
        unit_text = f" (compared in {expected.units:~})"
        value = value.to(expected.units).magnitude
        if _has_units(atol):
            if atol.dimensionality != expected.dimensionality:
                return Result(FAIL, f"atol is in {atol.units:~}, which is not a unit of the reference ({expected.units:~})")
            atol = atol.to(expected.units).magnitude
        expected = expected.magnitude
    elif _has_units(atol):
        return Result(FAIL, "atol has units but the value and reference are bare numbers")
    v = np.asarray(value, dtype=float)
    e = np.asarray(expected, dtype=float)
    if v.shape != e.shape and v.size != 1 and e.size != 1:
        return Result(FAIL, f"shapes differ: value {v.shape}, reference {e.shape}")
    if not (np.all(np.isfinite(v)) and np.all(np.isfinite(e))):
        return Result(FAIL, "the value or the reference has NaN or inf entries")
    scale = float(np.max(np.abs(e))) if e.size else 0.0
    diff = float(np.max(np.abs(v - e))) if v.size else 0.0
    allowed = rtol * scale + float(atol)
    msg = f"largest difference {diff:.3g}, allowed {allowed:.3g} (rtol {rtol:g}, atol {float(atol):g}){unit_text}"
    return Result(PASS if diff <= allowed else FAIL, msg)
