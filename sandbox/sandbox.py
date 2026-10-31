"""Run untrusted repositories inside the locked-down container.

    python -I sandbox/sandbox.py build [--stack latest]                 # --stack latest: newest NumPy/SciPy, tag :latest-stack
    python -I sandbox/sandbox.py fetch  <id> <git-url> <commit>   # clone on the host, no hooks, no checkout of LFS
    python -I sandbox/sandbox.py deps   [--clean] <id> [package ...]  # optional: wheels-only install, network on;
                                                                 # --clean empties deps/<id> first
    python -I sandbox/sandbox.py run    [--read-only-repo] [--py314-shim] <id> <script> [args ...]  # network off

Folders (under %LOCALAPPDATA%/physverify-corpus or $PHYSVERIFY_CORPUS):
    repos/<id>   the clone, mounted read-only at /repo-src and copied to /tmp/repo (writable, $PHYSVERIFY_REPO)
                 for the run; files the code writes there are reported as a portability note.
                 --read-only-repo runs from the read-only mount at /repo instead (no copy)
    deps/<id>    extra packages, mounted read-only at /deps during run
    out/<id>     the only writable mount, at /out
The folder holding the script given to `run` is mounted read-only at /work; it is ours (adapters), never the repo's.
--py314-shim adds `from __future__ import annotations` to every file of the copy, for code written for
Python 3.14's lazy annotations (the image has an older Python); it needs the copy.
A missing version file that setuptools-scm or hatch-vcs would generate from git (pkg/_version.py) is written
as a placeholder in the copy, and reported; set PHYSVERIFY_NO_VERSION_STUB=1 to turn that off.

PHYSVERIFY_IMAGE=physverify-sandbox:latest-stack selects the newer-stack image for deps and run. Its
packages go to deps-latest-stack/<id>, so wheels built against two NumPy versions never share a folder.
"""

import os
import re
import subprocess
import sys
import threading
from pathlib import Path

DEFAULT_IMAGE = "physverify-sandbox:1"
LATEST_IMAGE = "physverify-sandbox:latest-stack"
IMAGE = os.environ.get("PHYSVERIFY_IMAGE", DEFAULT_IMAGE)
ROOT = Path(__file__).resolve().parents[1]
CORPUS = Path(os.environ.get("PHYSVERIFY_CORPUS") or Path(os.environ.get("LOCALAPPDATA", Path.home())) / "physverify-corpus")
TIME_LIMIT = int(os.environ.get("PHYSVERIFY_TIME_LIMIT", "900"))  # seconds per run
DEPS_TIME_LIMIT = int(os.environ.get("PHYSVERIFY_DEPS_TIME_LIMIT", "2400"))  # seconds per install (JAX, Qiskit on a slow link)

LOCKDOWN = [
    "--rm",
    "--read-only",
    "--cap-drop=ALL",
    "--security-opt=no-new-privileges",
    "--pids-limit=256",
    "--memory=2g",
    "--memory-swap=2g",
    "--cpus=2",
    "--ulimit=nofile=1024:1024",
    "--ulimit=fsize=1073741824",  # no file over 1 GB
    "--tmpfs=/tmp:rw,nosuid,nodev,size=512m",
    "--user=10001:10001",
    "--env=OMP_NUM_THREADS=2",
]


def folder(kind, repo_id):
    if kind == "deps" and IMAGE != DEFAULT_IMAGE:
        kind = "deps-" + IMAGE.rsplit(":", 1)[-1]
    path = CORPUS / kind / repo_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def docker(args, timeout=None):
    print("+ docker " + " ".join(args), flush=True)
    return subprocess.run(["docker", *args], timeout=timeout).returncode


def remove_stale(name):
    """Remove a container left over from an earlier step with the same name.

    A step killed by the host-side time limit can leave its container running; a later install
    into the same deps folder then races it and leaves a half-installed folder.
    """
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)


def timed(args, name, limit, keep=None):
    """Run docker with a time limit. With a list `keep`, the output is shown as it comes and also kept there."""
    if keep is None:
        try:
            return oom_note(docker(args, timeout=limit))
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "kill", name], capture_output=True)
            print(f"killed after {limit} s")
            return 124
    print("+ docker " + " ".join(args), flush=True)
    proc = subprocess.Popen(["docker", *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace")
    timer = threading.Timer(limit, lambda: subprocess.run(["docker", "kill", name], capture_output=True))
    timer.start()
    try:
        for line in proc.stdout:
            print(line, end="", flush=True)
            keep.append(line)
        rc = proc.wait()
    finally:
        expired = not timer.is_alive()
        timer.cancel()
    if expired and rc != 0:
        print(f"killed after {limit} s")
        return 124
    return oom_note(rc)


def oom_note(rc):
    """Exit code 137 is SIGKILL; with no time limit reached it is almost always the 2 GB memory limit, and
    the container then dies with no message of its own."""
    if rc == 137:
        print("physverify sandbox: the run was killed (exit 137), most likely by the 2 GB memory limit;"
              " use smaller grids or fewer stored frames")
    return rc


STACK_CONFLICT = re.compile(r"depends on (numpy|scipy)\s*([^\r\n]+)", re.IGNORECASE)


def stack_hint(output: str) -> str:
    """A suggestion when pip failed because a package needs other NumPy/SciPy versions than the image pins."""
    found = sorted({m.group(1).lower() + " " + " and ".join(p.strip() for p in m.group(2).split(" and "))
                    for m in STACK_CONFLICT.finditer(output)})
    if not found or "ResolutionImpossible" not in output and "conflict" not in output.lower():
        return ""
    if IMAGE == DEFAULT_IMAGE:
        return (f"a dependency needs {', '.join(found)}, which the pinned image cannot provide. Build the newer stack with"
                f" `python -I sandbox/sandbox.py build --stack latest` and rerun with PHYSVERIFY_IMAGE={LATEST_IMAGE}")
    return f"a dependency needs {', '.join(found)}, which this image ({IMAGE}) does not have either"


def build(stack=None):
    if stack == "latest":
        args = ["--build-arg", "STACK=numpy scipy sympy matplotlib pytest"]
        tag = LATEST_IMAGE
    elif stack is None:
        args, tag = [], DEFAULT_IMAGE
    else:
        sys.exit(f"unknown stack {stack!r}; use --stack latest")
    rc = docker(["build", "-t", tag, *args, "-f", str(ROOT / "sandbox" / "Dockerfile"), str(ROOT)])
    if rc == 0 and stack:
        subprocess.run(["docker", "run", "--rm", tag, "pip", "freeze", "--exclude", "physverify"])
        print(f"built {tag}; select it with PHYSVERIFY_IMAGE={tag}")
    return rc


def fetch(repo_id, url, commit):
    dest = CORPUS / "repos" / repo_id
    if dest.exists():
        sys.exit(f"{dest} exists; delete it first")
    safe = ["-c", "core.hooksPath=/dev/null", "-c", "core.symlinks=false", "-c", "filter.lfs.smudge=", "-c", "filter.lfs.process=",
            "-c", "filter.lfs.clean=", "-c", "filter.lfs.required=false"]  # LFS files stay as small pointer files
    env = dict(os.environ, GIT_LFS_SKIP_SMUDGE="1", GIT_TERMINAL_PROMPT="0")
    subprocess.run(["git", *safe, "clone", "--config", "core.autocrlf=false", "--no-checkout", "--filter=blob:limit=20m", url, str(dest)], check=True, env=env)
    subprocess.run(["git", *safe, "-C", str(dest), "checkout", "--detach", commit], check=True, env=env)
    return 0


def deps(repo_id, packages=(), clean=False):
    """Install the repo's requirements.txt, or the named packages, into deps/<id>, wheels only, so no setup.py runs.

    The image's own packages are passed as constraints: a dependency that needs a different NumPy fails here
    instead of silently shadowing the image's version during `run`.
    """
    req = CORPUS / "repos" / repo_id / "requirements.txt"
    if packages:
        mounts, what = [], list(packages)
    elif req.exists():
        mounts, what = ["-v", f"{req}:/req.txt:ro"], ["-r", "/req.txt"]
    else:
        print("no requirements.txt and no packages named; nothing to install")
        return 0
    name = f"pv-deps-{repo_id}"
    if clean:
        # pip --target leaves files of an earlier version in place, so a downgrade does not take
        import shutil
        shutil.rmtree(folder("deps", repo_id))
        print(f"removed the old {folder('deps', repo_id)}")
    # pip unpacks wheels in /tmp: give this step more room than a run gets
    lockdown = [a if not a.startswith("--tmpfs=/tmp") else "--tmpfs=/tmp:rw,nosuid,nodev,size=4g" for a in LOCKDOWN]
    # one wheel cache for all repos, so a large package (JAX: 10 minutes) is downloaded once; it holds only
    # wheels from PyPI, and it is mounted in this install step only, never during `run`
    cache = CORPUS / "pip-cache"
    cache.mkdir(parents=True, exist_ok=True)
    remove_stale(name)
    out: list = []
    rc = timed(["run", *lockdown, "--name", name, *mounts, "-v", f"{folder('deps', repo_id)}:/deps:rw",
                "-v", f"{cache}:/pip-cache:rw", "-e", "PIP_CACHE_DIR=/pip-cache",
                IMAGE, "pip", "install", "--progress-bar=off", "--only-binary=:all:", "--target=/deps",
                "--constraint=/opt/constraints.txt", *what],
               name, DEPS_TIME_LIMIT, keep=out)
    hint = stack_hint("".join(out)) if rc else ""
    if hint:
        print(f"physverify sandbox: {hint}")
    return rc


def head(repo):
    out = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True)
    return out.stdout.strip() or "unknown"


def host_path(p):
    """A path as Windows Docker needs it: Git-Bash style /c/Users/... becomes C:/Users/..."""
    p = str(p)
    if os.name == "nt" and len(p) > 2 and p[0] == "/" and p[2] == "/" and p[1].isalpha():
        p = f"{p[1].upper()}:{p[2:]}"
    return Path(p).resolve()


def run(repo_id, script, extra, *, read_only_repo=False, py314_shim=False):
    script = host_path(script)
    if not script.is_file():
        sys.exit(f"no adapter script at {script}")
    repo = CORPUS / "repos" / repo_id
    if not repo.is_dir():
        sys.exit(f"no clone at {repo}; run fetch first")
    name = f"pv-run-{repo_id}"
    remove_stale(name)
    deps_dir = folder("deps", repo_id)
    # wheels that bundle their own OpenMP runtime (qiskit-aer) fail to load it late ("cannot allocate
    # memory in static TLS block"); preloading it at start-up is the usual fix
    gomp = sorted(deps_dir.glob("*.libs/libgomp*.so*"))
    preload = ["-e", f"LD_PRELOAD=/deps/{gomp[0].relative_to(deps_dir).as_posix()}"] if gomp else []
    if py314_shim and read_only_repo:
        sys.exit("--py314-shim edits the copy, so it cannot be used with --read-only-repo")
    if read_only_repo:
        repo_mount, start = ["-v", f"{repo}:/repo:ro", "-e", "PHYSVERIFY_REPO=/repo"], ["python"]
    else:
        repo_mount = ["-v", f"{repo}:/repo-src:ro", "-v", f"{Path(__file__).resolve().parent}:/pv:ro",
                      "-e", "PHYSVERIFY_REPO_SRC=/repo-src", "-e", "PHYSVERIFY_REPO=/tmp/repo",
                      *(["-e", "PHYSVERIFY_PY314_SHIM=1"] if py314_shim else [])]
        start = ["python", "/pv/runner.py"]
    args = ["run", *LOCKDOWN, "--network=none", "--name", name, *preload, *repo_mount,
            "-v", f"{deps_dir}:/deps:ro",
            "-v", f"{script.parent}:/work:ro", "-v", f"{folder('out', repo_id)}:/out:rw",
            *[a for k in os.environ.get("PHYSVERIFY_PASS_ENV", "").split(",") if k for a in ("-e", f"{k}={os.environ[k]}")], "-e", f"PHYSVERIFY_REPO_COMMIT={head(repo)}", IMAGE, *start, f"/work/{script.name}", *extra]
    return timed(args, name, TIME_LIMIT)


def main(argv):
    # pip and the repo code print UTF-8 (progress bars, Greek letters); a Windows console in cp1252 would raise
    # UnicodeEncodeError on print, so unknown characters are replaced instead
    sys.stdout.reconfigure(errors="replace")
    if not argv:
        sys.exit(__doc__)
    cmd, rest = argv[0], argv[1:]
    if cmd == "build":
        if rest[:1] == ["--stack"] and len(rest) == 2:
            return build(rest[1])
        if not rest:
            return build()
    if cmd == "fetch" and len(rest) == 3:
        return fetch(*rest)
    if cmd == "deps" and rest[:1] == ["--clean"] and len(rest) >= 2:
        return deps(rest[1], rest[2:], clean=True)
    if cmd == "deps" and len(rest) >= 1:
        return deps(rest[0], rest[1:])
    if cmd == "run":
        flags = {"--read-only-repo": "read_only_repo", "--py314-shim": "py314_shim"}
        opts = {}
        while rest and rest[0] in flags:
            opts[flags[rest.pop(0)]] = True
        if len(rest) >= 2:
            return run(rest[0], rest[1], rest[2:], **opts)
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
