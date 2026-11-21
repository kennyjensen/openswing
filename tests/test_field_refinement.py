"""Field derivative resolution against exact functions and physical equations."""
import numpy as np
import pytest
from openswing.geometry_tangent import refined_field_column,GeometryDerivativeUnresolved


def prepare(function,h):return [function(f*h) for f in (1,-1,2,-2)]


@pytest.mark.parametrize('units',[.01,1.,3.280839895,1000.])
def test_narrow_smooth_fields_converge_in_physical_units(units):
    speed=30*units;h=3e-4;calls=[]
    def field(x):
        calls.append(x)
        return {'cp':speed*np.array([1/(1+x/.003),np.sin(x/.004),np.exp(x/.002)]),
                'circulation_residual':np.array([np.sin(x/.001)]),'engine':np.empty((0,3))}
    values=prepare(field,h)
    actual,report=refined_field_column(field,h,values,speed)
    expected=speed*np.array([-1/.003,1/.004,1/.002])
    np.testing.assert_allclose(actual['cp'],expected,atol=1e-8*speed,rtol=2e-8)
    np.testing.assert_allclose(actual['circulation_residual'],[1000.],atol=2e-8,rtol=2e-8)
    assert report['refinements']>=2 and report['error_estimate']<=2e-8
    assert len(calls)==4+4*report['refinements']


def test_zero_and_linear_columns_need_no_additional_field_evaluations():
    h=1e-5;calls=[]
    def field(x):
        calls.append(x)
        return {'cp':np.array([3.,2.*x]),'circulation_residual':np.array([-7.*x])}
    values=prepare(field,h);actual,report=refined_field_column(field,h,values,30.)
    np.testing.assert_array_equal(actual['cp'],[0.,2.])
    np.testing.assert_allclose(actual['circulation_residual'],[-7.],atol=2e-15,rtol=0.)
    assert report['refinements']==0 and len(calls)==4


def test_fifth_order_error_is_not_missed_when_the_third_derivative_is_zero():
    h=1e-5
    def field(x):return {'cp':np.array([x+2e15*x**5]),'circulation_residual':np.array([0.])}
    actual,report=refined_field_column(field,h,prepare(field,h),1.)
    np.testing.assert_allclose(actual['cp'],[1.],atol=2e-8,rtol=0.)
    assert report['refinements']>0


def test_unresolved_or_interrupted_derivatives_are_not_silently_accepted():
    h=1e-5
    def discontinuous(x):return {'cp':np.array([np.sign(x)])}
    with pytest.raises(GeometryDerivativeUnresolved,match='did not resolve'):
        refined_field_column(discontinuous,h,prepare(discontinuous,h),30.)
    values=prepare(discontinuous,h)
    def invalid(x):raise ValueError('physical branch changed')
    with pytest.raises(ValueError,match='physical branch changed'):
        refined_field_column(invalid,h,values,30.)


def test_smooth_field_can_resolve_beyond_four_refinements_without_relaxing_accuracy():
    # A narrow smooth field can enter its convergent regime late. Its exact
    # derivative is 1, independent of the numerical acceptance estimator.
    h=1e-3;calls=[]
    def field(x):
        calls.append(x)
        return {'cp':np.array([x+1000*h*(x/h)**7])}
    values=prepare(field,h)
    with pytest.raises(GeometryDerivativeUnresolved,match='did not resolve'):
        refined_field_column(field,h,values,1.,max_refinements=4)
    calls.clear()
    actual,report=refined_field_column(field,h,values,1.)
    np.testing.assert_allclose(actual['cp'],[1.],atol=2e-8,rtol=0.)
    assert 4<report['refinements']<=6
    assert report['error_estimate']<=2e-8
    assert len(calls)==4*report['refinements']<=24
