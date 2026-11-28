"""Connect physverify to an AI coding assistant: a Claude Code hook and a minimal MCP server.

Both are thin layers over `physverify.report` (the same code as `physverify run`),
and the core works without them.

Hook (`physverify hook`)
    For Claude Code's PostToolUse event. It reads the event JSON on stdin. After
    an edit to a .py file it runs the project's specs, and when a check fails it
    prints a summary on stderr and exits 2, which Claude Code passes back to the
    assistant. Otherwise it exits 0 and prints nothing. See docs/agent.md.

MCP server (`physverify mcp`)
    Deprecated in 0.10.0 and planned for removal in 0.11.0 (DEPRECATION below).
    Model Context Protocol over stdio (newline-delimited JSON-RPC 2.0), with two
    tools: `run_checks`, that takes spec paths and returns the JSON report, and
    `confirm_claim`, that judges one claim file (docs/confirm.md). Both run the code
    in a fresh Python process with a time limit (physverify.isolate), so an edit to
    the solver between two calls is always seen. It is
    written with the standard library only, so it has no extra dependency; it
    implements the parts of the protocol a tool server needs, not the whole
    specification. It serves both protocol eras on the same process:
      - legacy (2025-11-25 and earlier): the client opens with `initialize`;
      - modern (2026-07-28): no handshake, every request carries its protocol
        version in `_meta`, and `server/discover` reports what the server supports.
    A request that carries the modern `_meta` version is served the modern way; an
    `initialize` request selects legacy behaviour.

Specs are found in this order: `[tool.physverify] specs = [...]` in the nearest
pyproject.toml, otherwise every verify_*.py under the project folder (skipping
hidden folders, virtual environments and build output). A pyproject.toml with
[[tool.physverify.ode]] tables is a spec too (physverify.declarative).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RUN_TIMEOUT = 600.0  # seconds for one run_checks call in its own process
SKIP_DIRS = {"venv", ".venv", "env", "node_modules", "build", "dist", "__pycache__", "site-packages"}
MAX_REPORTED = 10


def find_project_root(start: Path) -> Path:
    start = start.resolve()
    for folder in [start, *start.parents]:
        if (folder / "pyproject.toml").is_file() or (folder / ".git").exists():
            return folder
    return start


def find_specs(root: Path) -> list[Path]:
    root = Path(root)
    declared: list[Path] = []
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            from .declarative import read_config

            config = read_config(pyproject)
        except Exception:
            config = {}
        if config.get("ode"):
            declared = [pyproject.resolve()]
        if config.get("specs"):
            # Entries that leave the root are dropped (GCVE-110-VULN-PYPI-2026-000391).
            inside = root.resolve()
            return [p for p in ((root / s).resolve() for s in config["specs"]) if p.is_relative_to(inside)] + declared
    specs = []
    for path in sorted(root.rglob("verify_*.py")):
        parts = path.relative_to(root).parts[:-1]
        if any(p.startswith(".") or p in SKIP_DIRS for p in parts):
            continue
        specs.append(path)
    return specs + declared


def run_specs(specs) -> dict:
    """Run every spec; returns the JSON report as a dict, with load errors listed separately.

    Anything the code under test prints goes to stderr, so that it cannot corrupt
    the MCP stream on stdout.
    """
    import contextlib

    from .report import load_spec, run_checks, to_json

    outcomes, load_errors = [], []
    with contextlib.redirect_stdout(sys.stderr):
        for spec in specs:
            try:
                outcomes += run_checks(load_spec(spec))
            except Exception as exc:
                load_errors.append({"spec": str(spec), "error": f"{type(exc).__name__}: {exc}"})
    report = json.loads(to_json(outcomes, ", ".join(str(s) for s in specs)))
    report["load_errors"] = load_errors
    return report


def failure_summary(report: dict) -> str:
    failed = [c for c in report["checks"] if not c["ok"]]
    lines = [f"physverify: {len(failed)} of {report['summary']['total']} checks did not pass."]
    for c in failed[:MAX_REPORTED]:
        lines.append(f"- {c['status']} [{c['family']}] {c['label']}: {c['message']}")
    if len(failed) > MAX_REPORTED:
        lines.append(f"- ... and {len(failed) - MAX_REPORTED} more")
    for e in report["load_errors"]:
        lines.append(f"- could not load {e['spec']}: {e['error']}")
    lines.append("Run `physverify run <spec> --html report.html` for convergence plots.")
    return "\n".join(lines)


def hook_main(stdin=None, stderr=None) -> int:
    stdin = stdin or sys.stdin
    stderr = stderr or sys.stderr
    try:
        event = json.load(stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # not a hook event; never block the assistant on our own input problem
    if not isinstance(event, dict):
        return 0
    tool_input = event.get("tool_input")
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    edited = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not isinstance(edited, str) or (edited and not edited.endswith(".py")):
        return 0
    cwd = Path(event.get("cwd") or ".").resolve()
    edited_path = (cwd / edited).resolve() if edited else None  # a relative path is relative to the session folder
    if edited_path is not None and not edited_path.is_relative_to(cwd):
        return 0  # an edit outside the session folder must not run that folder's code (GCVE-110-VULN-PYPI-2026-000391)
    root = find_project_root(edited_path.parent if edited_path is not None else cwd)
    if not root.is_relative_to(cwd):
        root = cwd  # never climb above the session folder
    specs = find_specs(root)
    if not specs:
        return 0
    report = run_specs(specs)
    if report["summary"]["not_ok"] or report["load_errors"]:
        print(failure_summary(report), file=stderr)
        return 2
    return 0


# --- MCP server ---

MODERN_VERSION = "2026-07-28"
LEGACY_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")  # newest first

META_VERSION = "io.modelcontextprotocol/protocolVersion"
META_CAPABILITIES = "io.modelcontextprotocol/clientCapabilities"
META_SERVER_INFO = "io.modelcontextprotocol/serverInfo"

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
UNSUPPORTED_PROTOCOL_VERSION = -32022

DEPRECATION_ISSUE = "https://github.com/rcgiri-physics/physverify/issues/123"
DEPRECATION = (
    "physverify mcp is deprecated and planned for removal in physverify 0.11.0. "
    "Run the checks with `physverify run` or pytest instead (see AGENTS.md). "
    f"If you use this server, please say so at {DEPRECATION_ISSUE}"
)

CACHE_HINTS = {"ttlMs": 300_000, "cacheScope": "public"}  # the tool list does not change while the server runs
INSTRUCTIONS = DEPRECATION + " " + (
    "Run physverify checks on physics simulation code after writing or editing it. "
    "The tools execute the project's verify_*.py spec files and claim files (Python), so use them only on projects you trust."
)

TOOLS = [
    {
        "name": "run_checks",
        "description": (
            "Run physverify verification checks (manufactured solutions, order of convergence, "
            "invariants, limits, exactness) on physics simulation code. Takes spec files that "
            "define checks(); with no specs given, finds verify_*.py files under `project`. "
            "Returns a JSON report: per check family, label, status (PASS, EXACT, FAIL, "
            "INCONCLUSIVE, ERROR, SKIP), message, observed and expected order, step sizes and errors."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "specs": {"type": "array", "items": {"type": "string"}, "description": "spec file paths"},
                "project": {"type": "string", "description": "project folder to search for verify_*.py"},
                "timeout": {"type": "number", "description": f"seconds for the whole run (default {RUN_TIMEOUT:g})"},
            },
        },
    },
    {
        "name": "confirm_claim",
        "description": (
            "Judge one suspected defect with physverify confirm. Takes a claim file that defines CLAIM, "
            "control() and checks() with a reference written from the physics (docs/confirm.md), runs it "
            "in a fresh process and returns the verdict: confirmed, rejected or not decidable, with the "
            "reason and each check's status and message. Appends the result to a ledger file. Runs the "
            "code, so it needs trusted=true or the sandbox (PHYSVERIFY_REPO set)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "claim": {"type": "string", "description": "path of the claim file"},
                "trusted": {"type": "boolean", "description": "the code under test is trusted (required outside the sandbox)"},
                "ledger": {"type": "string", "description": "ledger file (default confirm_ledger.jsonl)"},
                "timeout": {"type": "number", "description": "seconds for the whole run (default 300)"},
                "allow_dependent_reference": {"type": "string", "description": "reason, recorded, to run although the reference seems to use the code under test"},
            },
            "required": ["claim"],
        },
    },
]
for _tool in TOOLS:
    _tool["description"] = "Deprecated: " + DEPRECATION + " " + _tool["description"]


def _error(msg_id, code: int, message: str, data=None) -> dict:
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": msg_id, "error": error}


def _run_checks_tool(arguments: dict) -> dict:
    """The tools/call result body (content and isError), identical in both protocol eras."""
    specs = [Path(s) for s in arguments.get("specs") or []]
    if not specs:
        specs = find_specs(Path(arguments.get("project") or "."))
    if not specs:
        return {"content": [{"type": "text", "text": "No spec files found (verify_*.py defining checks())."}], "isError": True}
    from .confirm import parse_timeout

    try:
        timeout = parse_timeout(RUN_TIMEOUT if arguments.get("timeout") is None else arguments["timeout"])
    except ValueError as exc:
        return {"content": [{"type": "text", "text": f"run_checks: {exc}"}], "isError": True}
    report = run_specs_isolated(specs, timeout)
    failed = bool(report["summary"]["not_ok"] or report["load_errors"])
    s = report["summary"]
    warn = ""
    if not report["load_errors"] and s["total"] == s.get("skipped", 0):
        # isError stays False (the tool call itself worked), so say it in the text a reader sees first
        warn = (f"WARNING: no check was executed ({s['total']} defined, {s.get('skipped', 0)} skipped);"
                " nothing was verified.\n\n")
    text = warn + (failure_summary(report) + "\n\n" if failed else "") + json.dumps(report, indent=2)
    return {"content": [{"type": "text", "text": text}], "isError": False}


def run_specs_isolated(specs, timeout: float | None = RUN_TIMEOUT) -> dict:
    """run_specs in a fresh Python process (physverify.isolate): the solver is imported as it is on disk now,
    and a run longer than `timeout` seconds is stopped and reported as a load error of every spec."""
    from .isolate import run_isolated
    from .report import to_json

    specs = [Path(s).resolve() for s in specs]
    run = run_isolated("specs", specs, timeout)
    if run["status"] == "done":
        return run["result"]
    why = (f"timed out after {timeout:g} s; the run was stopped" if run["status"] == "timeout" else run["error"])
    if run["stderr_tail"]:
        why += "; last output: " + run["stderr_tail"][-500:]
    report = json.loads(to_json([], ", ".join(str(s) for s in specs)))
    report["load_errors"] = [{"spec": str(s), "error": why} for s in specs]
    return report


def _confirm_claim_tool(arguments: dict) -> dict:
    """confirm_claim: the same runner and verdict rules as `physverify confirm`."""
    from .confirm import (
        DEFAULT_LEDGER,
        DEFAULT_TIMEOUT,
        Refused,
        confirm_claim,
        format_verdict,
        parse_timeout,
    )

    claim = arguments.get("claim")
    if not isinstance(claim, str) or not claim:
        return {"content": [{"type": "text", "text": "confirm_claim needs `claim`, the path of a claim file."}], "isError": True}
    try:
        timeout = parse_timeout(DEFAULT_TIMEOUT if arguments.get("timeout") is None else arguments["timeout"])
    except ValueError as exc:
        return {"content": [{"type": "text", "text": f"confirm_claim: {exc}"}], "isError": True}
    try:
        record = confirm_claim(claim, trusted=arguments.get("trusted") is True,
                               ledger=arguments.get("ledger") or DEFAULT_LEDGER,
                               timeout=timeout,
                               allow_dependent_reference=arguments.get("allow_dependent_reference") or None)
    except Refused as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "isError": True}
    return {"content": [{"type": "text", "text": format_verdict(record) + "\n\n" + json.dumps(record, indent=2)}],
            "isError": False}


TOOL_HANDLERS = {"run_checks": _run_checks_tool, "confirm_claim": _confirm_claim_tool}


def handle(message: dict):
    """Answer one JSON-RPC message; returns the response dict, or None for a notification."""
    from . import __version__

    method = message.get("method")
    msg_id = message.get("id")
    if msg_id is None:
        return None  # notifications (initialized, cancelled, ...) need no answer
    params = message.get("params") or {}
    meta = params.get("_meta") if isinstance(params.get("_meta"), dict) else {}
    server_info = {"name": "physverify", "version": __version__}

    def ok(result):
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    # Legacy era: the handshake. `initialize` always selects legacy behaviour.
    if method == "initialize":
        requested = params.get("protocolVersion")
        version = requested if requested in LEGACY_VERSIONS else LEGACY_VERSIONS[0]
        return ok({"protocolVersion": version, "capabilities": {"tools": {}}, "serverInfo": server_info,
                   "instructions": INSTRUCTIONS})

    # Modern era: no handshake; the request itself says which version it speaks.
    # `server/discover` exists only in this era, so it is always treated as modern.
    if META_VERSION in meta or method == "server/discover":
        requested = meta.get(META_VERSION)
        if requested is None or META_CAPABILITIES not in meta:
            return _error(msg_id, INVALID_PARAMS, f"missing required _meta field: {META_VERSION!r} and {META_CAPABILITIES!r} are required on every request")
        if requested != MODERN_VERSION:
            return _error(msg_id, UNSUPPORTED_PROTOCOL_VERSION, "Unsupported protocol version", {"supported": [MODERN_VERSION], "requested": requested})

        def modern(result, cacheable=False):
            body = {"resultType": "complete", **result, "_meta": {META_SERVER_INFO: server_info}}
            if cacheable:
                body.update(CACHE_HINTS)
            return ok(body)

        if method == "server/discover":
            return modern({"supportedVersions": [MODERN_VERSION], "capabilities": {"tools": {}}, "instructions": INSTRUCTIONS}, cacheable=True)
        if method == "ping":
            return modern({})
        if method == "tools/list":
            return modern({"tools": TOOLS}, cacheable=True)
        if method == "tools/call":
            tool = TOOL_HANDLERS.get(params.get("name"))
            if tool is None:
                return _error(msg_id, INVALID_PARAMS, f"unknown tool {params.get('name')!r}")
            return modern(tool(params.get("arguments") or {}))
        return _error(msg_id, METHOD_NOT_FOUND, f"method not found: {method}")

    # Legacy era, after the handshake: results carry no resultType or cache hints.
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        tool = TOOL_HANDLERS.get(params.get("name"))
        if tool is None:
            return _error(msg_id, INVALID_PARAMS, f"unknown tool {params.get('name')!r}")
        return ok(tool(params.get("arguments") or {}))
    return _error(msg_id, METHOD_NOT_FOUND, f"method not found: {method}")


def _respond(message):
    """handle(), but a message that is not an object, or an exception, becomes an error response; the server keeps running."""
    if not isinstance(message, dict):  # a batch, a number, a string: not a request this server answers
        return _error(None, INVALID_REQUEST, "invalid request: expected a JSON object")
    try:
        return handle(message)
    except Exception as exc:  # report the failure to the client
        return _error(message.get("id"), INTERNAL_ERROR, f"{type(exc).__name__}: {exc}")


def mcp_main(stdin=None, stdout=None) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    print(f"warning: {DEPRECATION}", file=sys.stderr, flush=True)  # stdout carries the protocol
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            response = _error(None, PARSE_ERROR, "parse error")
        else:
            response = _respond(message)
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()
    return 0
