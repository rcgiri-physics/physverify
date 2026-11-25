# Using physverify from an AI coding assistant

An assistant that writes simulation code can make the same mistakes a person does: a wrong sign, a missing factor, an RK stage at the wrong time. physverify gives it two ways to find out:
- a **hook** that runs the checks after every edit;
- an **MCP tool** the assistant can call when it chooses.

Both call the same code as `physverify run`. Neither needs anything beyond physverify itself.

Neither is switched on by installing the package. You add them to your own assistant's configuration, as shown below.

## 0. A prompt you can paste

[Start here](start-here.md#with-an-ai-assistant) has a prompt that asks an assistant to find what the code claims, write each reference from the physics (not from the code), test the claims as pytest tests and report what was and was not tested. An assistant working on physverify itself should read [AGENTS.md](https://github.com/rcgiri-physics/physverify/blob/main/AGENTS.md) in the repository.

### As an agent skill

The same rules are packaged as an [agent skill](https://agentskills.io): the folder [skills/physverify](https://github.com/rcgiri-physics/physverify/tree/main/skills/physverify). Copy that folder into your assistant's skills folder; for Claude Code that is `~/.claude/skills/` (all your projects) or `.claude/skills/` in one project. The assistant then loads it when you ask it to verify a solver. The skill is instructions only and contains no scripts; the steps it describes run your code.

## 1. Write a spec next to the solver

A spec is a `verify_*.py` file that defines `checks()`. [examples/verify_damped_oscillator.py](../examples/verify_damped_oscillator.py) is a complete one. The reference right-hand side in the spec must be written independently of the solver. If the assistant writes both, ask it to derive the reference from the equations, not from its solver.

The hook and the MCP tool find specs in this order:
1. `[tool.physverify] specs = ["path/verify_x.py", ...]` in the project's `pyproject.toml`;
2. otherwise, every `verify_*.py` under the project folder. Hidden folders, virtual environments and build output are skipped.

In both cases a `pyproject.toml` with [`[[tool.physverify.ode]]` tables](declarative.md) is run too.

## 2. Claude Code hook

Add this to `.claude/settings.json` in your project, or to your user settings:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [{ "type": "command", "command": "physverify hook" }]
      }
    ]
  }
}
```

After each edit to a `.py` file, the hook runs the specs.
- **All checks pass:** it prints nothing and exits 0.
- **A check fails, or a spec cannot be loaded:** it prints a short summary on stderr and exits 2. Claude Code shows that summary to the assistant, which can then fix the code.

Real output for a 10% error in the damping term of the example solver:

```
physverify: 4 of 4 checks did not pass.
- FAIL [mms] midpoint damped oscillator: error does not decrease with resolution (about 0.0114 at the finest level)
- FAIL [reference] midpoint damped oscillator: error does not decrease with resolution (about 0.028 at the finest level)
- FAIL [mms] midpoint damped oscillator (whole trajectory): error does not decrease with resolution (about 0.0207 at the finest level)
- FAIL [patch] midpoint damped oscillator: expected an exact solution to round-off, but the error reaches 0.0152 and shrinks at about order 0.01
Run `physverify run <spec> --html report.html` for convergence plots.
```

The checks run on every Python edit. For a slow suite, list only the fast specs under `[tool.physverify] specs`.

## 3. MCP server

```bash
claude mcp add physverify -- physverify mcp
```

### Other MCP clients

The server is a local program that the client starts; it runs on your computer, in the folder the client starts it in. Install physverify first (`pip install physverify`, best in a virtual environment), then give the client the command `physverify` with the argument `mcp`. If the client cannot find `physverify`, give the full path, for example `C:\Users\you\.venv\Scripts\physverify.exe` or `/home/you/.venv/bin/physverify`. With [uv](https://docs.astral.sh/uv/) installed you can skip the install and use the command `uvx` with the arguments `physverify`, `mcp`.

Most clients take the same `mcpServers` entry: Claude Desktop (`claude_desktop_config.json`), Cursor (`.cursor/mcp.json` or `~/.cursor/mcp.json`), Windsurf (`~/.codeium/windsurf/mcp_config.json`), Cline (MCP Servers, Configure, `cline_mcp_settings.json`) and Qoder (Qoder IDE Settings, MCP, My Servers, + Add):

```json
{
  "mcpServers": {
    "physverify": {
      "command": "physverify",
      "args": ["mcp"]
    }
  }
}
```

VS Code (`.vscode/mcp.json`) uses `servers`:

```json
{
  "servers": {
    "physverify": {
      "type": "stdio",
      "command": "physverify",
      "args": ["mcp"]
    }
  }
}
```

Codex CLI (`~/.codex/config.toml`):

```toml
[mcp_servers.physverify]
command = "physverify"
args = ["mcp"]
```

Give the tools full paths, or `project` as a full path: relative paths are taken from the folder the client started the server in. The server is also listed in the [official MCP registry](https://registry.modelcontextprotocol.io) as `io.github.rcgiri-physics/physverify`, for clients that install from it.

### Tools

The server speaks MCP over stdio and offers two tools. The first is `run_checks`:

| Argument | Meaning |
|---|---|
| `specs` | List of spec paths |
| `project` | Folder to search for `verify_*.py` when `specs` is not given |
| `timeout` | Seconds for the whole run (default 600) |

It returns the JSON report: status, message, observed and expected order, step sizes and errors for each check. Failures are summarised at the top. The checks run in a fresh Python process, so an edit to the solver between two calls is always seen; a run longer than `timeout` is stopped and reported as a load error.

The second is `confirm_claim`, which judges one claim file exactly like `physverify confirm` (see [Confirming one suspected defect](confirm.md)). It needs `trusted: true`, or the sandbox.

The server is written with the standard library only. It serves both protocol eras on the same process:
- the older handshake (`initialize`, protocol versions 2025-11-25 and earlier);
- the 2026-07-28 revision, which has no handshake: each request carries its protocol version in `_meta`, and `server/discover` reports what the server supports. A client that supports both eras probes with `server/discover` and takes this path; a client that supports only one era works with that era.

In both it implements `ping`, `tools/list` and `tools/call`, which is enough for a tool server, but not the whole MCP specification. Anything the code under test prints is sent to stderr, so that it cannot corrupt the protocol stream.

Safety: `run_checks` and the hook run the project's `verify_*.py` files, which is arbitrary Python. Use them only on projects you would trust to run their own tests, and do not expose the server over a network.

## What has been tested

`tests/test_agent.py` covers both layers:
- **Hook:** it feeds the hook a PostToolUse event for a solver with a seeded 10% damping error and checks that the failure is reported with exit code 2.
- **MCP:** it runs the MCP server as a subprocess and calls `run_checks` on the same bug.

These tests simulate the assistant's side. The installed `physverify hook` command was also run by hand on a PostToolUse event, which produced the output above. As of 2026-10-19, it has not been run inside a live Claude Code session.

For the MCP server, the tests also cover the 2026-07-28 path: `server/discover`, tool list and tool call without a handshake, an unsupported version, and a request missing the required `_meta` fields. The replies for that era were also validated, once and outside the test suite, against the official JSON schema for that revision. The older handshake is tested only in simulation, not against the schemas of the older revisions. The server has not been run with a real MCP client.
