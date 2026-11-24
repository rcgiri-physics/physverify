"""Stage `api`: NumPy, SciPy, JAX and Python features that have been removed or changed (PV501 to PV509)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from .common import NOTE, WARN, Finding, _aliases, _guarded, all_nodes

# --- removed APIs -----------------------------------------------------------------------------------

# attribute of numpy -> (replacement, what happened)
_NUMPY = {
    **{k: ("np.nan", "removed in NumPy 2.0") for k in ("NaN", "NAN")},
    **{k: ("np.inf", "removed in NumPy 2.0") for k in ("Inf", "Infinity", "infty", "PINF")},
    "NINF": ("-np.inf", "removed in NumPy 2.0"),
    "PZERO": ("0.0", "removed in NumPy 2.0"), "NZERO": ("-0.0", "removed in NumPy 2.0"),
    "float_": ("np.float64", "removed in NumPy 2.0"), "complex_": ("np.complex128", "removed in NumPy 2.0"),
    "cfloat": ("np.complex128", "removed in NumPy 2.0"), "singlecomplex": ("np.complex64", "removed in NumPy 2.0"),
    "longfloat": ("np.longdouble", "removed in NumPy 2.0"), "longcomplex": ("np.clongdouble", "removed in NumPy 2.0"),
    "clongfloat": ("np.clongdouble", "removed in NumPy 2.0"), "string_": ("np.bytes_", "removed in NumPy 2.0"),
    "unicode_": ("np.str_", "removed in NumPy 2.0"),
    "alltrue": ("np.all", "removed in NumPy 2.0"), "sometrue": ("np.any", "removed in NumPy 2.0"),
    "product": ("np.prod", "removed in NumPy 2.0"), "cumproduct": ("np.cumprod", "removed in NumPy 2.0"),
    "round_": ("np.round", "removed in NumPy 2.0"), "asfarray": ("np.asarray(x, dtype=float)", "removed in NumPy 2.0"),
    "find_common_type": ("np.result_type", "removed in NumPy 2.0"), "cast": ("arr.astype", "removed in NumPy 2.0"),
    "mat": ("np.asmatrix", "removed in NumPy 2.0"), "msort": ("np.sort(a, axis=0)", "removed in NumPy 2.0"),
    "issubclass_": ("issubclass", "removed in NumPy 2.0"), "safe_eval": ("ast.literal_eval", "removed in NumPy 2.0"),
    "who": ("(none)", "removed in NumPy 2.0"), "source": ("inspect.getsource", "removed in NumPy 2.0"),
    "set_string_function": ("np.set_printoptions", "removed in NumPy 2.0"),
    "obj2sctype": ("(none)", "removed in NumPy 2.0"), "sctype2char": ("(none)", "removed in NumPy 2.0"),
    "maximum_sctype": ("(none)", "removed in NumPy 2.0"), "sctypes": ("(none)", "removed in NumPy 2.0"),
    "disp": ("print", "removed in NumPy 2.0"), "deprecate": ("warnings.warn", "removed in NumPy 2.0"),
    "fastCopyAndTranspose": ("a.T.copy()", "removed in NumPy 2.0"), "recfromcsv": ("np.genfromtxt", "removed in NumPy 2.0"),
    "recfromtxt": ("np.genfromtxt", "removed in NumPy 2.0"), "byte_bounds": ("(none)", "removed in NumPy 2.0"),
    **{k: ({"unicode": "str"}.get(k, k), "removed in NumPy 1.24")
       for k in ("int", "float", "object", "str", "complex", "unicode")},
}
# removed in NumPy 1.24 and added back in 2.0 with a new meaning, so they fail only on NumPy 1.24 to 1.26: a NOTE
_NUMPY_READDED = {"bool": "np.bool_ (np.bool is the NumPy boolean type again since NumPy 2.0)",
                  "long": "int or np.int_ (np.long is the C long type again since NumPy 2.0)"}
_NUMPY_DEPRECATED = {"trapz": "np.trapezoid", "in1d": "np.isin", "row_stack": "np.vstack"}
# module path -> name -> replacement (all removed)
_SCIPY = {
    "scipy.integrate": {"simps": "scipy.integrate.simpson", "trapz": "scipy.integrate.trapezoid",
                        "cumtrapz": "scipy.integrate.cumulative_trapezoid",
                        # SciPy 1.15 removed romberg and quadrature; romb (on samples) is still there
                        "romberg": "scipy.integrate.quad", "quadrature": "scipy.integrate.quad"},
    "scipy.misc": {"*": "scipy.datasets, scipy.special or numpy (scipy.misc was removed)"},
}
_SHIMMED = {"distutils"}  # still importable wherever setuptools is installed, so only a NOTE
_PY_REMOVED = {"imp": "importlib (removed in Python 3.12)", "distutils": "setuptools or sysconfig (removed from the standard library in Python 3.12; setuptools still provides it)",
               "asynchat": "asyncio (removed in Python 3.12)", "asyncore": "asyncio (removed in Python 3.12)",
               "smtpd": "aiosmtpd (removed in Python 3.12)"}


_STACKERS = {"stack", "vstack", "hstack", "dstack", "column_stack", "row_stack", "concatenate"}


def _src_text(node) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return ""


_DOWNLOADS = {"urlretrieve", "urlopen", "download", "download_file", "hf_hub_download"}


def _import_time_downloads(tree, rel) -> list[Finding]:
    """A download in the module body runs on import, so the module cannot be imported without a network
    (corpus repo L102 fetched binaries at import). Calls inside functions or a __main__ block are not reported."""
    out = []
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(stmt, ast.If) and "__main__" in ast.unparse(stmt.test):
            continue
        for n in ast.walk(stmt):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                break
            if isinstance(n, ast.Call):
                fn = n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
                via_requests = fn == "get" and isinstance(n.func, ast.Attribute) and getattr(n.func.value, "id", "") == "requests"
                if fn in _DOWNLOADS or via_requests:
                    out.append(Finding("api", NOTE, rel, n.lineno, f"{ast.unparse(n.func)}(...) runs when the module is"
                                                                   " imported, so importing it needs a network connection", rule="PV501"))
    return out


def scan_api(path: Path, tree, rel: str) -> list[Finding]:
    out = _import_time_downloads(tree, rel)
    np_names = _aliases(tree, "numpy")
    guarded = _guarded(tree)  # try: np.float_ except AttributeError: ... is a compatibility shim
    for n in all_nodes(tree):
        if id(n) in guarded:
            continue
        # np.NaN, numpy.float, ...
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in np_names:
            if n.attr in _NUMPY:
                new, when = _NUMPY[n.attr]
                out.append(Finding("api", WARN, rel, n.lineno, f"{n.value.id}.{n.attr} was {when}; use {new}", rule="PV502"))
            elif n.attr in _NUMPY_READDED:
                out.append(Finding("api", NOTE, rel, n.lineno, f"{n.value.id}.{n.attr} raises AttributeError on NumPy 1.24"
                                                                 f" to 1.26; for those versions use {_NUMPY_READDED[n.attr]}", rule="PV503"))
            elif n.attr in _NUMPY_DEPRECATED:
                out.append(Finding("api", NOTE, rel, n.lineno, f"{n.value.id}.{n.attr} is deprecated in NumPy 2;"
                                                                 f" use {_NUMPY_DEPRECATED[n.attr]}", rule="PV504"))
        # from numpy import NaN
        if isinstance(n, ast.ImportFrom) and n.module == "numpy":
            for a in n.names:
                if a.name in _NUMPY:
                    new, when = _NUMPY[a.name]
                    out.append(Finding("api", WARN, rel, n.lineno, f"numpy.{a.name} was {when}; use {new}", rule="PV502"))
        # np.array(x, copy=False)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "array" \
                and isinstance(n.func.value, ast.Name) and n.func.value.id in np_names:
            first = n.args[0] if n.args else None
            # a buffer (memoryview, an MPI shared buffer) needs no copy, so copy=False works there (corpus repo L209)
            buffer = first is not None and bool(re.search(r"buf|memoryview", _src_text(first), re.I))
            for k in n.keywords:
                if k.arg == "copy" and isinstance(k.value, ast.Constant) and k.value.value is False and not buffer:
                    out.append(Finding("api", WARN, rel, n.lineno, "np.array(..., copy=False) raises ValueError in NumPy 2"
                                                                   " whenever a copy is needed (a list, a number); use np.asarray", rule="PV505"))
        # np.vstack(x for x in ...): stacking functions need a sequence; a generator raises TypeError since NumPy 1.24
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in _STACKERS                 and isinstance(n.func.value, ast.Name) and n.func.value.id in np_names                 and n.args and isinstance(n.args[0], ast.GeneratorExp):
            out.append(Finding("api", WARN, rel, n.lineno, f"{n.func.value.id}.{n.func.attr} is given a generator, which"
                                                           " raises TypeError since NumPy 1.24; pass a list ([... for ...])", rule="PV506"))
        # jnp.clip(x, a_min=, a_max=): current JAX rejects these keywords (corpus repo L329 could not run on it)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "clip"                 and _src_text(n.func.value) in ("jnp", "jax.numpy")                 and any(k.arg in ("a_min", "a_max") for k in n.keywords):
            out.append(Finding("api", WARN, rel, n.lineno, f"{_src_text(n.func)}(..., a_min=, a_max=): current JAX raises"
                                                           " TypeError for these keywords; use min= and max=, or pass them by position", rule="PV507"))
        # scipy and Python modules that were removed
        if isinstance(n, ast.ImportFrom) and n.module:
            for mod, names in _SCIPY.items():
                if n.module == mod or n.module.startswith(mod + "."):
                    for a in n.names:
                        new = names.get(a.name, names.get("*", False))
                        if new is not False:
                            out.append(Finding("api", WARN, rel, n.lineno, f"{n.module}.{a.name} has been removed from SciPy"
                                                                           + (f"; use {new}" if new else ""), rule="PV508"))
            if n.module.split(".")[0] in _PY_REMOVED:
                top = n.module.split(".")[0]
                out.append(Finding("api", NOTE if top in _SHIMMED else WARN, rel, n.lineno, f"{n.module}: use {_PY_REMOVED[top]}", rule="PV509"))
        if isinstance(n, ast.Import):
            for a in n.names:
                top = a.name.split(".")[0]
                if top in _PY_REMOVED:
                    out.append(Finding("api", NOTE if top in _SHIMMED else WARN, rel, n.lineno,
                                       f"import {a.name}: use {_PY_REMOVED[top]}", rule="PV509"))
                if a.name == "scipy.misc":
                    out.append(Finding("api", WARN, rel, n.lineno, "scipy.misc has been removed from SciPy", rule="PV508"))
        if isinstance(n, ast.Attribute) and n.attr in _SCIPY["scipy.integrate"] and isinstance(n.value, ast.Attribute) \
                and n.value.attr == "integrate":
            out.append(Finding("api", WARN, rel, n.lineno, f"scipy.integrate.{n.attr} has been removed from SciPy;"
                                                           f" use {_SCIPY['scipy.integrate'][n.attr]}", rule="PV508"))
    return out
