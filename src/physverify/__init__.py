"""physverify: verification checks for physics simulation code."""

from .checks import Check, OrderResult, Result, SkipCheck, requires
from .mms import ManufacturedODE, mms_order_study, zero_source
from .order import check_order, fit_order, pairwise_orders
from .order import check_exact
from .studies import invariant_study, ode_checks, patch_study, reference_study

__version__ = "0.7.0"

__all__ = [
    "Check",
    "ManufacturedODE",
    "OrderResult",
    "Result",
    "SkipCheck",
    "check_exact",
    "check_order",
    "fit_order",
    "invariant_study",
    "mms_order_study",
    "ode_checks",
    "pairwise_orders",
    "requires",
    "patch_study",
    "reference_study",
    "zero_source",
]
