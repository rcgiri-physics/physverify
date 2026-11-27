"""Run physverify work in a fresh Python process with a time limit.

A new interpreter imports the code under test as it is on disk now, so an edit between two runs is always
seen (a long-running process such as the MCP server keeps its first import), and a run that hangs can be
killed. Used by `physverify confirm` and by the MCP tools. The child sends everything the code under test
prints to stderr and writes its result as JSON after a marker line on stdout.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
from pathlib import Path

MARKER = "@@physverify-result@@"
TAIL = 2000  # characters of the child's stderr kept for a report
_CHILD = "import sys; from physverify.isolate import child_main; sys.exit(child_main(sys.argv[1:]))"


def _text(data) -> str:
    if data is None:
        return ""
    return data.decode("utf-8", "replace") if isinstance(data, bytes) else data


def _tail(data) -> str:
    return _text(data)[-TAIL:]


def run_isolated(mode: str, args, timeout: float | None, cwd=None) -> dict:
    """Run `mode` ("claim" or "specs") on `args` in a new Python process, killed after `timeout` seconds.

    Returns {"status": "done", "result": ..., "stderr_tail": ...}, {"status": "timeout", "stderr_tail": ...}
    or {"status": "error", "error": ..., "stderr_tail": ...} when the child ended without a result.
    """
    # no .pyc written: a same-size edit within a second could otherwise load stale bytecode in the next run
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    src = Path(__file__).resolve().parents[1]  # the physverify the parent uses, also for the child
    if src.name not in ("site-packages", "dist-packages"):  # an installed copy is found anyway; never put
        # site-packages ahead of the standard library
        env["PYTHONPATH"] = str(src) + os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else str(src)
    cmd = [sys.executable, "-c", _CHILD, mode, *[str(a) for a in args]]
    # its own process group (POSIX) so that a timeout can stop the processes the code under test started too
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, env=env,
                            cwd=cwd, start_new_session=(os.name != "nt"))
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            _, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:  # a process outside the tree still holds the pipes
            stderr = b""
        return {"status": "timeout", "stderr_tail": _tail(stderr)}
    except BaseException:  # Ctrl-C no longer reaches a child in its own session, so stop the tree here
        _kill_tree(proc)
        raise
    out = _text(stdout)
    i = out.rfind(MARKER)
    if i < 0:
        return {"status": "error", "error": f"the child process exited with code {proc.returncode} without a result",
                "stderr_tail": _tail(stderr)}
    try:  # read the first JSON value only: the code under test may print more at exit (atexit, a C library)
        result, _ = json.JSONDecoder().raw_decode(out[i + len(MARKER):])
    except json.JSONDecodeError as exc:
        return {"status": "error", "error": f"the child's result is not valid JSON ({exc})", "stderr_tail": _tail(stderr)}
    return {"status": "done", "result": result, "stderr_tail": _tail(stderr)}


def _kill_tree(proc) -> None:
    """Stop the child and every process it started (a process that detached itself on purpose can escape)."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=30,
                           stdin=subprocess.DEVNULL)
        else:
            import signal

            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        proc.kill()
    except OSError:
        pass


def child_main(argv) -> int:
    """Entry point of the child process: run one mode and write its JSON result after MARKER on stdout."""
    mode, rest = argv[0], list(argv[1:])
    real_stdout = sys.stdout
    with contextlib.redirect_stdout(sys.stderr):  # the code under test must not corrupt the result
        if mode == "claim":
            from .confirm import evaluate_claim

            result = evaluate_claim(rest[0])
        elif mode == "specs":
            from .agent import run_specs

            result = run_specs([Path(s) for s in rest])
        elif mode == "specs_lines":  # the first argument is a file whose executed lines are recorded too
            result = _run_tracing_lines(Path(rest[0]), [Path(s) for s in rest[1:]])
        else:
            print(f"physverify.isolate: unknown mode {mode!r}", file=sys.stderr)
            return 2
    real_stdout.write("\n" + MARKER + json.dumps(result) + "\n")
    real_stdout.flush()
    return 0


def _run_tracing_lines(target: Path, specs) -> dict:
    """run_specs, also recording which lines of `target` ran (for physverify mutate)."""
    import threading

    from .agent import run_specs

    want = os.path.normcase(str(target.resolve()))
    lines: set[int] = set()

    def tracer(frame, event, arg):
        if os.path.normcase(os.path.abspath(frame.f_code.co_filename)) != want:
            return None
        if event in ("call", "line"):
            lines.add(frame.f_lineno)
        return tracer

    sys.settrace(tracer)
    threading.settrace(tracer)
    try:
        result = run_specs(specs)
    finally:
        sys.settrace(None)
        threading.settrace(None)  # type: ignore[arg-type]
    result["target_lines"] = sorted(lines)
    return result
