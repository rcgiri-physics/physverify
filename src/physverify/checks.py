"""Result types shared by every check."""

from __future__ import annotations

import contextvars
import importlib
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

PASS = "PASS"
FAIL = "FAIL"
EXACT = "EXACT"  # error below the noise floor at every resolution
INCONCLUSIVE = "INCONCLUSIVE"
ERROR = "ERROR"  # the code under test raised an exception
SKIP = "SKIP"  # not run (an optional dependency is missing); neither a pass nor a failure

FAMILIES = ("mms", "reference", "invariant", "limit", "patch")


@dataclass
class Result:
    status: str
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status in (PASS, EXACT)

    @property
    def failed(self) -> bool:
        """Neither a pass nor a skip: FAIL, ERROR or INCONCLUSIVE."""
        return self.status not in (PASS, EXACT, SKIP)


@dataclass
class OrderResult(Result):
    expected: float = float("nan")
    fitted: float = float("nan")
    fitted_se: float = float("nan")  # standard error of the fitted order; nan with fewer than three fit points
    hs: tuple = ()
    errors: tuple = ()
    acceptance: str = ""  # the rule a PASS had to meet, in words (reported in the JSON output)


@dataclass
class Check:
    """One runnable check. `family` says which kind of evidence it gives:

    mms        manufactured-solution order study against an independent reference operator
    reference  comparison with an independently written reference solution
    invariant  drift of a conserved quantity as the resolution is refined
    limit      a known limiting case (analytic range, normal-mode frequencies, ...)
    patch      a manufactured solution the scheme should reproduce exactly (to round-off),
               so any error at all is a bug, whatever its order
    """

    family: str
    label: str
    run: Callable[[], Result]
    budget_s: float | None = None  # wall-clock budget; see run_check


class SkipCheck(Exception):
    """Raise inside a check to report SKIP with this message (e.g. an optional dependency is missing)."""


def requires(*modules: str) -> None:
    """Raise SkipCheck unless every module imports, so a missing optional dependency is a SKIP, not a pass."""
    for name in modules:
        try:
            importlib.import_module(name)
        except ImportError as exc:
            raise SkipCheck(f"needs {name}, which is not installed ({exc})") from None


_deadline: contextvars.ContextVar = contextvars.ContextVar("physverify_deadline", default=None)
_notes: contextvars.ContextVar = contextvars.ContextVar("physverify_notes", default=None)


def within_budget(resolutions):
    """Yield the resolutions in order, stopping early when the next one would not finish inside the time budget.

    The cost of the next run is guessed as the last run's time scaled by the ratio of resolutions. The order
    study then fits what it has; fewer than two usable resolutions give INCONCLUSIVE. Outside a budget
    (no `budget_s`) every resolution is yielded.
    """
    resolutions = list(resolutions)
    deadline = _deadline.get()
    prev_n = prev_dt = None
    for i, n in enumerate(resolutions):
        if deadline is not None and prev_dt is not None:
            try:
                scale = max(1.0, float(n) / float(prev_n))
            except (TypeError, ValueError, ZeroDivisionError):
                scale = 1.0
            if time.monotonic() + prev_dt * scale > deadline:
                notes = _notes.get()
                if notes is not None:
                    notes.append(f"time budget: ran {i} of {len(resolutions)} resolutions (up to {prev_n}); "
                                 f"the next would take about {prev_dt * scale:.0f} s")
                return
        start = time.monotonic()
        yield n
        prev_dt, prev_n = time.monotonic() - start, n


def _run(check: Check) -> Result:
    try:
        with np.errstate(all="ignore"):  # a buggy code may overflow; the order check reports non-finite errors
            return check.run()
    except SkipCheck as exc:
        return Result(SKIP, str(exc))
    except Exception as exc:  # the code under test may crash; that is a finding too
        return Result(ERROR, f"{type(exc).__name__}: {exc}")


def run_check(check: Check, budget_s: float | None = None) -> Result:
    """Run one check. With a budget (`check.budget_s`, else `budget_s`), order studies stop adding resolutions
    when the next would overrun it (see `within_budget`), and a check still running at twice the budget is
    reported INCONCLUSIVE so the later checks still run. Python cannot stop a thread, so such a check keeps
    running in the background until the process exits; its result is discarded.
    """
    budget = check.budget_s if check.budget_s is not None else budget_s
    if not budget:
        return _run(check)
    notes: list = []

    def target():
        _deadline.set(time.monotonic() + budget)
        _notes.set(notes)
        box.append(_run(check))

    box: list = []
    worker = threading.Thread(target=contextvars.copy_context().run, args=(target,), daemon=True)
    worker.start()
    worker.join(2 * budget)
    if not box:
        return Result(INCONCLUSIVE, f"did not finish within twice its time budget ({2 * budget:.0f} s); "
                                    "use coarser resolutions or a larger budget")
    result = box[0]
    if notes:
        result.message = (result.message + "; " if result.message else "") + "; ".join(notes)
    return result
