import numpy as np
import pytest
from openswing.network import StaticNetwork
from openswing.aero import FlightCondition
from openswing.linear_dynamics import DynamicSystem
from openswing.local_motion import rotation_matrix,rotation_vector
from openswing.structural_geometry import geometry_columns as mechanics,StructuralGeometryUnavailable
from openswing.geometry_tangent import geometry_columns
from openswing.operating import time_load_constraints
from openswing.tangent_influences import TangentInfluences
from test_direct_circulation import model_for,state_for


def ideal_model(name,typ=0):
    model=model_for(name)
    if name=='articulated':
        for row in model.records['joint']:row[4]=typ
        model.records.pop('jangle',None)
    return model


@pytest.mark.parametrize('name,typ',[('flexible',0),('wing-body',0),('articulated',0),('articulated',1),('articulated',2)])
@pytest.mark.parametrize('chart',['absolute','spatial'])
def test_structural_geometry_against_complete_unloaded_residual(name,typ,chart):
    n=StaticNetwork(ideal_model(name,typ),4,None,[0,0,0],[])
    assert not n.struts
    n.offa+=np.array([.07,-.04,.03]);n.offb+=np.array([-.02,.05,.06])
    n.S+=np.full_like(n.S,1e-8)
    x=state_for(n);x[:6*n.nn].reshape(-1,6)[:,3:]+=[.3,-.2,.4]
    a,report=mechanics(n,x,chart=chart);q=n.unpack(x)[1]
    assert not a.data.flags.writeable and report['chart']==chart
    def evaluate(delta):
        trial=x.copy();trial[:6*n.nn]+=delta
        if chart=='spatial':
            trial[:6*n.nn].reshape(-1,6)[:,3:]=rotation_vector(rotation_matrix(delta.reshape(-1,6)[:,3:])@q)
        return n.residual(trial)
    for j in range(6*n.nn):
        for width in [1e-4,3e-5]:
            d=np.zeros(6*n.nn);d[j]=width
            p,m,pp,mm=[evaluate(v*d) for v in (1,-1,2,-2)]
            reference=(8*(p-m)-(pp-mm))/(12*width)
            error=np.max(abs(a[:,j].toarray().ravel()-reference)/(1+abs(reference)))
            assert error<2e-8,(name,typ,chart,j,width,error)


@pytest.mark.parametrize('name,frame,extra',[
    ('flexible','free',{'circulation_modes':{1:3}}),
    ('wing-body','prescribed',{'ground_effect':1}),
    ('jet-2','free',{'powers':{1:50000.}}),
    ('stepped-wing-body','fixed',{'freeze_influences':True}),
])
def test_shared_structural_and_flow_columns_preserve_complete_physics(name,frame,extra):
    model=model_for(name);model.reference[1]=[.7,-.2,.3]
    condition=FlightCondition(speed=30,alpha=7,beta=3,mach=.2,rates=[.03,-.04,.02],position_earth=[0,0,30],**extra)
    n=StaticNetwork(model,4,condition,None,[],operating_constraints=time_load_constraints('prescribed' if frame=='fixed' else frame))
    s=DynamicSystem(n,state_for(n,.3),frame);zero=np.zeros(s.size)
    baseline=s.residual(zero,zero).copy()
    scales=np.r_[np.maximum(1.,abs(s.base)),np.ones(s.size-n.size)]
    n.tangent_influences=TangentInfluences(local_geometry=True)
    try:
        a,report=geometry_columns(n,lambda z:s.residual(z,zero),lambda z:s.unpack(z,zero)[0].x,scales,
            _direct_vortex=True,_direct_volume=True,_direct_geometry=True,_rotation_chart='spatial',
            _direct_structural=True,_structural_system=s)
    finally:n.tangent_influences=None;n.aero_key=None
    assert report['structural_fallback'] is None and report['structural_geometry'] is not None
    assert n.iteration_fields is None
    packet=s._structural_output_tangent
    from openswing.structural_outputs import compatibility_columns
    compatibility_columns(s);assert s._structural_output_tangent is packet
    for j in range(6*n.nn):
        for width in [1e-4,3e-5]:
            d=zero.copy();d[j]=width
            p,m,pp,mm=[s.residual(v*d,zero) for v in (1,-1,2,-2)]
            reference=(8*(p-m)-(pp-mm))/(12*width)
            error=np.max(abs(a[:,j].toarray().ravel()-reference)/(1+abs(reference)))
            assert error<2e-8,(name,frame,j,width,error)
    np.testing.assert_array_equal(s.residual(zero,zero),baseline)


def test_unsupported_hinge_and_storage_retain_original_geometry(monkeypatch):
    from openswing import structural_geometry as module
    n=StaticNetwork(model_for('torsion-joint'),4,FlightCondition(speed=20,alpha=3,mach=.1),None,[])
    x=state_for(n)
    with pytest.raises(StructuralGeometryUnavailable,match='ideal'):mechanics(n,x)
    n=StaticNetwork(model_for('flexible'),4,FlightCondition(speed=20,alpha=3,mach=.1),None,[])
    x=state_for(n);scales=np.maximum(1.,abs(x))
    with pytest.raises(StructuralGeometryUnavailable,match='budget'):mechanics(n,x,limit=1)
    def calculate(direct):
        return geometry_columns(n,lambda d:n.residual(x+d),lambda d:x+d,scales,
            _direct_vortex=True,_direct_volume=True,_direct_geometry=True,_direct_structural=direct)
    expected,_=calculate(False)
    def unavailable(*args,**kwargs):raise StructuralGeometryUnavailable('injected budget')
    monkeypatch.setattr(module,'geometry_columns',unavailable)
    actual,report=calculate(True)
    assert report['structural_fallback']=='injected budget'
    np.testing.assert_array_equal(actual.toarray(),expected.toarray())
    assert n.iteration_fields is None
