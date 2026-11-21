"""The provisional allowance must not turn invalid or missing physics green."""
from copy import deepcopy
import importlib.util
import math
from pathlib import Path

import pytest


path = Path(__file__).resolve().parents[1] / "scripts/isae_acceptance.py"
spec = importlib.util.spec_from_file_location("isae_acceptance", path)
acceptance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acceptance)


def strict_result(predicted=1.02, expected=1.0, tolerance=5e-7, passed=False, **fields):
    return {
        "status": "computed", "numerical_pass": True,
        "reference_match": passed,
        "reference_checks": [dict(name="CL", predicted=predicted, expected=expected,
                                  tolerance=tolerance, passed=passed, **fields)],
        "numerical_checks": [{"name": "circulation residual", "tolerance": 1e-8,
                              "value": 1e-12, "passed": True}],
        "output_accounting": {"required": 1, "reported": 1, "finite": 1,
                              "unavailable": 0, "numerically_valid": 1,
                              "passed": int(passed), "missing": 0},
    }


@pytest.mark.parametrize("predicted, expected, passes", [
    (1.03, 1.0, True), (0.97, 1.0, True),
    (1.0300000001, 1.0, False), (0.9699999999, 1.0, False),
    (-1.03, -1.0, True), (-0.97, -1.0, True),
    (-1.0300000001, -1.0, False),
])
def test_inclusive_three_percent_with_both_reference_signs(predicted, expected, passes):
    view = acceptance.apply_reference_acceptance(strict_result(predicted, expected), relative_tolerance=.03)
    check = view["reference_checks"][0]
    assert check["passed"] is passes
    assert view["reference_match"] is passes
    assert check["effective_tolerance"] == .03
    assert check["tolerance"] == check["original_tolerance"] == 5e-7
    assert check["strict_passed"] is False


@pytest.mark.parametrize("predicted, expected, passes", [
    (1.05, 1., True), (.95, 1., True),
    (1.0500000001, 1., False), (.9499999999, 1., False),
    (-1.05, -1., True), (-.95, -1., True),
    (-1.0500000001, -1., False), (-.9499999999, -1., False),
])
def test_default_five_percent_inclusive_boundary(predicted, expected, passes):
    view = acceptance.apply_reference_acceptance(strict_result(predicted, expected))
    assert view['reference_match'] is passes
    assert view['output_accounting']['passed'] == int(passes)
    assert view['reference_checks'][0]['effective_tolerance'] == .05


def test_policy_does_not_mutate_frozen_results_or_solver_checks():
    raw = strict_result()
    snapshot = deepcopy(raw)
    view = acceptance.apply_reference_acceptance(raw)
    assert raw == snapshot
    assert view["numerical_checks"] == raw["numerical_checks"]
    assert view["strict_output_accounting"] == raw["output_accounting"]
    assert view["strict_reference_match"] is False
    assert view["output_accounting"]["passed"] == 1
    view["numerical_checks"][0]["tolerance"] = 1
    assert raw == snapshot


@pytest.mark.parametrize("status, numerical", [
    ("timeout", False), ("unsupported", False), ("adapter_contract_failure", True),
    ("computed", False),
])
def test_bad_status_or_numerical_failure_cannot_be_promoted(status, numerical):
    raw = strict_result()
    raw.update(status=status, numerical_pass=numerical)
    view = acceptance.apply_reference_acceptance(raw)
    assert view["reference_match"] is False
    assert view["reference_checks"][0]["passed"] is False
    assert view["output_accounting"]["passed"] == 0
    assert view["status"] == status
    assert view["numerical_pass"] is numerical


@pytest.mark.parametrize("field, value", [
    ("predicted", None), ("predicted", float("nan")), ("predicted", float("inf")),
    ("expected", None), ("expected", float("-inf")), ("tolerance", None),
    ("tolerance", -1), ("tolerance", float("inf")),
    ("predicted", True), ("expected", True), ("tolerance", False),
])
def test_unavailable_invalid_and_boolean_values_are_not_promoted(field, value):
    raw = strict_result()
    raw["reference_checks"][0][field] = value
    view = acceptance.apply_reference_acceptance(raw)
    assert view["reference_checks"][0]["passed"] is False
    assert view["reference_match"] is False


@pytest.mark.parametrize("fields", [
    {"kind": "discrete"}, {"value_kind": "count"}, {"is_discrete": True},
    {"relative_tolerance_allowed": False}, {"comparison": "=="},
])
def test_discrete_checks_keep_original_outcome(fields):
    view = acceptance.apply_reference_acceptance(strict_result(**fields))
    assert view["reference_checks"][0]["passed"] is False
    assert view["reference_checks"][0]["effective_tolerance"] == 5e-7


@pytest.mark.parametrize("reference", [0., 1e-12, -1e-12, 1e-8, -1e-8])
def test_zero_and_tiny_references_keep_the_original_absolute_gate(reference):
    raw = strict_result(reference * 1.02 + 1e-20, reference, 1e-22)
    view = acceptance.apply_reference_acceptance(raw)
    assert view["reference_checks"][0]["passed"] is False
    assert view["reference_checks"][0]["effective_tolerance"] == 1e-22
    assert view["reference_checks"][0]["acceptance_basis"] == "tiny_reference_original_strict"


def test_just_above_tiny_threshold_uses_relative_error():
    raw = strict_result(1.02e-8, 1.00000001e-8, 1e-22)
    assert acceptance.apply_reference_acceptance(raw)["reference_match"] is True


def test_wider_original_absolute_interval_is_never_narrowed():
    raw = strict_result(1.04, 1., .05, passed=True)
    view = acceptance.apply_reference_acceptance(raw)
    assert view["reference_match"] is True
    assert view["reference_checks"][0]["effective_tolerance"] == .05


def test_tightening_and_restoring_strict_policy_use_the_same_raw_evidence():
    raw = strict_result()
    assert acceptance.apply_reference_acceptance(raw)["reference_match"] is True
    assert acceptance.apply_reference_acceptance(raw, relative_tolerance=.01)["reference_match"] is False
    view = acceptance.apply_reference_acceptance(raw, relative_tolerance=0)
    assert view["reference_match"] is False
    assert view["output_accounting"] == raw["output_accounting"]
    assert view["reference_acceptance_policy"]["name"] == "original_strict"


def test_decimal_reference_center_controls_boundary_and_preserves_source_fields():
    raw = strict_result(1.03, 1., 5e-7, exact_decimal_expected="1.000000",
                        exact_decimal_tolerance="0.0000005")
    view = acceptance.apply_reference_acceptance(raw)
    check = view["reference_checks"][0]
    assert check["passed"] is True
    assert check["exact_decimal_expected"] == "1.000000"
    assert check["exact_decimal_tolerance"] == "0.0000005"
    assert check["exact_decimal_effective_tolerance"] == "0.05000000"


def test_zero_allowance_preserves_existing_decimal_boundary_pass():
    raw = strict_result(1.0000005, 1., 5e-7, passed=True,
                        exact_decimal_expected="1.000000", exact_decimal_tolerance="0.0000005")
    assert abs(raw["reference_checks"][0]["predicted"] - 1.) > 5e-7
    view = acceptance.apply_reference_acceptance(raw, relative_tolerance=0)
    assert view["reference_match"] is True
    assert view["output_accounting"] == raw["output_accounting"]


@pytest.mark.parametrize("fields", [
    {"exact_decimal_expected": "1"},
    {"exact_decimal_expected": "NaN", "exact_decimal_tolerance": "0.000001"},
    {"exact_decimal_expected": "1", "exact_decimal_tolerance": "-1"},
    {"exact_decimal_expected": "garbage", "exact_decimal_tolerance": "0.000001"},
])
def test_invalid_native_decimal_fields_cannot_gain_pass(fields):
    view = acceptance.apply_reference_acceptance(strict_result(**fields))
    assert view["reference_match"] is False


def test_missing_reference_output_never_becomes_full_match():
    raw = strict_result()
    raw["output_accounting"].update(required=2, missing=1)
    view = acceptance.apply_reference_acceptance(raw)
    assert view["reference_checks"][0]["passed"] is True
    assert view["reference_match"] is False
    assert view["output_accounting"]["missing"] == 1


@pytest.mark.parametrize("parameter, value", [
    ("relative_tolerance", -1), ("relative_tolerance", float("nan")),
    ("relative_tolerance", float("inf")), ("relative_tolerance", True),
    ("tiny_reference", -1), ("tiny_reference", None),
])
def test_policy_parameters_must_be_valid(parameter, value):
    with pytest.raises(ValueError, match=parameter):
        acceptance.apply_reference_acceptance(strict_result(), **{parameter: value})


def test_policy_view_cannot_be_mistaken_for_original_strict_evidence():
    view = acceptance.apply_reference_acceptance(strict_result())
    with pytest.raises(ValueError, match="original strict result"):
        acceptance.apply_reference_acceptance(view, relative_tolerance=.01)


@pytest.mark.parametrize("predicted, expected", [
    (1.03, 1.0), (0.97, 1.0), (-1.03, -1.0), (-0.97, -1.0),
])
def test_inclusive_relative_boundary_when_original_strict_interval_has_same_width(
        predicted, expected):
    raw = strict_result(predicted, expected, .03, passed=False, comparison="<")
    snapshot = deepcopy(raw)
    view = acceptance.apply_reference_acceptance(raw, relative_tolerance=.03)
    check = view["reference_checks"][0]
    assert check["passed"] is True
    assert view["reference_match"] is True
    assert check["strict_passed"] is False
    assert check["effective_tolerance"] == .03
    assert check["comparison"] == "<"
    assert check["acceptance_comparison"] == "<="
    assert raw == snapshot
    # Restoring strict acceptance retains the original open boundary.
    assert acceptance.apply_reference_acceptance(raw, relative_tolerance=0)["reference_match"] is False
