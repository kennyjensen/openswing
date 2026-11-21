"""Full trim borders against independent physical residual differences."""
from dataclasses import replace
import numpy as np
import pytest

from openswing.source_airflow import SourceAirflowNetwork
from openswing.operating import OperatingConstraint
from openswing.structured_static import load_kinematic_constraints, acceleration_load_constraints
from test_source_static_mechanical_tangent import fixture
from test_source_joints import trial


@pytest.mark.parametrize('frozen',[False,True])
def test_full_trim_border_and_all_matrix_columns_match_complete_residual(frozen):
    original,_=fixture('airflow')
    # These need not define a solvable trim: test the full derivative operator,
    # including zero sensitivities. Put flight path between load rows to catch
    # assumptions that the trim border has six contiguous force/moment rows.
    targets=[('alpha','force.z'),('attitude.elevation','flight_path'),
             ('attitude.bank','force.y'),('speed','force.x'),('beta','moment.x'),
             ('attitude.heading','moment.y'),('rates.z','moment.z')]
    condition=replace(original.condition,freeze_influences=frozen,
                      rates=[.03,-.02,.01],attitude=[4.,6.,-3.])
    n=SourceAirflowNetwork(original.model,4,condition,original.gravity,[],steady_trim=True,
        operating_constraints=[OperatingConstraint(variable,quantity) for variable,quantity in targets])
    x=trial(n)
    assert load_kinematic_constraints(n) and not acceleration_load_constraints(n)
    baseline=n.residual(x,.65).copy()
    np.testing.assert_allclose(n.residual(x,.65,detail=True)[0],baseline,rtol=1e-13,atol=1e-13)
    before=n.nfev
    matrix=n.jacobian(x,.65)
    assert n.geometry_derivative_diagnostics.get('geometry_columns')==6*n.nn,n.geometry_derivative_diagnostics
    assert n.circulation_derivative_diagnostics['method']=='direct fixed-geometry blocks'
    assert n.nfev-before<n.size
    errors=[]
    for column in range(n.size):
        h=3e-6*max(1.,abs(x[column]))
        p,m=x.copy(),x.copy();p[column]+=h;m[column]-=h
        expected=(n.residual(p,.65,detail=True)[0]-n.residual(m,.65,detail=True)[0])/(2*h)
        errors.append(float(np.max(abs(matrix[:,column]-expected)/(1+abs(expected)))))
    assert max(errors)<2e-6, (max(errors),int(np.argmax(errors)))
    # Flight path remains a real equation: only its pose/circulation partials
    # vanish. Its operating-angle partial must survive in the full border.
    row=n.operating_start+1
    np.testing.assert_array_equal(matrix[row,:n.operating_start],0.)
    assert np.linalg.norm(matrix[row,n.operating_start:])>0
    np.testing.assert_array_equal(n.residual(x,.65),baseline)
    assert n.iteration_fields is None and n.tangent_influences is None


def test_other_operating_targets_retain_complete_residual_fallback():
    original,_=fixture('airflow')
    n=SourceAirflowNetwork(original.model,4,original.condition,original.gravity,[],steady_trim=True,
        operating_constraints=[OperatingConstraint('alpha','lift')])
    x=trial(n)
    assert not load_kinematic_constraints(n)
    expected=n.jacobian(x,.65,_direct_geometry=False,_direct_circulation=False)
    automatic=n.jacobian(x,.65)
    np.testing.assert_array_equal(automatic,expected)
    actual=n.jacobian(x,.65,_direct_geometry=True)
    assert 'load/flight-path constraints' in n.geometry_derivative_diagnostics['fallback']
    np.testing.assert_array_equal(actual,expected)
    assert n.iteration_fields is None and n.tangent_influences is None
