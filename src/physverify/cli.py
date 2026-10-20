"""Command line.

    physverify run SPEC.py [SPEC.py ...] [--json FILE|-] [--html FILE] [--markdown FILE] [--quiet]
    physverify init [SPEC.py] [--solver MODULE] [--function NAME] [--dim N] [--order P]
    physverify matrix [OUT.md]
    physverify compare [OUT.md]
    physverify hook        (Claude Code PostToolUse hook; see docs/agent.md)
    physverify mcp         (MCP server on stdio; see docs/agent.md)

`run` exits 0 when every check passes (PASS or EXACT), 1 when any does not,
and 2 when a spec cannot be loaded. A spec is a Python file defining
`checks()`; see examples/verify_damped_oscillator.py.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__


def expand_specs(patterns) -> list[str]:
    """Spec paths, with glob patterns ("**/verify_*.py") expanded here so they work in any shell.

    A pattern that matches nothing raises FileNotFoundError, so a CI job with a
    mistyped path fails instead of passing with no checks.
    """
    import glob

    specs = []
    for pattern in patterns:
        if any(c in pattern for c in "*?[") and not Path(pattern).exists():
            found = sorted(glob.glob(pattern, recursive=True))
            if not found:
                raise FileNotFoundError(f"no spec file matches {pattern}")
            specs += [f for f in found if f not in specs]
        elif pattern not in specs:
            specs.append(pattern)
    return specs


def _cmd_run(args) -> int:
    from .report import load_spec, run_checks, to_html, to_json, to_markdown, to_text

    try:
        args.specs = expand_specs(args.specs)
    except FileNotFoundError as exc:
        print(f"physverify: {exc}", file=sys.stderr)
        return 2
    outcomes = []
    for spec in args.specs:
        try:
            checks = load_spec(spec)
        except Exception as exc:
            print(f"physverify: cannot load {spec}: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
        outcomes += run_checks(checks)
    source = ", ".join(str(Path(s)) for s in args.specs)
    if args.json == "-":
        print(to_json(outcomes, source))
    else:
        if not args.quiet:
            print(to_text(outcomes))
        if args.json:
            Path(args.json).write_text(to_json(outcomes, source), encoding="utf-8")
    if args.html:
        Path(args.html).write_text(to_html(outcomes, source=source), encoding="utf-8")
    if args.markdown:
        with open(args.markdown, "a", encoding="utf-8") as f:  # append: $GITHUB_STEP_SUMMARY may hold other steps' output
            f.write(to_markdown(outcomes, source))
    return 0 if all(o.result.ok for o in outcomes) else 1


def _cmd_init(args) -> int:
    from .scaffold import write_spec

    try:
        path = write_spec(args.spec, args.solver, args.function, args.dim, args.order, args.t_end, force=args.force)
    except (FileExistsError, ValueError) as exc:
        print(f"physverify: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {path}")
    print("next: write reference_rhs and Y0 in it (marked TODO), then run")
    print(f"    physverify run {path}")
    return 0


def _cmd_matrix(args) -> int:
    from . import matrix

    return matrix.main([args.out] if args.out else [])


def _cmd_compare(args) -> int:
    from . import compare

    return compare.main([args.out] if args.out else [])


def _cmd_hook(args) -> int:
    from .agent import hook_main

    return hook_main()


def _cmd_mcp(args) -> int:
    from .agent import mcp_main

    return mcp_main()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="physverify", description="Verification checks for physics simulation code.")
    parser.add_argument("--version", action="version", version=f"physverify {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run the checks defined in one or more spec files")
    run.add_argument("specs", nargs="+", help="Python files that define checks(); glob patterns such as '**/verify_*.py' are expanded")
    run.add_argument("--json", metavar="FILE", help="write results as JSON to FILE, or to stdout with -")
    run.add_argument("--html", metavar="FILE", help="write a self-contained HTML report")
    run.add_argument("--markdown", metavar="FILE", help="append a Markdown table to FILE (for $GITHUB_STEP_SUMMARY)")
    run.add_argument("--quiet", action="store_true", help="no text output")
    run.set_defaults(func=_cmd_run)

    i = sub.add_parser("init", help="write a starter spec for a fixed-step ODE solver")
    i.add_argument("spec", nargs="?", default="verify_solver.py", help="spec file to write (default verify_solver.py)")
    i.add_argument("--solver", default="solver", help="module that holds the solver, importable from the spec's folder (default solver)")
    i.add_argument("--function", default="integrate", help="integrate(source, y0, t_end, n_steps) function (default integrate)")
    i.add_argument("--dim", type=int, default=2, help="number of state variables (default 2)")
    i.add_argument("--order", type=float, default=2.0, help="order of accuracy the solver claims (default 2)")
    i.add_argument("--t-end", type=float, default=1.0, help="end time of the test runs (default 1)")
    i.add_argument("--force", action="store_true", help="overwrite an existing file")
    i.set_defaults(func=_cmd_init)

    m = sub.add_parser("matrix", help="run the seeded-bug benchmark")
    m.add_argument("out", nargs="?", help="also write the tables next to this Markdown file")
    m.set_defaults(func=_cmd_matrix)

    c = sub.add_parser("compare", help="compare the families with plain tests on the seeded bugs")
    c.add_argument("out", nargs="?", help="also write the table to this Markdown file")
    c.set_defaults(func=_cmd_compare)

    h = sub.add_parser("hook", help="Claude Code PostToolUse hook: reads the event on stdin, exits 2 on a failed check")
    h.set_defaults(func=_cmd_hook)

    s = sub.add_parser("mcp", help="run a minimal MCP server on stdio with a run_checks tool")
    s.set_defaults(func=_cmd_mcp)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
