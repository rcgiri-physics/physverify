"""The assistant hook and the MCP server: a seeded bug in a solver is reported back."""

import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from physverify.agent import find_specs, handle, hook_main, mcp_main

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


@pytest.fixture
def project(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n")
    for name in ("damped_oscillator.py", "verify_damped_oscillator.py"):
        shutil.copy(EXAMPLES / name, tmp_path / name)
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "verify_ignored.py").write_text("raise SystemExit('must not be imported')\n")
    yield tmp_path
    sys.modules.pop("damped_oscillator", None)
    while str(tmp_path) in sys.path:
        sys.path.remove(str(tmp_path))


def seed_bug(project):
    path = project / "damped_oscillator.py"
    path.write_text(path.read_text().replace("damping = 2.0 * GAMMA", "damping = 2.0 * GAMMA * 1.1"))


def event(project, file_name="damped_oscillator.py"):
    return io.StringIO(json.dumps({
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "cwd": str(project),
        "tool_input": {"file_path": str(project / file_name)},
    }))


def test_find_specs_skips_virtual_environments_and_honours_pyproject(project):
    assert [p.name for p in find_specs(project)] == ["verify_damped_oscillator.py"]
    (project / "pyproject.toml").write_text("[tool.physverify]\nspecs = ['verify_damped_oscillator.py']\n")
    assert find_specs(project) == [(project / "verify_damped_oscillator.py").resolve()]


def test_hook_is_silent_on_a_correct_solver(project):
    err = io.StringIO()
    assert hook_main(event(project), err) == 0
    assert err.getvalue() == ""


def test_hook_reports_a_seeded_bug_back_to_the_assistant(project):
    seed_bug(project)
    err = io.StringIO()
    assert hook_main(event(project), err) == 2
    text = err.getvalue()
    assert "checks did not pass" in text and "[mms]" in text and "[patch]" in text


def test_hook_ignores_non_python_edits_and_bad_input(project):
    seed_bug(project)
    assert hook_main(event(project, "notes.md"), io.StringIO()) == 0
    assert hook_main(io.StringIO("not json"), io.StringIO()) == 0


def test_hook_does_not_run_code_outside_the_session_folder(project, tmp_path_factory):
    session = tmp_path_factory.mktemp("session")
    seed_bug(project)
    edit = io.StringIO(json.dumps({"cwd": str(session),
                                   "tool_input": {"file_path": str(project / "damped_oscillator.py")}}))
    assert hook_main(edit, io.StringIO()) == 0


def test_pyproject_specs_outside_the_root_are_dropped(project, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "verify_evil.py"
    outside.write_text("raise SystemExit('must not be imported')\n")
    (project / "pyproject.toml").write_text(
        f"[tool.physverify]\nspecs = ['verify_damped_oscillator.py', {str(outside)!r}, '../verify_up.py']\n")
    assert find_specs(project) == [(project / "verify_damped_oscillator.py").resolve()]


def test_mcp_lists_and_runs_the_tool(project):
    init = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
    assert init["result"]["serverInfo"]["name"] == "physverify"
    assert handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    tools = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    assert [t["name"] for t in tools] == ["run_checks", "confirm_claim"]

    seed_bug(project)
    call = handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                   "params": {"name": "run_checks", "arguments": {"project": str(project)}}})
    text = call["result"]["content"][0]["text"]
    assert text.startswith("physverify: 4 of 4 checks did not pass")
    report = json.loads(text[text.index("{"):])
    assert report["summary"]["not_ok"] == 4


def test_mcp_server_says_it_is_deprecated(capsys):
    """The notice reaches the person (stderr) and the assistant (instructions and tool descriptions)."""
    from physverify.agent import DEPRECATION_ISSUE
    init = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
    assert "deprecated" in init["result"]["instructions"] and DEPRECATION_ISSUE in init["result"]["instructions"]
    tools = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    assert all(t["description"].startswith("Deprecated: ") for t in tools)
    out = io.StringIO()
    mcp_main(io.StringIO(""), out)
    assert out.getvalue() == ""  # nothing on the protocol stream
    assert "deprecated" in capsys.readouterr().err


def test_mcp_errors_are_json_rpc_errors():
    assert handle({"jsonrpc": "2.0", "id": 1, "method": "nope"})["error"]["code"] == -32601
    out = io.StringIO()
    mcp_main(io.StringIO("{bad json\n"), out)
    assert json.loads(out.getvalue())["error"]["code"] == -32700


def test_mcp_server_over_stdio_in_a_subprocess(project):
    """End to end, as a client would run it: python -m physverify mcp."""
    seed_bug(project)
    lines = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "run_checks", "arguments": {"specs": [str(project / "verify_damped_oscillator.py")]}}},
    ]
    proc = subprocess.run(
        [sys.executable, "-m", "physverify", "mcp"],
        input="\n".join(json.dumps(m) for m in lines) + "\n",
        capture_output=True, text=True, timeout=120,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")},
    )
    responses = [json.loads(l) for l in proc.stdout.splitlines()]
    assert [r["id"] for r in responses] == [1, 2], proc.stderr
    assert "did not pass" in responses[1]["result"]["content"][0]["text"]


# --- modern era (MCP 2026-07-28): no handshake, the version travels in every request's _meta ---

MODERN_META = {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientInfo": {"name": "test-client", "version": "0"},
    "io.modelcontextprotocol/clientCapabilities": {},
}


def modern(method, params=None, msg_id=1, meta=None):
    return {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": {**(params or {}), "_meta": MODERN_META if meta is None else meta}}


def test_mcp_discover_reports_the_modern_version_with_cache_hints():
    result = handle(modern("server/discover"))["result"]
    assert result["resultType"] == "complete"
    assert result["supportedVersions"] == ["2026-07-28"]
    assert result["capabilities"] == {"tools": {}}
    assert result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "physverify"
    assert result["ttlMs"] >= 0 and result["cacheScope"] == "public"
    assert result["instructions"]


def test_mcp_modern_list_and_call_work_without_a_handshake(project):
    listed = handle(modern("tools/list"))["result"]
    assert listed["resultType"] == "complete" and [t["name"] for t in listed["tools"]] == ["run_checks", "confirm_claim"]
    assert listed["ttlMs"] >= 0 and listed["cacheScope"] == "public"

    seed_bug(project)
    called = handle(modern("tools/call", {"name": "run_checks", "arguments": {"project": str(project)}}, msg_id=2))["result"]
    assert called["resultType"] == "complete" and called["isError"] is False
    assert "ttlMs" not in called  # a tool call is never cached
    assert called["content"][0]["text"].startswith("physverify: 4 of 4 checks did not pass")
    assert handle(modern("ping"))["result"]["resultType"] == "complete"


def test_mcp_modern_unknown_tool_and_method_are_json_rpc_errors():
    assert handle(modern("tools/call", {"name": "nope"}))["error"]["code"] == -32602
    assert handle(modern("resources/list"))["error"]["code"] == -32601


def test_mcp_modern_rejects_an_unsupported_version_and_lists_the_supported_ones():
    meta = {**MODERN_META, "io.modelcontextprotocol/protocolVersion": "2999-01-01"}
    error = handle(modern("tools/list", meta=meta))["error"]
    assert error["code"] == -32022
    assert error["data"] == {"supported": ["2026-07-28"], "requested": "2999-01-01"}


def test_mcp_modern_rejects_requests_missing_required_meta():
    no_caps = {"io.modelcontextprotocol/protocolVersion": "2026-07-28"}
    assert handle(modern("tools/list", meta=no_caps))["error"]["code"] == -32602
    assert handle({"jsonrpc": "2.0", "id": 1, "method": "server/discover"})["error"]["code"] == -32602


def test_mcp_legacy_handshake_still_negotiates_and_results_stay_legacy_shaped():
    def init(version):
        message = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": version}}
        return handle(message)["result"]["protocolVersion"]

    assert init("2025-06-18") == "2025-06-18"
    assert init("2024-11-05") == "2024-11-05"
    assert init("1900-01-01") == "2025-11-25"  # unknown: answer with the newest legacy version served
    listed = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {"_meta": {"progressToken": 7}}})["result"]
    assert "resultType" not in listed and "ttlMs" not in listed


def test_mcp_server_over_stdio_in_modern_mode_with_no_initialize(project):
    """A modern client: probe with server/discover, then call the tool, never sending initialize."""
    seed_bug(project)
    lines = [
        modern("server/discover", msg_id=1),
        modern("tools/call", {"name": "run_checks", "arguments": {"specs": [str(project / "verify_damped_oscillator.py")]}}, msg_id=2),
    ]
    proc = subprocess.run(
        [sys.executable, "-m", "physverify", "mcp"],
        input="\n".join(json.dumps(m) for m in lines) + "\n",
        capture_output=True, text=True, timeout=120,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")},
    )
    responses = [json.loads(l) for l in proc.stdout.splitlines()]
    assert [r["id"] for r in responses] == [1, 2], proc.stderr
    assert responses[0]["result"]["supportedVersions"] == ["2026-07-28"]
    assert responses[1]["result"]["resultType"] == "complete"
    assert "did not pass" in responses[1]["result"]["content"][0]["text"]


def test_mcp_run_checks_sees_a_solver_edit_between_two_calls(project):
    def call():
        return handle({"jsonrpc": "2.0", "id": 9, "method": "tools/call",
                       "params": {"name": "run_checks", "arguments": {"project": str(project)}}})["result"]["content"][0]["text"]

    assert not call().startswith("physverify:")  # correct solver: no failure summary
    seed_bug(project)
    assert call().startswith("physverify: 4 of 4 checks did not pass")
    assert "damped_oscillator" not in sys.modules  # the checks ran in a child process, not in the server


def test_mcp_run_checks_times_out_as_a_load_error(tmp_path):
    (tmp_path / "verify_hang.py").write_text("import time\ntime.sleep(60)\ndef checks():\n    return []\n")
    text = handle({"jsonrpc": "2.0", "id": 9, "method": "tools/call",
                   "params": {"name": "run_checks", "arguments": {"project": str(tmp_path), "timeout": 3}}})["result"]["content"][0]["text"]
    assert "timed out after 3 s" in text


def test_mcp_confirm_claim_needs_trust_and_gives_the_verdict(tmp_path, monkeypatch):
    monkeypatch.delenv("PHYSVERIFY_REPO", raising=False)
    claims = ROOT / "docs" / "examples" / "confirm"
    ledger = tmp_path / "ledger.jsonl"

    def call(**arguments):
        return handle(modern("tools/call", {"name": "confirm_claim", "arguments": arguments}, msg_id=4))["result"]

    refused = call(claim=str(claims / "claim_damping_sign.py"), ledger=str(ledger))
    assert refused["isError"] is True and "sandbox/README.md" in refused["content"][0]["text"] and not ledger.exists()
    done = call(claim=str(claims / "claim_damping_sign.py"), ledger=str(ledger), trusted=True)
    assert done["isError"] is False and done["content"][0]["text"].startswith("confirmed (impact: used)")
    assert json.loads(ledger.read_text())["verdict"] == "confirmed"


@pytest.mark.parametrize("tool", ["run_checks", "confirm_claim"])
def test_mcp_a_non_numeric_timeout_is_a_tool_error(tool, tmp_path):
    arguments = {"timeout": "abc", "project": str(tmp_path), "claim": str(tmp_path / "claim.py"), "trusted": True}
    (tmp_path / "verify_x.py").write_text("def checks():\n    return []\n")
    result = handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": tool, "arguments": arguments}})
    assert "error" not in result
    assert result["result"]["isError"] is True and "timeout" in result["result"]["content"][0]["text"]


@pytest.mark.parametrize("tool", ["run_checks", "confirm_claim"])
@pytest.mark.parametrize("timeout", [0, True, -3])
def test_mcp_a_zero_or_boolean_timeout_is_refused_not_replaced(tool, timeout, tmp_path):
    arguments = {"timeout": timeout, "project": str(tmp_path), "claim": str(tmp_path / "claim.py"), "trusted": True}
    (tmp_path / "verify_x.py").write_text("def checks():\n    return []\n")
    result = handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": tool, "arguments": arguments}})
    assert result["result"]["isError"] is True and "timeout" in result["result"]["content"][0]["text"]
