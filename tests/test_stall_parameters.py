"""User-supplied stall settings must be physical before assembly or solve."""
from pathlib import Path
import runpy
import numpy as np
import pytest
from openswing.aero import AnalysisError, FlightCondition, solve_rigid
from openswing.asw import parse_asw

reference_leakage = runpy.run_path('scripts/verify-stall-parameters.py')['reference_leakage']


@pytest.mark.parametrize('lower,upper', [(-1.2,1.2),(-.7,1.3),(.3,1.9)])
@pytest.mark.parametrize('width', [1e-310,1e-100,1e-12,.01,.05,.15,10.,1e12,1e100,1e308])
def test_stall_leakage_and_tangent_against_high_precision_logarithms(lower,upper,width):
    from openswing.aero import _stall_leakage
    values = [-3.,-.01,0.,.01,3.,lower,upper,
              np.nextafter(lower,-np.inf),np.nextafter(upper,np.inf)]
    expected = np.array([reference_leakage(cl,lower,upper,width) for cl in values]).T
    with np.errstate(all='raise'):
        actual = np.array(_stall_leakage(values,lower,upper,width))
    np.testing.assert_allclose(actual,expected,rtol=3e-15,atol=3e-15)


def test_stall_leakage_formula_switch_is_smooth_at_both_sides():
    from openswing.aero import _stall_leakage
    width = .05
    values = [point+offset for point in [-16*width,16*width] for offset in [-1e-10,0,1e-10]]
    expected = np.array([reference_leakage(cl,-1.2,1.2,width) for cl in values]).T
    np.testing.assert_allclose(_stall_leakage(values,-1.2,1.2,width),expected,rtol=3e-14,atol=1e-17)


@pytest.mark.parametrize('upper', [.9, 1.1])
def test_asymmetric_stall_tail_at_zero_lift_is_not_clipped(upper):
    # SA-10's literal asymmetric limits give a small, nonzero leakage at cl=0.
    # An absolute tolerance would hide a log(1+exp(x)) cancellation or clipping
    # regression here; compare both value and tangent to independent 450-digit
    # evaluation using a relative-only gate.
    from openswing.aero import _stall_leakage
    expected = reference_leakage(0., -2., upper, .05)
    actual = _stall_leakage(0., -2., upper, .05)
    assert expected[0] > 0 and expected[1] > 0
    np.testing.assert_allclose(actual, expected, rtol=5e-15, atol=0.)


@pytest.mark.parametrize('stall', [True, False])
@pytest.mark.parametrize('name,value,message', [
    *[('stall_factor', v, 'leakage factor') for v in [-1, np.nan, np.inf, None, True, '40', 10**400]],
    *[('stall_width', v, 'transition width') for v in [0, -1, np.nan, np.inf, None, False, '.05', 10**400]],
])
def test_invalid_stall_parameters_rejected_even_when_disabled(stall, name, value, message):
    model = parse_asw(Path('examples/stall-branch.asw').read_text())
    condition = FlightCondition(stall=stall, **{name:value})
    with pytest.raises(AnalysisError, match=message):
        solve_rigid(model, condition, panels=4)


def test_zero_factor_and_disabled_stall_recover_the_same_finite_wing():
    model = parse_asw(Path('examples/stall-branch.asw').read_text())
    conditions = [FlightCondition(alpha=25, mach=0, stall_factor=0, stall_width=.15),
                  FlightCondition(alpha=25, mach=0, stall=False, stall_factor=80, stall_width=.01)]
    results = [solve_rigid(model, condition, panels=12) for condition in conditions]
    for key in ['CL', 'CD', 'Cm', 'force', 'moment']:
        np.testing.assert_allclose(results[0][key], results[1][key], rtol=2e-10, atol=1e-9)
