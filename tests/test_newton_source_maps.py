"""Newton's retained source derivatives and original physical acceptance."""
import numpy as np
import pytest
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.operating import time_load_constraints
from openswing.geometry_tangent import geometry_columns
from openswing.tangent_influences import TangentInfluences
from test_direct_circulation import model_for,state_for


CASES=[('wing-body',{'ground_effect':1},.37,'free'),
       ('stepped-wing-body',{'ground_effect':-1},1.,'fixed'),
       ('powered',{'powers':{1:7}},.6,'free'),
       ('dae',{},.25,'fixed')]


def fixture(example,extra,factor,frame):
    n=StaticNetwork(model_for(example),4,FlightCondition(speed=30,alpha=7,beta=3,mach=.2,
        position_earth=[0,0,30],**extra),None,[],
        operating_constraints=time_load_constraints('prescribed' if frame=='fixed' else frame))
    n._frequency_local_geometry=True
    return n,state_for(n,.3)


@pytest.mark.parametrize('example,extra,factor,frame',CASES)
def test_retained_fields_preserve_other_columns_and_refine_to_physical_tangent(example,extra,factor,frame,monkeypatch):
    import openswing.geometry_tangent as module
    n,x=fixture(example,extra,factor,frame);before=n.residual(x,factor)
    actual=n.jacobian(x,factor)
    report=n.geometry_derivative_diagnostics
    assert report['direct_vortex_queries']>0 and report['direct_volume_queries']>0
    assert report['difference_order']==1
    original=module.geometry_columns
    def no_maps(*args,**kwargs):
        kwargs.update(_direct_vortex=False,_direct_volume=False)
        return original(*args,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(module,'geometry_columns',no_maps)
        reference=n.jacobian(x,factor)
    np.testing.assert_array_equal(actual[:,6*n.nn:],reference[:,6*n.nn:])
    n.tangent_influences=TangentInfluences(local_geometry=True)
    try:
        # Refine the same derivative path used by StaticNetwork.jacobian.
        # Disabling its direct geometry/structural blocks here would compare
        # different approximations instead of refining the Newton stencil.
        fine,fine_report=geometry_columns(n,lambda d:n.residual(x+d,factor),lambda d:x+d,
            np.maximum(1.,abs(x)),step=3e-7,factor=factor,difference_order=1,
            _direct_vortex=True,_direct_volume=True,_nodewise_state=True,
            _direct_geometry=True,_direct_structural=True)
    finally:n.tangent_influences=None;n.aero_key=None
    assert fine_report['direct_geometry_columns']==report['direct_geometry_columns']
    assert fine_report['structural_geometry']['method']==report['structural_geometry']['method']
    expected=[]
    # Independent complete nonlinear residual differences, including both
    # geometry and all external loads, at every geometry column in this model.
    for j in range(6*n.nn):
        h=3e-6*max(1.,abs(x[j]));d=np.zeros(n.size);d[j]=h
        values=[n.residual(x+k*d,factor) for k in [1,-1,2,-2]]
        expected.append((8*(values[0]-values[1])-(values[2]-values[3]))/(12*h))
    expected=np.array(expected).T
    error=lambda m:np.max(abs(m-expected)/(1+abs(expected)))
    coarse=error(actual[:,:6*n.nn]);refined=error(fine.toarray())
    # The established first-order Newton accuracy/refinement gates. These
    # columns are not represented as fourth-order physical Bode derivatives.
    # On the added synthetic coarse DAE fixture, the old forward stencil
    # already misses2e-5 by0.00694. Keep that observation; require this
    # derivative to improve the original accuracy and to refine at the
    # unchanged first-order rate. The established wing/body gate is kept.
    baseline_error=error(reference[:,:6*n.nn])
    assert coarse<=baseline_error+2e-9
    if example!='dae':assert max(coarse,baseline_error)<2e-5
    assert refined<max(.5*coarse,2e-9)
    np.testing.assert_array_equal(n.residual(x,factor),before)
    assert n.iteration_fields is None and n.tangent_influences is None


def test_source_map_budget_fallback_is_the_original_complete_stencil(monkeypatch):
    import openswing.geometry_tangent as geometry
    import openswing.vortex_tangent as vortex
    import openswing.volume_tangent as volume
    n,x=fixture(*CASES[0]);original=geometry.geometry_columns
    def no_maps(*args,**kwargs):
        kwargs.update(_direct_vortex=False,_direct_volume=False)
        return original(*args,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(geometry,'geometry_columns',no_maps)
        expected=n.jacobian(x,.37)
    def no_vortex(*args,**kwargs):raise vortex.VortexDerivativeUnavailable('deliberate source storage limit')
    def no_volume(*args,**kwargs):raise volume.VolumeDerivativeUnavailable('deliberate source storage limit')
    monkeypatch.setattr(vortex,'VortexFieldTangent',no_vortex)
    monkeypatch.setattr(volume,'VolumeFieldTangent',no_volume)
    actual=n.jacobian(x,.37)
    np.testing.assert_array_equal(actual,expected)
    assert n.geometry_derivative_diagnostics['direct_vortex_queries']==0
    assert n.geometry_derivative_diagnostics['direct_volume_queries']==0
    assert n.geometry_derivative_diagnostics['direct_vortex_fallbacks']
    assert n.geometry_derivative_diagnostics['direct_volume_fallbacks']
    assert n.iteration_fields is None and n.tangent_influences is None
