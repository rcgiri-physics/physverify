"""Start-up inside the sandbox container: copy the repository to a writable place, optionally apply the
Python 3.14 shim, run the adapter, then report files the code wrote into its own directory.

    python /pv/runner.py <adapter.py> [args ...]

Environment: PHYSVERIFY_REPO_SRC (read-only clone, default /repo-src), PHYSVERIFY_REPO (the writable copy,
default /tmp/repo), PHYSVERIFY_PY314_SHIM=1 to apply the shim. Standard library only.

Some repositories write next to their own source (a cache in the package folder, an output folder
that must already exist), which fails from a read-only install. Running from a copy lets the checks
go ahead, and the note at the end records it as a portability issue rather than hiding it.
"""

import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path

FUTURE = "from __future__ import annotations\n"


def snapshot(root: Path) -> dict:
    out = {}
    for p in root.rglob("*"):
        if p.is_file() and not p.is_symlink():
            st = p.stat()
            out[p.relative_to(root).as_posix()] = (st.st_size, st.st_mtime_ns)
    return out


def written(before: dict, after: dict) -> list:
    """Files created or changed between two snapshots."""
    return sorted(k for k, v in after.items() if before.get(k) != v)


def py314_shim(source: str) -> str | None:
    """Source with `from __future__ import annotations` as its first statement, or None when not needed
    or not possible (already there, or the file does not parse on this Python).

    Python 3.14 evaluates annotations lazily, so code written for it may annotate with names defined
    later in the file; on 3.10-3.13 that fails at import unless annotations are postponed.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__" and any(a.name == "annotations" for a in node.names):
            return None
    lines = source.splitlines(keepends=True)
    body = tree.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        at = body[0].end_lineno  # after the module docstring
    else:
        at = 0
        while at < min(2, len(lines)) and lines[at].startswith("#"):  # shebang and coding lines stay first
            at += 1
    if at and at <= len(lines) and not lines[at - 1].endswith("\n"):
        lines[at - 1] += "\n"
    return "".join(lines[:at]) + FUTURE + "".join(lines[at:])


def apply_shim(root: Path) -> int:
    n = 0
    for p in root.rglob("*.py"):
        try:
            new = py314_shim(p.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, OSError):
            continue
        if new is not None:
            p.write_text(new, encoding="utf-8")
            n += 1
    return n


STUB = '__version__ = version = "0+unknown"\n__version_tuple__ = version_tuple = (0, 0, "unknown")\n'


def version_files(root: Path) -> list:
    """Version files a build backend would generate from git (setuptools-scm, hatch-vcs), as paths in root.

    A source checkout has none of them, so `import pkg` fails with ModuleNotFoundError for pkg._version
    before any physics runs. Read from pyproject.toml (tool.setuptools_scm version_file / write_to,
    tool.hatch.build.hooks.vcs version-file) and from setup.py (use_scm_version={"write_to": ...}).
    """
    import re
    found = []
    pp = root / "pyproject.toml"
    if pp.is_file():
        text = pp.read_text(encoding="utf-8", errors="replace")
        try:
            import tomllib
            data = tomllib.loads(text)
        except ModuleNotFoundError:  # Python 3.10: read the three keys directly
            data = {}
            found += re.findall(r"""^\s*(?:version_file|write_to|version-file)\s*=\s*["']([^"']+)["']""", text, re.M)
        except Exception:  # noqa: BLE001 - an unreadable pyproject just gives no stub
            data = {}
        tool = data.get("tool", {})
        scm = tool.get("setuptools_scm", {})
        found += [scm[k] for k in ("version_file", "write_to") if isinstance(scm.get(k), str)]
        hatch = tool.get("hatch", {}).get("build", {})
        for hooks in (hatch.get("hooks", {}), hatch.get("targets", {}).get("wheel", {}).get("hooks", {})):
            vf = hooks.get("vcs", {}).get("version-file")
            if isinstance(vf, str):
                found.append(vf)
    sp = root / "setup.py"
    if sp.is_file():
        try:
            text = sp.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            text = ""
        found += re.findall(r"""["'](?:write_to|version_file)["']\s*:\s*["']([^"']+\.py)["']""", text)
        found += re.findall(r"""(?:write_to|version_file)\s*=\s*["']([^"']+\.py)["']""", text)
    out = []
    for rel in dict.fromkeys(found):
        p = (root / rel).resolve()
        if p.suffix == ".py" and root.resolve() in p.parents:
            out.append(p)
    return out


def add_version_stubs(root: Path) -> list:
    """Write a placeholder version file for each generated one that is missing; return the ones written."""
    written_ = []
    for p in version_files(root):
        if not p.exists() and p.parent.is_dir():
            p.write_text(STUB, encoding="utf-8")
            written_.append(p.relative_to(root.resolve()).as_posix())
    return written_


def dist_names(root: Path) -> list:
    """The repository's own distribution names, from pyproject.toml, setup.cfg and setup.py."""
    import re
    names = []
    for f, pat in (("pyproject.toml", r"""^\s*name\s*=\s*["']([^"']+)["']"""), ("setup.cfg", r"^\s*name\s*=\s*(\S+)"),
                   ("setup.py", r"""\bname\s*=\s*["']([^"']+)["']""")):
        p = root / f
        if p.is_file():
            m = re.search(pat, p.read_text(encoding="utf-8", errors="replace"), re.M)
            if m:
                names.append(m.group(1))
    return list(dict.fromkeys(names))


SITE = """import importlib.metadata as _md, os
_own = {n.lower().replace("_", "-") for n in os.environ.get("PHYSVERIFY_SOURCE_DISTS", "").split(",") if n}
_version = _md.version
def version(name):
    try:
        return _version(name)
    except _md.PackageNotFoundError:
        if name.lower().replace("_", "-") in _own:
            return "0+source"
        raise
_md.version = version
"""


def metadata_shim(root: Path) -> list:
    """A source checkout is not installed, so `importlib.metadata.version("pkg")` in pkg/__init__.py raises
    PackageNotFoundError before any physics runs (corpus repos L171, L173, L225). A sitecustomize on the path
    answers "0+source" for the repository's own distribution names only, and only when it is not installed."""
    names = dist_names(root)
    if not names:
        return []
    site = Path("/tmp/pv-site")
    site.mkdir(exist_ok=True)
    (site / "sitecustomize.py").write_text(SITE, encoding="utf-8")
    os.environ["PYTHONPATH"] = os.pathsep.join(p for p in (str(site), os.environ.get("PYTHONPATH", "")) if p)
    os.environ["PHYSVERIFY_SOURCE_DISTS"] = ",".join(names)
    return names


def main(argv) -> int:
    src = Path(os.environ.get("PHYSVERIFY_REPO_SRC", "/repo-src"))
    dst = Path(os.environ.get("PHYSVERIFY_REPO", "/tmp/repo"))
    shutil.copytree(src, dst, symlinks=True, ignore=shutil.ignore_patterns(".git"), dirs_exist_ok=True)
    if os.environ.get("PHYSVERIFY_PY314_SHIM") == "1":
        print(f"physverify sandbox: Python 3.14 shim added postponed annotations to {apply_shim(dst)} files", file=sys.stderr)
    if os.environ.get("PHYSVERIFY_NO_VERSION_STUB") != "1":
        stubs = add_version_stubs(dst)
        if stubs:
            print(f"physverify sandbox: wrote placeholder version file{'s' if len(stubs) > 1 else ''} {', '.join(stubs)} "
                  "(generated from git at build time, absent from a source checkout)", file=sys.stderr)
    if os.environ.get("PHYSVERIFY_NO_METADATA_SHIM") != "1":
        shimmed = metadata_shim(dst)
        if shimmed:
            print(f"physverify sandbox: importlib.metadata.version answers 0+source for {', '.join(shimmed)} "
                  "when not installed (a source checkout)", file=sys.stderr)
    before = snapshot(dst)
    rc = subprocess.call([sys.executable, *argv], env={**os.environ, "PHYSVERIFY_REPO": str(dst)})
    changed = written(before, snapshot(dst))
    if changed:
        shown = ", ".join(changed[:5]) + (f" and {len(changed) - 5} more" if len(changed) > 5 else "")
        print(f"physverify sandbox: portability note: the code wrote {len(changed)} file{'s' if len(changed) != 1 else ''} into its own directory "
              f"({shown}); it would fail from a read-only install", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
