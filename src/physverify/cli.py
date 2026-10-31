"""Command line.

    physverify run SPEC.py [SPEC.py ...] [--json FILE|-] [--html FILE] [--markdown FILE] [--quiet]
    physverify demo        (a correct and a broken solver, no files needed)
    physverify init [SPEC.py] [--solver MODULE] [--function NAME] [--dim N] [--order P]
    physverify scan PATH   (reads the source, runs nothing: constants, RK tables, grid spacing, inverse pairs,
                           undefined names, removed APIs, typo-like literals, unit tables)
    physverify hook        (Claude Code PostToolUse hook; see docs/agent.md)
    physverify mcp         (MCP server on stdio; see docs/agent.md)

`run` exits 0 when no check fails (PASS, EXACT or SKIP), 1 when any does not,
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
    from .report import NOTE, load_spec, run_checks, to_html, to_json, to_markdown, to_text

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
        if not checks:
            print(f"physverify: {spec}: checks() returned no checks, so nothing was tested", file=sys.stderr)
            return 2
        outcomes += run_checks(checks, args.budget)
        from .specscan import reference_notes
        for note in reference_notes(spec):
            print(f"physverify: note: {note}", file=sys.stderr)
    source = ", ".join(str(Path(s)) for s in args.specs)
    if args.json == "-":
        print(to_json(outcomes, source))
    else:
        if not args.quiet:
            print(to_text(outcomes))
            print(NOTE)
        if args.json:
            Path(args.json).write_text(to_json(outcomes, source), encoding="utf-8")
    if args.html:
        Path(args.html).write_text(to_html(outcomes, source=source), encoding="utf-8")
    if args.markdown:
        with open(args.markdown, "a", encoding="utf-8") as f:  # append: $GITHUB_STEP_SUMMARY may hold other steps' output
            f.write(to_markdown(outcomes, source))
    return 1 if any(o.result.failed for o in outcomes) else 0


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


def _cmd_demo(args) -> int:
    from .demo import main as demo_main

    return demo_main()


def _cmd_hook(args) -> int:
    from .agent import hook_main

    return hook_main()


def _cmd_mcp(args) -> int:
    from .agent import mcp_main

    return mcp_main()


def _cmd_smoke(args) -> int:
    from .smoke import OK, smoke

    results = smoke(args.path, timeout=args.timeout)
    for r in results:
        note = f" ({r.nan_warnings} NaN/overflow warnings)" if r.nan_warnings else ""
        print(f"{r.outcome:16s} {r.path}: {r.detail}{note}")
    bad = sum(r.outcome != OK for r in results)
    print(f"{len(results)} scripts, {len(results) - bad} ran to the end")
    return 1 if bad else 0


def _cmd_scan(args) -> int:
    import json

    from .probes import DEFAULT_PROBES, PROBES, probe
    from .scan import STAGES, WARN, scan, to_dict

    known = STAGES + PROBES if args.run else STAGES
    stages = args.only.split(",") if args.only else (STAGES + DEFAULT_PROBES if args.run else STAGES)
    unknown = set(stages) - set(known)
    if unknown:
        extra = "; the probes need --run" if unknown <= set(PROBES) else ""
        print(f"physverify: unknown stage {', '.join(sorted(unknown))}; choose from {', '.join(known)}{extra}", file=sys.stderr)
        return 2
    if not Path(args.path).exists():
        print(f"physverify: {args.path} does not exist", file=sys.stderr)
        return 2
    findings, unparsed = scan(args.path, stages=[s for s in stages if s in STAGES])
    probes = [s for s in stages if s in PROBES]
    if probes:
        print("physverify: --run calls the code; use it only on code you trust or inside the sandbox", file=sys.stderr)
        findings += probe(args.path, probes=probes, timeout=args.timeout)
    if args.json:
        text = json.dumps(to_dict(findings, unparsed), indent=1)
        if args.json == "-":
            print(text)
        else:
            Path(args.json).write_text(text, encoding="utf-8")
    if args.json != "-":
        for f in findings:
            print(f)
        for u in unparsed:
            print(f"NOTE parse     {u}")
        warn = sum(f.level == WARN for f in findings)
        skip = sum(f.level == "SKIP" for f in findings)
        ran = (f", {skip} skipped (not passed)" if probes else "")
        how = "the probes called the code with small inputs" if probes else "the scan reads the code and runs nothing"
        print(f"{warn} warnings, {len(findings) - warn - skip} notes{ran}, {len(unparsed)} files not parsed"
              f" ({how}; a clean scan means only that these patterns were not found)")
    return 1 if any(f.level == WARN for f in findings) else 0


def _cmd_references(args) -> int:
    from . import references

    for name, what in references.REFERENCES.items():
        print(f"{name:30s} {what}")
    print()
    print("from physverify import references; help(references.<name>) gives the formula and its source")
    return 0


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
    run.add_argument("--budget", type=float, metavar="SECONDS",
                     help="time budget per check: order studies stop adding resolutions when the next would overrun it,"
                          " and a check still running at twice the budget is reported INCONCLUSIVE")
    run.set_defaults(func=_cmd_run)

    d = sub.add_parser("demo", help="run the checks on a correct and on a broken example solver (no files needed)")
    d.set_defaults(func=_cmd_demo)

    i = sub.add_parser("init", help="write a starter spec for a fixed-step ODE solver")
    i.add_argument("spec", nargs="?", default="verify_solver.py", help="spec file to write (default verify_solver.py)")
    i.add_argument("--solver", default="solver", help="module that holds the solver, importable from the spec's folder (default solver)")
    i.add_argument("--function", default="integrate", help="integrate(source, y0, t_end, n_steps) function (default integrate)")
    i.add_argument("--dim", type=int, default=2, help="number of state variables (default 2)")
    i.add_argument("--order", type=float, default=2.0, help="order of accuracy the solver claims (default 2)")
    i.add_argument("--t-end", type=float, default=1.0, help="end time of the test runs (default 1)")
    i.add_argument("--force", action="store_true", help="overwrite an existing file")
    i.set_defaults(func=_cmd_init)

    h = sub.add_parser("hook", help="Claude Code PostToolUse hook: reads the event on stdin, exits 2 on a failed check")
    h.set_defaults(func=_cmd_hook)

    sm = sub.add_parser("smoke", help="check that each script parses and runs to the end (runs the code: trusted code or the sandbox only)")
    sm.add_argument("path", help="a script or a folder of scripts")
    sm.add_argument("--timeout", type=float, default=60.0, help="seconds per script (default 60)")
    sm.set_defaults(func=_cmd_smoke)

    sc = sub.add_parser("scan", help="look for common defects without a spec file; reads the code and runs nothing")
    sc.add_argument("path", help="a Python file or a folder")
    sc.add_argument("--only", metavar="STAGES", help="comma-separated stages: constants,tables,grid,pairs,names,api,literals,units (default all)")
    sc.add_argument("--json", metavar="FILE", help="write findings as JSON to FILE, or to stdout with -")
    sc.add_argument("--run", action="store_true",
                    help="also run the probes smoke and branches, which CALL the code (trusted code or the sandbox only); "
                         "the experimental probes edges,deadargs,roundtrip,siblings,known,monotone with --only")
    sc.add_argument("--timeout", type=float, default=60.0, help="with --run: seconds per script or file of functions (default 60)")
    sc.set_defaults(func=_cmd_scan)

    r = sub.add_parser("references", help="list the exact reference solutions in physverify.references")
    r.set_defaults(func=_cmd_references)

    s = sub.add_parser("mcp", help="run a minimal MCP server on stdio with a run_checks tool")
    s.set_defaults(func=_cmd_mcp)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
