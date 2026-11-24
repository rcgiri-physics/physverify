"""`physverify scan PATH --run`: probes that call the code with small inputs (Phase 2 of the scan plan, ROADMAP.md).

Unlike the static scan, these probes **run the code**: use them only on code you trust, or inside the sandbox
(sandbox/). Each probe needs no reference, only a rule that must hold, and each comes from defects in the corpus study:

- smoke      every script runs to the end; the project's own tests can be collected (J253, J264, J265, J147, J157)
- edges      zero, negative and odd-size inputs give no silent NaN (I12 negative anomaly, J409 NaN at rest, G10 odd N)
- deadargs   changing an argument changes the result (J019 gamma ignored, K21 P_delta ignored, K16 mode not passed on)
- branches   a result does not jump where the code switches formula at `if x < a` (J400 jump at rho = d/2, J133)
- roundtrip  `y_to_x(x_to_y(x)) == x` for the inverse pairs the static scan lists
- siblings   two versions of one computation agree: `f` and `f_py`, `_slow` and `_fast`, `_dense` and `_sparse`
             (K18: the C and the Python STA/LTA), and one function under each value of a `method=` option
- known      a cumulative trapezoid integral, running mean or autocorrelation, found by its name, against a slow
             direct loop in any of the usual conventions (K17-style binned and windowed quantities)
- monotone   the direction a named law fixes (reverberation time falls with absorption: K16 rt60_eyring), or one
             the docstring states for an argument ("decreases with temperature")

Only module-level functions are probed, and only in files whose top level defines things and runs nothing else
(scripts are covered by the smoke probe). Inputs are the function's own numeric defaults, then guesses from the
parameter names. Each file runs in its own process with a time limit; a file or function that runs out of time,
or that the probes cannot call, is reported as SKIP, never as passed.
"""

from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import warnings
from pathlib import Path

from .probing.branches import _probe_branches
from .probing.common import _CALL_LIMIT, _Fn, _import
from .probing.deadargs import _probe_dead
from .probing.edges import _probe_edges
from .probing.known import _probe_known
from .probing.monotone import _probe_monotone
from .probing.roundtrip import _probe_roundtrips
from .probing.siblings import _baseline, _probe_options, _probe_siblings
from .stages.common import NOTE, WARN, Finding, python_files

SKIP = "SKIP"
PROBES = ("smoke", "edges", "deadargs", "branches", "roundtrip", "siblings", "known", "monotone")
# what `scan --run` runs without --only: the probes that found real defects in the 626-repository sweep (2026-10-26).
# The others found none there and are kept as opt-in experiments (results/corpus/FEATURES.md).
DEFAULT_PROBES = ("smoke", "branches")

# functions that write, plot, fetch or start things are not called
_SIDE_EFFECT = re.compile(r"(^|_)(main|run|save|write|plot|show|draw|load|read|download|fetch|open|print|export|"
                          r"animate|gui|app|cli|parse|setup|install|test|clean|delete|remove|mkdir|serve)(_|$)", re.I)


def _safe_module(tree) -> bool:
    """True when importing the file only defines things: no top-level calls, loops or `with` blocks."""
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                             ast.Assign, ast.AnnAssign, ast.Try, ast.Pass)):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue  # docstring
        if isinstance(node, ast.If):
            continue  # `if __name__ == "__main__":` and version switches
        return False
    return True


def _runs_something(tree) -> bool:
    """True for scripts: a `__main__` block or top-level statements beyond definitions."""
    for node in tree.body:
        if isinstance(node, ast.If) and "__main__" in ast.unparse(node.test):
            return True
    return not _safe_module(tree)


def worker(path: str, root: str, rel: str, probes) -> list[Finding]:
    """Probe the module-level functions of one file (runs in its own process)."""
    import numpy as np  # noqa: F401 - fail early when NumPy is missing

    os.environ.setdefault("MPLBACKEND", "Agg")
    p, out = Path(path), []
    tree = ast.parse(p.read_text(encoding="utf-8-sig", errors="replace"))
    try:
        with contextlib.redirect_stdout(io.StringIO()), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mod = _import(p, Path(root))
    except BaseException as exc:  # noqa: BLE001 - SystemExit too
        return [Finding("run", SKIP, rel, 1, f"not probed: the module does not import ({type(exc).__name__}: {str(exc)[:200]})")]
    allfns = {}  # private ones too: `_trace_dense` and `_trace_sparse` are siblings worth comparing
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or _SIDE_EFFECT.search(node.name):
            continue
        fn = getattr(mod, node.name, None)
        if callable(fn) and not node.args.kwonlyargs and getattr(fn, "__module__", None) == mod.__name__:
            allfns[node.name] = _Fn(node.name, fn, node, mod)
    fns = {k: v for k, v in allfns.items() if not k.startswith("_")}
    if "roundtrip" in probes:
        _probe_roundtrips(fns, out, rel)
    if "siblings" in probes:
        try:
            _probe_siblings(allfns, out, rel)
        except Exception as exc:  # noqa: BLE001
            out.append(Finding("run", SKIP, rel, 1, f"siblings probe stopped ({type(exc).__name__})"))
    for f in fns.values():
        if not f.params:
            continue
        if "known" in probes:
            try:
                _probe_known(f, out, rel)
            except Exception as exc:  # noqa: BLE001
                out.append(Finding("run", SKIP, rel, f.node.lineno, f"{f.name}: known probe stopped ({type(exc).__name__})"))
        start = _baseline(f)
        if start is None:
            continue  # functions taking objects, strings or callables are not probed (not a SKIP: nothing applies)
        base, y0, dt = start
        if dt > _CALL_LIMIT:
            out.append(Finding("run", SKIP, rel, f.node.lineno, f"{f.name}: one call took {dt:.1f} s; its probes were skipped"))
            continue
        for name, run in (("deadargs", _probe_dead), ("edges", _probe_edges), ("branches", _probe_branches),
                          ("siblings", _probe_options), ("monotone", _probe_monotone)):
            if name in probes:
                try:
                    run(f, base, y0, out, rel)
                except Exception as exc:  # noqa: BLE001
                    out.append(Finding("run", SKIP, rel, f.node.lineno, f"{f.name}: {name} probe stopped ({type(exc).__name__})"))
    return out


# --- driver ---------------------------------------------------------------------------------------

def _collect_tests(root: Path, timeout: float) -> list[Finding]:
    if not any((root / d).is_dir() for d in ("tests", "test")) and not list(root.glob("test_*.py")):
        return []
    try:
        p = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"], cwd=root,
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout,
                           env=dict(os.environ, MPLBACKEND="Agg"))
    except subprocess.TimeoutExpired:
        return [Finding("smoke", SKIP, "tests", 1, f"collecting the project's tests took longer than {timeout:g} s")]
    errors = [ln for ln in p.stdout.splitlines() if ln.startswith("ERROR ")]
    if "No module named pytest" in p.stderr:
        return [Finding("smoke", SKIP, "tests", 1, "pytest is not installed, so the project's tests were not collected")]
    return [Finding("smoke", NOTE, ln.split()[1].split("::")[0], 1,
                    f"the project's own test file does not import under pytest: {ln[6:][:200]}", rule="PV909") for ln in errors[:20]]


_CODE_ERRORS = ("NameError", "TypeError", "AttributeError", "IndexError", "ZeroDivisionError", "UnboundLocalError",
                "SyntaxError", "KeyError")


def _code_error(detail: str, src: str) -> bool:
    """True when the script's last error points at the code rather than at what it was given or what is installed."""
    kind = detail.split(":")[0].strip()
    if kind not in _CODE_ERRORS:
        return False
    if kind in ("IndexError", "KeyError") and re.search(r"\bargv\b|os\.environ|getenv", src):
        return False  # run without the command-line arguments or environment variables it expects (J265 from sys import argv)
    if kind == "IndexError" and re.search(r"\.glob\(|iterdir\(|listdir\(|read_csv\(|loadtxt\(", src):
        return False  # a list of data files or rows that is empty in a bare clone (F04 summarize, J099)
    m = re.match(r"NameError: name '(\w+)'", detail)
    if m and re.search(r"\bargv\b", src) and re.search(rf"^\s+{m.group(1)}\s*=", src, re.M):
        return False  # set only on the command-line branch the probe did not take (K15 ROOT = sys.argv[2])
    if kind == "TypeError" and re.search(r"not NoneType|'NoneType' object is not (iterable|subscriptable)", detail) \
            and re.search(r"argparse|sys\.argv|os\.environ|getenv|input\(", src):
        return False  # a path or option that would come from the command line was None
    if kind == "AttributeError" and "'NoneType' object has no attribute" in detail and re.search(r"=\s*None|\bcp\b|cupy|cuda|torch|jax", src):
        return False  # an optional package set to None when it is not installed (torch = None)
    m = re.search(r"module '([\w.]+)' has no attribute", detail)
    if m and m.group(1).split(".")[0] not in ("numpy", "scipy", "matplotlib"):
        return False  # a platform module (ctypes.windll) or a stub of a package that is not installed
    return True


def probe(path, *, probes=PROBES, timeout: float = 60.0) -> list[Finding]:
    """Run the probes on every Python file under `path`. Runs the code: trusted code or the sandbox only."""
    from .smoke import OK, TIMEOUT, smoke_script

    root = Path(path)
    out = []
    for f in python_files(root):
        rel = str(f.relative_to(root)) if root.is_dir() else f.name
        try:
            tree = ast.parse(f.read_text(encoding="utf-8-sig", errors="replace"))
        except (SyntaxError, ValueError):
            continue  # the static scan reports files that do not parse
        if f.name.startswith("test_") or "tests" in Path(rel).parts or f.name in ("setup.py", "conftest.py"):
            continue
        # a module inside a package is written to be imported (top-level calls there are registrations, not runs),
        # and run by path it fails on its relative imports; loose files are scripts unless they only define things
        in_package = (f.parent / "__init__.py").exists() and f.name != "__main__.py"
        if not in_package and _runs_something(tree):
            if "smoke" in probes:
                r = smoke_script(f, timeout=timeout)
                if r.outcome == TIMEOUT:
                    out.append(Finding("smoke", SKIP, rel, 1, f"the script was still running after {timeout:g} s"))
                elif r.outcome != OK:
                    level = WARN if _code_error(r.detail, f.read_text(encoding="utf-8", errors="replace")) else NOTE
                    out.append(Finding("smoke", level, rel, 1, f"the script stops with an error: {r.detail}", rule="PV910"))
            if not _safe_module(tree):
                continue
        func_probes = [p for p in probes if p != "smoke"]
        if not func_probes or not any(isinstance(n, ast.FunctionDef) for n in tree.body):
            continue
        out += _run_worker(f, root if root.is_dir() else f.parent, rel, func_probes, timeout)
    if "smoke" in probes and root.is_dir():
        out += _collect_tests(root, timeout)
    return out


def _run_worker(f: Path, root: Path, rel: str, probes, timeout: float) -> list[Finding]:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        res = Path(tmp) / "out.json"
        cmd = [sys.executable, "-m", "physverify.probes", str(f.resolve()), str(root.resolve()), rel, ",".join(probes), str(res)]
        # the worker must import this copy of physverify, installed or not
        here = str(Path(__file__).resolve().parents[1])
        env = dict(os.environ, MPLBACKEND="Agg", PYTHONPATH=os.pathsep.join(filter(None, [here, os.environ.get("PYTHONPATH")])))
        try:
            r = subprocess.run(cmd, cwd=tmp, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout, env=env)
        except subprocess.TimeoutExpired:
            return [Finding("run", SKIP, rel, 1, f"probing this file took longer than {timeout:g} s; its functions were not probed")]
        if not res.exists():
            last = [ln for ln in (r.stderr or "").strip().splitlines() if ln.strip()][-1:] or [f"exit code {r.returncode}"]
            return [Finding("run", SKIP, rel, 1, f"the probe process stopped before reporting: {last[0][:200]}")]
        return [Finding(**d) for d in json.loads(res.read_text(encoding="utf-8"))]


def _main(argv) -> int:
    from dataclasses import asdict

    path, root, rel, probes, res = argv
    found = worker(path, root, rel, probes.split(","))
    Path(res).write_text(json.dumps([asdict(f) for f in found]), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
