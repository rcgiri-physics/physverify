"""Run a list of checks and report the results as text, JSON or a self-contained HTML page."""

from __future__ import annotations

import html
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path

from .checks import Check, OrderResult, Result, run_check
from .loaders import load_module_from_path


@dataclass
class Outcome:
    check: Check
    result: Result
    seconds: float


def run_checks(checks) -> list[Outcome]:
    out = []
    for check in checks:
        start = time.perf_counter()
        result = run_check(check)
        out.append(Outcome(check, result, time.perf_counter() - start))
    return out


def load_spec(path):
    """Import a spec file and return its checks.

    A spec is a Python file that defines `checks()`, returning a list of
    `physverify.Check`. Its folder is put on sys.path first, so it can import
    the solver next to it.
    """
    import sys

    path = Path(path).resolve()
    folder = str(path.parent)
    if folder not in sys.path:
        sys.path.insert(0, folder)
    name = "physverify_spec_" + "".join(c if c.isalnum() else "_" for c in str(path))
    module = load_module_from_path(name, path)
    if not callable(getattr(module, "checks", None)):
        raise AttributeError(f"{path} does not define checks()")
    checks = list(module.checks())
    for check in checks:
        if not isinstance(check, Check):
            raise TypeError(f"{path}: checks() returned {type(check).__name__}, not physverify.Check")
    return checks


def _number(x):
    x = float(x)
    return x if math.isfinite(x) else None


def outcome_to_dict(o: Outcome) -> dict:
    d = {
        "family": o.check.family,
        "label": o.check.label,
        "status": o.result.status,
        "ok": o.result.ok,
        "message": o.result.message,
        "seconds": round(o.seconds, 4),
    }
    if isinstance(o.result, OrderResult):
        d["expected_order"] = _number(o.result.expected)
        d["observed_order"] = _number(o.result.fitted)
        d["h"] = [_number(h) for h in o.result.hs]
        d["error"] = [_number(e) for e in o.result.errors]
    return d


def summary(outcomes) -> dict:
    return {
        "total": len(outcomes),
        "ok": sum(o.result.ok for o in outcomes),
        "not_ok": sum(not o.result.ok for o in outcomes),
        "by_status": {s: sum(o.result.status == s for o in outcomes) for s in sorted({o.result.status for o in outcomes})},
    }


def to_json(outcomes, source: str = "") -> str:
    from . import __version__

    payload = {
        "physverify": __version__,
        "source": source,
        "summary": summary(outcomes),
        "checks": [outcome_to_dict(o) for o in outcomes],
    }
    return json.dumps(payload, indent=2)


def to_text(outcomes) -> str:
    lines = [f"{o.check.family:10s} {o.result.status:12s} {o.check.label}: {o.result.message}" for o in outcomes]
    s = summary(outcomes)
    lines.append(f"{s['ok']} of {s['total']} checks passed")
    return "\n".join(lines)


def to_markdown(outcomes, source: str = "") -> str:
    """A Markdown table, for a CI job summary ($GITHUB_STEP_SUMMARY) or a pull-request comment."""

    def cell(text) -> str:
        return str(text).replace("|", "\\|").replace("\n", " ")

    s = summary(outcomes)
    mark = "✅" if s["not_ok"] == 0 else "❌"
    lines = [f"### {mark} physverify: {s['ok']} of {s['total']} checks passed", ""]
    if source:
        lines += [f"Spec: `{cell(source)}`", ""]
    lines += ["| Family | Status | Check | Observed order | Message |", "|---|---|---|---|---|"]
    for o in outcomes:
        observed = ""
        if isinstance(o.result, OrderResult) and math.isfinite(o.result.fitted):
            observed = f"{o.result.fitted:.2f} (expected {o.result.expected:g})"
        lines.append(
            f"| {cell(o.check.family)} | {cell(o.result.status)} | {cell(o.check.label)} | {observed} | {cell(o.result.message)} |"
        )
    return "\n".join(lines) + "\n"


def _svg_plot(result: OrderResult, width=220, height=150) -> str:
    """Log-log plot of error against step size, with a line of the expected slope."""
    pts = [(h, e) for h, e in zip(result.hs, result.errors) if h > 0 and e > 0 and math.isfinite(e)]
    if len(pts) < 2:
        return ""
    lx = [math.log10(h) for h, _ in pts]
    ly = [math.log10(e) for _, e in pts]
    x0, x1 = min(lx), max(lx)
    y0, y1 = min(ly), max(ly)
    expected_line = []
    if math.isfinite(result.expected):
        # through the finest point, with the expected slope
        yf = ly[-1] if lx[-1] == x0 else ly[lx.index(x0)]
        expected_line = [(x0, yf), (x1, yf + result.expected * (x1 - x0))]
        y0 = min(y0, *[p[1] for p in expected_line])
        y1 = max(y1, *[p[1] for p in expected_line])
    pad = 14
    sx = (width - 2 * pad) / ((x1 - x0) or 1.0)
    sy = (height - 2 * pad) / ((y1 - y0) or 1.0)

    def xy(x, y):
        return f"{pad + (x - x0) * sx:.1f},{height - pad - (y - y0) * sy:.1f}"

    parts = [f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="error against step size, log-log">']
    parts.append(f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" class="frame"/>')
    if expected_line:
        parts.append(f'<polyline points="{xy(*expected_line[0])} {xy(*expected_line[1])}" class="expected"/>')
    parts.append('<polyline points="' + " ".join(xy(x, y) for x, y in zip(lx, ly)) + '" class="observed"/>')
    for x, y in zip(lx, ly):
        cx, cy = xy(x, y).split(",")
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="2.5" class="point"/>')
    parts.append("</svg>")
    return "".join(parts)


_CSS = """
:root { --bg:#ffffff; --fg:#1d1d1f; --muted:#6b6b70; --line:#d9d9de; --ok:#1a7f37; --bad:#b42318; --warn:#9a6700; --accent:#2f5bd3; }
@media (prefers-color-scheme: dark) { :root { --bg:#16171a; --fg:#ececf0; --muted:#a0a0a8; --line:#33343a; --ok:#4ac26b; --bad:#ff7b72; --warn:#d4a72c; --accent:#7aa2ff; } }
body { background:var(--bg); color:var(--fg); font:15px/1.5 system-ui, sans-serif; margin:0 auto; max-width:1100px; padding:24px 16px; }
h1 { font-size:22px; margin:0 0 4px; } p.meta { color:var(--muted); margin:0 0 20px; }
table { border-collapse:collapse; width:100%; } th, td { border-bottom:1px solid var(--line); padding:8px 6px; text-align:left; vertical-align:top; }
th { color:var(--muted); font-weight:600; font-size:13px; }
.status { font-weight:700; white-space:nowrap; } .ok { color:var(--ok); } .bad { color:var(--bad); } .warn { color:var(--warn); }
.wrap { overflow-x:auto; } svg .frame { fill:none; stroke:var(--line); } svg .observed { fill:none; stroke:var(--accent); stroke-width:2; }
svg .expected { fill:none; stroke:var(--muted); stroke-dasharray:4 3; } svg .point { fill:var(--accent); }
td.num { font-variant-numeric:tabular-nums; white-space:nowrap; }
"""


def to_html(outcomes, title: str = "physverify report", source: str = "") -> str:
    from . import __version__

    s = summary(outcomes)
    rows = []
    for o in outcomes:
        r = o.result
        cls = "ok" if r.ok else ("warn" if r.status == "INCONCLUSIVE" else "bad")
        plot = _svg_plot(r) if isinstance(r, OrderResult) else ""
        order = ""
        if isinstance(r, OrderResult) and math.isfinite(r.fitted):
            order = f"{r.fitted:.2f}" + (f" (expected {r.expected:g})" if math.isfinite(r.expected) else "")
        rows.append(
            "<tr>"
            f'<td class="status {cls}">{html.escape(r.status)}</td>'
            f"<td>{html.escape(o.check.family)}</td>"
            f"<td>{html.escape(o.check.label)}</td>"
            f"<td>{html.escape(r.message)}</td>"
            f'<td class="num">{html.escape(order)}</td>'
            f"<td>{plot}</td>"
            "</tr>"
        )
    return (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html.escape(title)}</title><style>{_CSS}</style></head><body>"
        f"<h1>{html.escape(title)}</h1>"
        f'<p class="meta">{s["ok"]} of {s["total"]} checks passed. physverify {html.escape(__version__)}'
        + (f" · {html.escape(source)}" if source else "")
        + ". Plots: error against step size on log-log axes; dashed line has the expected slope.</p>"
        '<div class="wrap"><table><thead><tr><th>Status</th><th>Family</th><th>Check</th><th>Message</th>'
        "<th>Observed order</th><th>Convergence</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div></body></html>\n"
    )
