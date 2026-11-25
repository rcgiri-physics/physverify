"""A spec written as a `[[tool.physverify.ode]]` table in pyproject.toml, for fixed-step ODE solvers.

    [[tool.physverify.ode]]
    solver = "mysolver:integrate"
    args = ["source", "y0", "t_end", "n_steps"]
    order = 4
    t_end = 1.0
    y0 = { x = 1.0, v = 0.0 }
    parameters = { omega = 3.0 }
    equations = { x = "v", v = "-omega**2 * x" }

`physverify run pyproject.toml` runs the same bundle as a Python spec (studies.ode_checks).
The equations are read with a small parser that accepts arithmetic and a fixed list of
functions. They are never passed to eval or to SymPy's sympify (which uses eval), so the
text in the table cannot run code. Importing and calling the solver does, as in any spec.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import math
import operator
import sys
from collections.abc import Callable
from pathlib import Path

import numpy as np

from .checks import Check
from .mms import ManufacturedODE
from .scaffold import default_ns
from .studies import invariant_study, ode_checks, reference_study

FUNCTIONS = {name: getattr(np, name) for name in
             ("sin", "cos", "tan", "arcsin", "arccos", "arctan", "arctan2", "sinh", "cosh", "tanh", "exp", "log", "sqrt")}
FUNCTIONS["abs"] = np.abs
NARGS = {"arctan2": 2}
CONSTANTS = {"pi": math.pi}
ARGS = ("source", "f", "y0", "t0", "t_end", "n_steps", "h", "times")
RETURNS = ("final", "trajectory")
KEYS = {"solver", "path", "label", "args", "returns", "order", "t_end", "n_steps", "y0", "parameters", "equations",
        "conserved", "patch"}
_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
           ast.Pow: operator.pow}


class SpecError(ValueError):
    """The table cannot be turned into checks."""


def compile_expression(text: str, names) -> Callable[[dict], float]:
    """A function of {name: value} for an arithmetic expression in `names`, read without eval."""
    if not isinstance(text, str):
        raise SpecError(f"an expression must be text in quotes, got {text!r}")
    try:
        tree = ast.parse(text.strip(), mode="eval").body
    except (SyntaxError, ValueError, RecursionError, MemoryError) as exc:
        raise SpecError(f"cannot read the expression {text!r}: {exc}") from None
    allowed = set(names)

    def build(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = float(node.value)
            return lambda env: value
        if isinstance(node, ast.Name):
            name = node.id
            if name in allowed:
                return lambda env: env[name]
            if name in CONSTANTS:
                constant = CONSTANTS[name]
                return lambda env: constant
            raise SpecError(f"unknown name {name!r} in {text!r}; known names: {', '.join(sorted(allowed | set(CONSTANTS)))}")
        if isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.BitXor):
                raise SpecError(f"write a power as ** rather than ^ in {text!r}")
            if type(node.op) in _BINARY:
                op, left, right = _BINARY[type(node.op)], build(node.left), build(node.right)
                return lambda env: op(left(env), right(env))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            sign, operand = (-1.0 if isinstance(node.op, ast.USub) else 1.0), build(node.operand)
            return lambda env: sign * operand(env)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            name = node.func.id
            if name not in FUNCTIONS:
                raise SpecError(f"unknown function {name!r} in {text!r}; known functions: {', '.join(sorted(FUNCTIONS))}")
            if len(node.args) != NARGS.get(name, 1):
                raise SpecError(f"{name} takes {NARGS.get(name, 1)} argument(s) in {text!r}")
            func, args = FUNCTIONS[name], [build(a) for a in node.args]
            return lambda env: func(*[a(env) for a in args])
        raise SpecError(f"{ast.unparse(node)!r} is not allowed in {text!r}; use numbers, names, + - * / ** and functions")

    return build(tree)


def _number(value, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise SpecError(f"{what} must be a finite number, got {value!r}")
    return float(value)


def _table(table: dict, key: str) -> dict:
    value = table.get(key, {})
    if not isinstance(value, dict):
        raise SpecError(f"{key} must be a table, for example {key} = {{ x = ... }}")
    return value


def _load_solver(table: dict, root: Path) -> Callable:
    target = table["solver"]
    module_name, _, function = target.partition(":") if isinstance(target, str) else ("", "", "")
    if not function.isidentifier() or not all(p.isidentifier() for p in module_name.split(".")):
        raise SpecError(f'solver must be "module:function", got {target!r}')
    subfolder = table.get("path", ".")
    if not isinstance(subfolder, str):
        raise SpecError(f"path must be text, got {subfolder!r}")
    folder = (root / subfolder).resolve()
    if not folder.is_relative_to(root):  # as for `specs` (GCVE-110-VULN-PYPI-2026-000391)
        raise SpecError(f"path {subfolder!r} leaves the project folder")
    if str(folder) in sys.path:
        sys.path.remove(str(folder))
    sys.path.insert(0, str(folder))
    # forget a module of the same name loaded earlier, from another project or before an edit
    top = module_name.split(".")[0]
    for name, mod in list(sys.modules.items()):
        if name == top or name.startswith(top + "."):
            origin = getattr(mod, "__file__", None) or ""
            if top != "physverify" and "site-packages" not in origin and "dist-packages" not in origin:
                del sys.modules[name]
                try:  # a .pyc can survive a same-size edit within the same second (as in report.load_spec)
                    Path(importlib.util.cache_from_source(origin)).unlink(missing_ok=True)
                except (NotImplementedError, ValueError, OSError):
                    pass
    importlib.invalidate_caches()
    solver = getattr(importlib.import_module(module_name), function, None)
    if not callable(solver):
        raise SpecError(f"{module_name} has no function {function!r}")
    return solver


def ode_table_checks(table: dict, root) -> list[Check]:
    """The checks for one `[[tool.physverify.ode]]` table; `root` is the folder of its pyproject.toml."""
    root = Path(root).resolve()
    unknown = set(table) - KEYS
    if unknown:
        raise SpecError(f"unknown key(s) {', '.join(sorted(unknown))}; known keys: {', '.join(sorted(KEYS))}")
    missing = [k for k in ("solver", "order", "t_end", "y0", "equations") if k not in table]
    if missing:
        raise SpecError(f"missing key(s): {', '.join(missing)}")

    equations, start = _table(table, "equations"), _table(table, "y0")
    states = list(equations)
    if not states:
        raise SpecError("equations is empty")
    if set(start) != set(states):
        raise SpecError(f"y0 and equations must name the same variables: {sorted(start)} and {sorted(states)}")
    if list(start) != states:
        raise SpecError(f"y0 and equations must list the variables in the same order, the solver's: {list(start)} and {states}")
    parameters = {k: _number(v, f"parameter {k}") for k, v in _table(table, "parameters").items()}
    reserved = {"t", *CONSTANTS, *FUNCTIONS}
    for name in [*states, *parameters]:
        if not name.isidentifier() or name in reserved:
            raise SpecError(f"{name!r} cannot be used as a name (reserved, or not an identifier)")
    if set(states) & set(parameters):
        raise SpecError(f"both a variable and a parameter: {', '.join(sorted(set(states) & set(parameters)))}")
    y0 = np.array([_number(start[s], f"y0.{s}") for s in states])
    rhs = [compile_expression(equations[s], {"t", *states, *parameters}) for s in states]

    def reference(t, y):
        env = {"t": t, **parameters, **dict(zip(states, y))}
        return np.array([g(env) for g in rhs], dtype=float)

    order, t_end = _number(table["order"], "order"), _number(table["t_end"], "t_end")
    if order <= 0 or t_end <= 0:
        raise SpecError("order and t_end must be positive")
    ns = table.get("n_steps", list(default_ns(order)))
    if not isinstance(ns, list) or not all(type(n) is int and n > 0 for n in ns) or len(set(ns)) < 3:
        raise SpecError("n_steps must be a list of at least 3 different positive whole numbers")
    args = table.get("args", ["source", "y0", "t_end", "n_steps"])
    if not isinstance(args, list) or not args or any(a not in ARGS for a in args):
        raise SpecError(f"args must list, in the solver's order, some of: {', '.join(ARGS)}")
    if not {"n_steps", "h", "times"} & set(args):
        raise SpecError("args must include n_steps, h or times, or the step size cannot be refined")
    if "f" in args and "source" in args:
        raise SpecError("args may include f or source, not both (f already contains the source)")
    returns = table.get("returns", "final")
    if returns not in RETURNS:
        raise SpecError(f"returns must be one of {', '.join(RETURNS)}, got {returns!r}")
    patch = table.get("patch", False)
    if not isinstance(patch, bool):
        raise SpecError(f"patch must be true or false, got {patch!r}")
    forced = "f" in args or "source" in args
    if patch and not forced:
        raise SpecError("patch needs source or f in args")
    quantity: Callable | None = None
    if "conserved" in table:
        conserved = compile_expression(table["conserved"], {*states, *parameters})

        def quantity(y):
            return float(conserved({**parameters, **dict(zip(states, y))}))

    label = table.get("label", table["solver"])
    if not isinstance(label, str):
        raise SpecError(f"label must be text, got {label!r}")
    solver = _load_solver(table, root)
    if "f" in args:
        label += " (integrator only: the equations come from the table)"
    elif not forced:
        label += " (no source term: no manufactured solution)"

    def run(source, y_start, t_stop, n):
        values = {"source": source, "f": lambda t, y: reference(t, y) + source(t), "y0": np.array(y_start, dtype=float),
                  "t0": 0.0, "t_end": t_stop, "n_steps": n, "h": t_stop / n, "times": np.linspace(0.0, t_stop, n + 1)}
        out = np.asarray(solver(*[values[a] for a in args]), dtype=float)
        shape = (len(states),) if returns == "final" else (n + 1, len(states))
        # the shape is required, so that a broadcast or a run of the wrong length is not read as a result
        if out.shape != shape:
            raise ValueError(f"the solver returned shape {out.shape}; expected {shape} for {n} steps (returns = {returns!r})")
        return out

    def final(source, y_start, t_stop, n):
        out = run(source, y_start, t_stop, n)
        return out if returns == "final" else out[-1]

    if not forced:
        checks = [Check("reference", label, lambda: reference_study(final, reference, y0, t_end, ns, order, floor=1e-12))]
        if quantity is not None:
            checks.append(Check("invariant", label,
                                lambda: invariant_study(final, quantity, y0, t_end, ns, order, floor=1e-12)))
        return checks
    # smooth, with a different frequency per variable, around the starting state
    k = np.arange(1, len(states) + 1)
    manufactured = ManufacturedODE(lambda t: y0 + 0.1 * np.sin(0.7 * k * t + 0.3), reference,
                                   du=lambda t: 0.07 * k * np.cos(0.7 * k * t + 0.3))
    return ode_checks(label, final, rhs_ref=reference, mms=manufactured, y0_free=y0, t_end=t_end, ns=ns, order=order,
                      quantity=quantity, patch=(y0, np.linspace(0.1, -0.05, len(states))) if patch else None,
                      integrate_trajectory=run if returns == "trajectory" else None)


def read_config(path) -> dict:
    """The [tool.physverify] table of a pyproject.toml, {} when it has none."""
    try:
        import tomllib
    except ImportError:  # Python 3.10
        import tomli as tomllib  # type: ignore[no-redef]
    tool = tomllib.loads(Path(path).read_text(encoding="utf-8")).get("tool", {})
    config = tool.get("physverify", {}) if isinstance(tool, dict) else {}
    return config if isinstance(config, dict) else {}


def load_toml_spec(path) -> list[Check]:
    """The checks of every `[[tool.physverify.ode]]` table in a TOML file."""
    path = Path(path).resolve()
    tables = read_config(path).get("ode", [])
    if not isinstance(tables, list) or not all(isinstance(t, dict) for t in tables):
        raise SpecError(f"{path.name}: write [[tool.physverify.ode]] with two brackets")
    checks = []
    for i, table in enumerate(tables, 1):
        try:
            checks += ode_table_checks(table, path.parent)
        except SpecError as exc:
            raise SpecError(f"{path.name}, [[tool.physverify.ode]] number {i}: {exc}") from None
    return checks
