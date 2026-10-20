"""physverify: verification checks for physics simulation code."""

from .checks import Check, OrderResult, Result
from .mms import ManufacturedODE, mms_order_study, zero_source
from .order import check_order, fit_order, pairwise_orders
from .order import check_exact
from .studies import invariant_study, ode_checks, patch_study, reference_study

__version__ = "0.3.0"

__all__ = [
    "Check",
    "ManufacturedODE",
    "OrderResult",
    "Result",
    "check_exact",
    "check_order",
    "fit_order",
    "invariant_study",
    "mms_order_study",
    "ode_checks",
    "pairwise_orders",
    "patch_study",
    "reference_study",
    "zero_source",
]
