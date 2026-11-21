"""Provisional reference-error acceptance, separate from solver validity.

Apply this only after the runner's strict ``checked_result`` assessment.  The
original result and printed-precision comparisons remain available unchanged;
the returned report view may accept continuous reference outputs within a
configurable relative error.  Solver checks and adapter contracts are not
reassessed or relaxed here.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import math


DEFAULT_RELATIVE_TOLERANCE = 0.05
DEFAULT_TINY_REFERENCE = 1e-8
_DISCRETE_KINDS = frozenset({"boolean", "discrete", "integer", "count", "exact"})


def _finite_number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def reference_acceptance_policy(*, relative_tolerance=DEFAULT_RELATIVE_TOLERANCE,
                                tiny_reference=DEFAULT_TINY_REFERENCE):
    """Return serializable policy metadata; zero relative tolerance is strict."""
    for name, value in (("relative_tolerance", relative_tolerance),
                        ("tiny_reference", tiny_reference)):
        if not _finite_number(value) or value < 0:
            raise ValueError(name + " must be a finite nonnegative number")
    return {
        "name": "provisional_relative_reference_error" if relative_tolerance else "original_strict",
        "version": 1,
        "relative_tolerance": float(relative_tolerance),
        "tiny_reference": float(tiny_reference),
        "scope": "continuous reference_checks only; numerical checks and contracts unchanged",
        "effective_tolerance": "max(original absolute tolerance, relative_tolerance * abs(reference))",
        "tiny_reference_rule": "abs(reference) <= tiny_reference retains original strict comparison",
        "relative_comparison": "<=",
        "strict_results_retained": True,
    }


def _reference_decimals(check):
    """Use original decimal centers where the native contract supplies them."""
    x, y, tolerance = (check.get(key) for key in ("predicted", "expected", "tolerance"))
    if not all(_finite_number(value) for value in (x, y, tolerance)) or tolerance < 0:
        return None
    has_exact = "exact_decimal_expected" in check or "exact_decimal_tolerance" in check
    try:
        predicted = Decimal(str(x))
        expected = Decimal(check["exact_decimal_expected"]) if has_exact else Decimal(str(y))
        absolute = Decimal(check["exact_decimal_tolerance"]) if has_exact else Decimal(str(tolerance))
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None
    if not expected.is_finite() or not absolute.is_finite() or absolute < 0:
        return None
    return predicted, expected, absolute


def _json_float(value):
    value = float(value)
    return value if math.isfinite(value) else None


def apply_reference_acceptance(result, *, relative_tolerance=DEFAULT_RELATIVE_TOLERANCE,
                               tiny_reference=DEFAULT_TINY_REFERENCE):
    """Return a report view of an already strictly assessed adapter result.

    ``tolerance``, ``comparison``, source decimal fields and numerical checks
    are unchanged.  Each reference check gains ``strict_passed``,
    ``original_tolerance``, ``effective_tolerance`` and error-policy metadata.
    Overall strict accounting is saved separately.  Unavailable, malformed,
    discrete and numerically invalid results cannot gain a pass.

    For an eligible continuous reference, an existing strict pass is retained;
    otherwise the additional inclusive relative-error allowance may pass it.
    The declared ST-5 per-check additive rule retains printed precision in
    addition to relative error, including tiny values; other checks keep the
    unchanged maximum rule. ``relative_tolerance=0`` uses the original strict
    outcome exactly, including native decimal boundary behavior.

    Always call with the strict result, including when changing the policy;
    this deliberately rejects reapplying a policy to an already modified view.
    """
    policy = reference_acceptance_policy(relative_tolerance=relative_tolerance,
                                         tiny_reference=tiny_reference)
    if "reference_acceptance_policy" in result:
        raise ValueError("Apply reference acceptance to the original strict result, not a policy view")
    view = deepcopy(result)
    view["reference_acceptance_policy"] = policy
    view["strict_reference_match"] = result.get("reference_match") is True
    view["strict_output_accounting"] = deepcopy(result.get("output_accounting", {}))
    numerical = result.get("numerical_pass", result.get("numerical_passed", False)) is True
    valid_result = result.get("status") == "computed" and numerical
    relative = Decimal(str(relative_tolerance))
    tiny = Decimal(str(tiny_reference))
    checks = view.get("reference_checks", [])

    for check in checks:
        strict = check.get("passed") is True
        check.update(strict_passed=strict,
                     original_tolerance=check.get("tolerance"),
                     effective_tolerance=check.get("tolerance"),
                     acceptance_comparison=check.get("comparison", "<="),
                     acceptance_basis="original_strict",
                     relative_error=None)
        numbers = _reference_decimals(check)
        discrete = (check.get("is_discrete") is True
                    or check.get("kind") in _DISCRETE_KINDS
                    or check.get("value_kind") in _DISCRETE_KINDS
                    or check.get("relative_tolerance_allowed") is False
                    or check.get("comparison", "<=") not in ("<", "<="))
        if numbers is None or discrete:
            # The strict assessor controls exact/discrete comparisons.  Their
            # values are never interpreted as continuous error budgets here.
            check["acceptance_basis"] = "ineligible_or_unavailable"
            continue
        predicted, expected, original = numbers
        error = abs(predicted - expected)
        magnitude = abs(expected)
        check["relative_error"] = _json_float(error / magnitude) if magnitude else None
        additive = check.get("relative_allowance_rule") == "add_printed_precision"
        if magnitude <= tiny and not additive:
            check["acceptance_basis"] = "tiny_reference_original_strict"
            continue
        if not relative:
            continue
        relative_limit = relative * magnitude
        effective = original + relative_limit if additive else max(original, relative_limit)
        check["effective_tolerance"] = _json_float(effective)
        check["acceptance_basis"] = "relative_reference_error" if relative_limit >= original else "original_strict"
        if additive:
            check["acceptance_basis"] = "declared_relative_plus_printed_precision"
            check["acceptance_comparison"] = "<="
            if valid_result:
                check["passed"] = strict or error <= effective
        if "exact_decimal_expected" in check:
            check["exact_decimal_effective_tolerance"] = str(effective)
        # Preserve strict operators when their original interval is wider.
        # The additional relative allowance is inclusive at its boundary.
        if relative_limit >= original:
            check["acceptance_comparison"] = "<="
        if valid_result and relative_limit >= original and not additive:
            check["passed"] = strict or error <= relative_limit

    accounting = view.get("output_accounting", {})
    complete = (bool(checks)
                and accounting.get("required") == len(checks)
                and accounting.get("missing", 0) == 0
                and len({check.get("name") for check in checks}) == len(checks))
    view["reference_match"] = bool(valid_result and complete and
                                    all(check.get("passed") is True for check in checks))
    if "output_accounting" in view:
        view["output_accounting"]["passed"] = (
            sum(check.get("passed") is True for check in checks) if valid_result else 0)
    return view
