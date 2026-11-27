"""Mutation runs: does a spec fail when the solver is broken on purpose?

A PASS means more when the same spec is shown to fail on broken code. `physverify mutate SPEC --target FILE`
makes one small change at a time in FILE (a numeric constant scaled by 1.1, keyword defaults and arguments
included; + swapped with -, * with /; < with <=, > with >=; a constant index moved by one; a unary minus
dropped), runs the spec on each changed copy in a fresh process and reports which changes the
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
_CMP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt}
_CMP_NAMES = {ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">="}


def _int_index(node) -> bool:
    """y[0], y[-1]: a subscript whose index is one integer constant."""
    s = node.slice
    if isinstance(s, ast.UnaryOp) and isinstance(s.op, ast.USub):
        s = s.operand
    return isinstance(s, ast.Constant) and type(s.value) is int


def _index_value(node) -> int:
    s = node.slice
    return -s.operand.value if isinstance(s, ast.UnaryOp) else s.value


@dataclass
class Mutant:
    index: int
    line: int
    col: int
    description: str
    stmt_line: int = 0  # first line of the statement the change is in
    status: str = ""  # "caught", "survived", "timeout", "not run"
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


def _is_one(node) -> bool:
    return isinstance(node, ast.Constant) and type(node.value) in (int, float) and node.value == 1


def _statement_lines(tree) -> dict[int, int]:
    """id of each node -> first line of the innermost statement that holds it."""
    out: dict[int, int] = {}
    for stmt in ast.walk(tree):
        if isinstance(stmt, ast.stmt):
            for n in ast.walk(stmt):
                out[id(n)] = stmt.lineno  # inner statements come later in the walk and overwrite
    return out


def _inside_functions(tree, names) -> set[int] | None:
    """ids of nodes inside a function (or method) with one of `names`; None when `names` is empty."""
    if not names:
        return None
    inside: set[int] = set()
    for f in ast.walk(tree):
        if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) and f.name in names:
            for part in f.body:  # the body only: defaults and decorators are evaluated outside the call
                inside.update(id(n) for n in ast.walk(part))
    return inside


def _sites(tree, functions=()):
    """Yield (node, kind, description) for every change made, in a fixed order; only inside `functions` if given.

    Changes that cannot alter the result are not made: x * 1 and x / 1 are the same number."""
    skip = _skip_subscript_parents(tree)
    inside = _inside_functions(tree, set(functions))
    for node in ast.walk(tree):
        if id(node) in skip or (inside is not None and id(node) not in inside):
            continue
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mult, ast.Div)) and _is_one(node.right):
            continue
        if isinstance(node, ast.Subscript) and _int_index(node):
            i = _index_value(node)
            yield node, "index", f"index [{i}] -> [{i + 1 if i >= 0 else i - 1}]"
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _CMP:
            old = type(node.ops[0])
            yield node, "cmp", f"comparison {_CMP_NAMES[old]} -> {_CMP_NAMES[_CMP[old]]}"
        elif isinstance(node, ast.Constant) and type(node.value) in (int, float) and node.value != 0:
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
    if kind == "cmp":
        node.ops = [_CMP[type(node.ops[0])]()]
        return node
    if kind == "index":  # away from zero, so y[0] -> y[1] and y[-1] -> y[-2]
        i = _index_value(node)
        node.slice = ast.Constant(i + 1 if i >= 0 else i - 1)
        return node
    return node.operand  # "neg"


class _Replace(ast.NodeTransformer):
    def __init__(self, target, kind):
        self.target, self.kind = target, kind

    def visit(self, node):
        if node is self.target:
            return _apply(node, self.kind)
        return self.generic_visit(node)


def mutants(source: str, functions=()) -> list[Mutant]:
    """The changes `mutate` makes in `source` (only inside `functions` if given), with the line and column of
    each in the original."""
    tree = ast.parse(source)
    stmts = _statement_lines(tree)
    return [Mutant(i, n.lineno, n.col_offset + 1, d, stmts.get(id(n), n.lineno))
            for i, (n, _, d) in enumerate(_sites(tree, functions))]


def mutant_source(source: str, index: int, functions=()) -> str:
    """`source` with change number `index` made (as Python source; comments and layout are not kept)."""
    tree = ast.parse(source)
    for i, (node, kind, _) in enumerate(_sites(tree, functions)):
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


def run_mutants(specs, target, timeout: float = 120.0, limit: int | None = None, progress=None, functions=()):
    """Run `specs` on the unchanged target, then on each mutant of it. Returns (baseline report, mutants).

    Raises RuntimeError when the specs do not pass on the unchanged code: a mutation run then says nothing.
    The target file is restored before this returns or raises.
    """
    from .agent import run_specs_isolated

    target = Path(target)
    original = target.read_bytes()
    source = original.decode("utf-8")
    baseline = _traced_baseline(specs, target, timeout)
    status, detail = _verdict(baseline)
    if status != "survived":
        raise RuntimeError(f"the specs do not pass on the unchanged code ({detail}), so a mutation run would say nothing")
    ran = baseline.get("target_lines")
    found = mutants(source, functions)[:limit]
    if functions and not found:
        raise RuntimeError(f"no change can be made inside {', '.join(functions)} in {target}; check the names")
    try:
        for m in found:
            if ran is not None and m.stmt_line not in ran and m.line not in ran:
                m.status, m.detail = "not run", "the specs never run this line, so no change here can be caught"
                if progress:
                    progress(m)
                continue
            target.write_text(mutant_source(source, m.index, functions), encoding="utf-8")
            m.status, m.detail = _verdict(run_specs_isolated(specs, timeout))
            if progress:
                progress(m)
    finally:
        target.write_bytes(original)
    return baseline, found


def _traced_baseline(specs, target, timeout):
    """The specs on the unchanged code, with the lines of `target` that ran (key "target_lines").
    Without that key when the traced run failed; the untraced result is returned then."""
    from .agent import run_specs_isolated
    from .isolate import run_isolated

    run = run_isolated("specs_lines", [Path(target).resolve(), *[Path(s).resolve() for s in specs]],
                       None if timeout is None else 4 * timeout)  # tracing makes the run slower
    if run["status"] == "done":
        return run["result"]
    return run_specs_isolated(specs, timeout)


def to_json(target, found) -> str:
    """One record per change, for recording mutation scores."""
    import json

    caught = sum(m.status in ("caught", "timeout") for m in found)
    return json.dumps({"target": str(target), "total": len(found), "caught": caught,
                       "not_run": sum(m.status == "not run" for m in found),
                       "survived": sum(m.status == "survived" for m in found),
                       "mutants": [{"line": m.line, "col": m.col, "change": m.description, "status": m.status,
                                    "detail": m.detail} for m in sorted(found, key=lambda m: (m.line, m.col, m.index))]},
                      indent=2)


def format_report(target, found) -> str:
    caught = sum(m.status in ("caught", "timeout") for m in found)
    not_run = sum(m.status == "not run" for m in found)
    lines = [f"{target}:{m.line}:{m.col}: {m.status.upper():9} {m.description} ({m.detail})"
             for m in sorted(found, key=lambda m: (m.line, m.col, m.index))]
    lines.append(f"physverify mutate: the specs caught {caught} of {len(found)} changes to {target}"
                 " (a timeout counts as caught).")
    if not_run:
        lines.append(f"{not_run} change(s) are on lines the specs never run: a test that runs that code is missing.")
    if caught + not_run < len(found):
        lines.append("A survivor is either a gap in the specs or a change that does not alter what the code"
                     " computes; look at each one before calling it a gap.")
    return "\n".join(lines)
