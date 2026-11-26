"""Mutation runs: does a spec fail when the solver is broken on purpose?

A PASS means more when the same spec is shown to fail on broken code. `physverify mutate SPEC --target FILE`
makes one small change at a time in FILE (a numeric constant scaled by 1.1, + swapped with -, * with /,
a unary minus dropped), runs the spec on each changed copy in a fresh process and reports which changes the
spec caught. The idea follows mutation testing as applied to numerical code by Wu and Mitchell (NSV 2019);
fineness gates its checks the same way.

FILE is changed in place during the run and restored afterwards, also on Ctrl-C. This runs the code under
test: trusted code or the sandbox only. A change that survives is not always a gap in the spec: some changes
do not alter what the code computes (an equivalent mutant), so each survivor needs a look.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

SCALE = 1.1
_SWAP = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult}
_NAMES = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}


@dataclass
class Mutant:
    index: int
    line: int
    col: int
    description: str
    status: str = ""  # "caught", "survived", "timeout"
    detail: str = ""


def _skip_subscript_parents(tree) -> set[int]:
    """ids of nodes inside a subscript slice or a range() call: changing an index or a loop count mostly
    gives an IndexError or a shorter loop, which says little about the physics checks."""
    skip = set()
    for node in ast.walk(tree):
        inner = []
        if isinstance(node, ast.Subscript):
            inner = [node.slice]
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "range":
            inner = node.args
        for part in inner:
            skip.update(id(n) for n in ast.walk(part))
    return skip


def _sites(tree):
    """Yield (node, kind, description) for every change made, in a fixed order."""
    skip = _skip_subscript_parents(tree)
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if isinstance(node, ast.Constant) and type(node.value) in (int, float) and node.value != 0:
            yield node, "scale", f"constant {node.value!r} -> {node.value * SCALE!r}"
        elif isinstance(node, ast.BinOp) and type(node.op) in _SWAP:
            new = _SWAP[type(node.op)]
            yield node, "swap", f"operator {_NAMES[type(node.op)]} -> {_NAMES[new]}"
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            yield node, "neg", "unary minus removed"


def _apply(node, kind):
    if kind == "scale":
        node.value = node.value * SCALE
        return node
    if kind == "swap":
        node.op = _SWAP[type(node.op)]()
        return node
    return node.operand  # "neg"


class _Replace(ast.NodeTransformer):
    def __init__(self, target, kind):
        self.target, self.kind = target, kind

    def visit(self, node):
        if node is self.target:
            return _apply(node, self.kind)
        return self.generic_visit(node)


def mutants(source: str) -> list[Mutant]:
    """The changes `mutate` makes in `source`, with the line and column of each in the original."""
    tree = ast.parse(source)
    return [Mutant(i, n.lineno, n.col_offset + 1, d) for i, (n, _, d) in enumerate(_sites(tree))]


def mutant_source(source: str, index: int) -> str:
    """`source` with change number `index` made (as Python source; comments and layout are not kept)."""
    tree = ast.parse(source)
    for i, (node, kind, _) in enumerate(_sites(tree)):
        if i == index:
            tree = _Replace(node, kind).visit(tree)
            return ast.unparse(ast.fix_missing_locations(tree))
    raise IndexError(f"no change number {index}")


def _verdict(report: dict) -> tuple[str, str]:
    errors = report.get("load_errors") or []
    if any("timed out" in e["error"] for e in errors):
        return "timeout", errors[0]["error"][:200]
    if errors:
        return "caught", "spec could not run: " + errors[0]["error"][:200]
    failed = [c for c in report["checks"] if not c["ok"]]
    if failed:
        return "caught", f"{failed[0]['status']} {failed[0]['label']}"
    return "survived", f"all {len(report['checks'])} checks passed"


def run_mutants(specs, target, timeout: float = 120.0, limit: int | None = None, progress=None):
    """Run `specs` on the unchanged target, then on each mutant of it. Returns (baseline report, mutants).

    Raises RuntimeError when the specs do not pass on the unchanged code: a mutation run then says nothing.
    The target file is restored before this returns or raises.
    """
    from .agent import run_specs_isolated

    target = Path(target)
    original = target.read_bytes()
    source = original.decode("utf-8")
    baseline = run_specs_isolated(specs, timeout)
    status, detail = _verdict(baseline)
    if status != "survived":
        raise RuntimeError(f"the specs do not pass on the unchanged code ({detail}), so a mutation run would say nothing")
    found = mutants(source)[:limit]
    try:
        for m in found:
            target.write_text(mutant_source(source, m.index), encoding="utf-8")
            m.status, m.detail = _verdict(run_specs_isolated(specs, timeout))
            if progress:
                progress(m)
    finally:
        target.write_bytes(original)
    return baseline, found


def format_report(target, found) -> str:
    caught = sum(m.status in ("caught", "timeout") for m in found)
    lines = [f"{target}:{m.line}:{m.col}: {m.status.upper():8} {m.description} ({m.detail})"
             for m in sorted(found, key=lambda m: (m.line, m.col, m.index))]
    lines.append(f"physverify mutate: the specs caught {caught} of {len(found)} changes to {target}"
                 " (a timeout counts as caught).")
    if caught < len(found):
        lines.append("A survivor is either a gap in the specs or a change that does not alter what the code"
                     " computes; look at each one before calling it a gap.")
    return "\n".join(lines)
