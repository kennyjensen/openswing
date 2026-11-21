"""Independent limiting laws include the selected influence direction."""
import math
import runpy
import pytest

STUDY=runpy.run_path('scripts/verify-frozen-stall.py')
section=STUDY['section']


@pytest.mark.parametrize('frozen',[True,False],ids=['frozen','current'])
@pytest.mark.parametrize('control',[-44.,-40.,-32.,0.,4.,44.])
def test_asymmetric_stall_and_both_control_and_state_derivatives_in_infinite_span_limit(control,frozen):
    STUDY['check'](control,frozen)


def test_frozen_control_rotation_and_incidence_are_distinct_physical_changes():
    alpha,theta=math.radians(12),math.radians(7.7)
    frozen=section(alpha,theta,frozen=True,factor=0)
    current=section(alpha,theta,frozen=False,factor=0)
    assert frozen['CL']==pytest.approx(5.77*math.sin(alpha+theta)/math.cos(theta),rel=2e-15)
    assert current['CL']==pytest.approx(5.77*math.tan(alpha+theta),rel=2e-15)
    # Undo the fixed-base-axis drag transport to compare the actual CL slopes.
    frozen_alpha=frozen['alpha']['CL']-frozen['CD']
    frozen_theta=frozen['control']['CL']*5.77/.071
    assert frozen_theta-frozen_alpha==pytest.approx(frozen['CL']*math.tan(theta),rel=3e-14)
    current_alpha=current['alpha']['CL']-current['CD']
    assert current['control']['CL']*5.77/.071==pytest.approx(current_alpha,rel=3e-15)


def test_historical_stall_fixture_retains_its_declared_current_influences():
    old=runpy.run_path('scripts/verify-stall-parameters.py')
    actual=old['compute'](dict(alpha=25.,factor=40.,width=.05,span=590000.,panels=16))
    expected=old['reference'](25.,40.,.05)
    assert actual['condition']['freeze_influences'] is False
    assert max(abs(actual['coefficients'][k]-expected[k]) for k in ('CL','CD'))<1e-4
