"""Complete source Newton matrices; physical pose columns remain unfrozen."""
import numpy as np
import pytest

from openswing.mechanical_tangent import MechanicalDerivativeUnavailable
from openswing.circulation_tangent import CirculationDerivativeUnavailable
from test_source_static_mechanical_tangent import fixture


@pytest.mark.parametrize('kind',['zero','section','dynamic','coupled','airflow','fuselage'])
def test_complete_matrix_matches_scalar_physical_residual_columns(kind):
    n,x=fixture(kind)
    before=n.residual(x,.6).copy()
    count=n.nfev
    actual=n.jacobian(x,.6,_direct_geometry=False)
    calls=n.nfev-count
    assert n.mechanical_derivative_diagnostics['method'].startswith('direct source')
    if n.ng:assert n.circulation_derivative_diagnostics['method']=='direct fixed-geometry blocks'
    count=n.nfev
    expected=n.jacobian(x,.6,_direct_mechanics=False,_direct_circulation=False,_direct_geometry=False)
    original_calls=n.nfev-count
    assert calls<original_calls-5
    assert np.max(abs(actual-expected)/(1+abs(expected)))<2e-6
    # Complete geometry columns must include the original moving field terms.
    np.testing.assert_allclose(actual[:,:6*n.nn],expected[:,:6*n.nn],rtol=0,atol=1e-12)
    np.testing.assert_array_equal(n.residual(x,.6),before)
    assert n.iteration_fields is None and n.tangent_influences is None
    assert n.analytic_mechanics is False


@pytest.mark.parametrize('kind',['section','airflow'])
def test_sparse_full_matrix_has_identical_columns_and_no_dropped_small_entries(kind):
    n,x=fixture(kind)
    dense=n.jacobian(x,.7)
    sparse=n.jacobian(x,.7,_sparse=True)
    np.testing.assert_array_equal(sparse.toarray(),dense)


def test_unavailable_helpers_keep_full_residual_fallback(monkeypatch):
    import openswing.mechanical_tangent as mechanical
    import openswing.circulation_tangent as flow
    n,x=fixture('airflow')
    expected=n.jacobian(x,.6,_direct_mechanics=False,_direct_circulation=False)
    def no_mechanics(*args,**kwargs):raise MechanicalDerivativeUnavailable('unavailable mechanics')
    def no_flow(*args,**kwargs):raise CirculationDerivativeUnavailable('unavailable circulation')
    monkeypatch.setattr(mechanical,'source_network_mechanical_columns',no_mechanics)
    monkeypatch.setattr(flow,'circulation_columns',no_flow)
    actual=n.jacobian(x,.6)
    assert n.mechanical_derivative_diagnostics['fallback']=='unavailable mechanics'
    assert n.circulation_derivative_diagnostics['fallback']=='unavailable circulation'
    np.testing.assert_array_equal(actual,expected)
    assert n.iteration_fields is None and n.tangent_influences is None


def test_unknown_rate_law_cannot_inherit_direct_mechanical_columns():
    n,x=fixture('dynamic')
    original=n.constitutive_motion
    n.constitutive_motion=lambda *args,**kwargs:original(*args,**kwargs)
    expected=n.jacobian(x,.6,_direct_mechanics=False,_direct_circulation=False)
    actual=n.jacobian(x,.6)
    assert n.mechanical_derivative_diagnostics['fallback']=='Unknown source rate-dependent constitutive law.'
    np.testing.assert_array_equal(actual,expected)


def test_unavailable_geometry_keeps_the_complete_physical_fallback(monkeypatch):
    import openswing.geometry_tangent as geometry
    n,x=fixture('airflow')
    expected=n.jacobian(x,.6,_direct_geometry=False)
    def unavailable(*args,**kwargs):
        raise geometry.GeometryDerivativeUnavailable('deliberate geometry boundary')
    monkeypatch.setattr(geometry,'geometry_columns',unavailable)
    actual=n.jacobian(x,.6,_direct_geometry=True)
    assert n.geometry_derivative_diagnostics['fallback']=='deliberate geometry boundary'
    np.testing.assert_array_equal(actual,expected)
    assert n.iteration_fields is None and n.tangent_influences is None


@pytest.mark.parametrize('kind',['coupled','airflow'])
@pytest.mark.parametrize('frozen',[False,True])
def test_source_complete_geometry_includes_moving_fields_at_loaded_poses(kind,frozen):
    from dataclasses import replace
    n,x=fixture(kind)
    condition=replace(n.condition,freeze_influences=frozen)
    if kind=='airflow':
        condition=replace(condition,rates=[.1,-.2,.3],acceleration=[.2,-.1,.3],
                          angular_acceleration=[-.1,.2,.1])
    n=type(n)(n.model,n.panels,condition,n.gravity,[])
    original=n.residual(x,.6).copy()
    before=n.nfev
    actual=n.jacobian(x,.6,_direct_geometry=True)
    calls=n.nfev-before
    assert n.geometry_derivative_diagnostics['geometry_columns']==6*n.nn
    assert calls<6*n.nn
    # Independently centered complete residuals, with all physical fields
    # recomputed. No midpoint structural derivative is valid for these laws.
    for j in range(6*n.nn):
        h=3e-6*max(1.,abs(x[j]));p,m=x.copy(),x.copy();p[j]+=h;m[j]-=h
        expected=(n.residual(p,.6)-n.residual(m,.6))/(2*h)
        assert np.max(abs(actual[:,j]-expected)/(1+abs(expected)))<2e-6
    assert n.analytic_mechanics is False
    np.testing.assert_array_equal(n.residual(x,.6),original)
    assert n.iteration_fields is None and n.tangent_influences is None
