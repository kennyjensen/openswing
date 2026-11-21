"""Full geometry feedback against independent complete-residual stencils."""
import numpy as np
import pytest
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.linear_dynamics import DynamicSystem
from openswing.operating import time_load_constraints
from openswing.structured_static import linearization
from openswing.tangent_influences import TangentInfluences
from openswing.geometry_tangent import GeometryFields, geometry_columns
from test_direct_circulation import model_for, state_for


CASES = [
    ('rectangular', 'fixed', {}, .08),
    ('flexible', 'free', {'circulation_modes':{1:3}}, .3),
    ('wing-body', 'free', {'ground_effect':1}, .08),
    ('wing-body', 'fixed', {'ground_effect':-1}, .08),
    ('stepped-wing-body', 'free', {}, .08),
    ('stepped-wing-body', 'fixed', {'freeze_influences':True}, .08),
    ('torsion-joint', 'free', {}, .3),
    ('rectangular', 'free', {}, 1.2),
    ('rectangular', 'free', {'aero_lag':False}, .3),
    ('jet-0', 'free', {'powers':{1:50000.}}, .3),
    ('jet-1', 'free', {'powers':{1:50000.}}, .3),
    ('jet-2', 'free', {'powers':{1:50000.}}, .3),
    ('stepped-body', 'free', {}, .08),
]


@pytest.mark.parametrize('example,frame,extra,circulation', CASES)
def test_complete_geometry_columns_match_refined_full_residual(example, frame, extra, circulation):
    model = model_for(example)
    model.reference[1] = [.7,-.2,.3];model.reference[2] = [.1,.2,-.1]
    condition = FlightCondition(speed=30, alpha=7, beta=3, mach=.2, rates=[.03,-.04,.02],
        position_earth=[0,0,30], attitude=[13,-7,21], **extra)
    n = StaticNetwork(model,4,condition,None,[],operating_constraints=time_load_constraints('prescribed' if frame=='fixed' else frame))
    s = DynamicSystem(n,state_for(n,circulation),frame)
    zero = np.zeros(s.size);baseline = s.residual(zero,zero).copy()
    scales = np.r_[np.maximum(1.,abs(s.base)),np.ones(s.size-n.size)]
    n.tangent_influences = TangentInfluences(local_geometry=True);n.aero_key=None
    actual,diagnostics = geometry_columns(n,lambda d:s.residual(d,zero),lambda d:s.unpack(d,zero)[0].x,scales,_direct_geometry=True,_rotation_chart='spatial',_direct_vortex=True,_direct_volume=True)
    n.tangent_influences = None;n.aero_key=None
    for step in [1e-5,3e-6]:
        for j in range(6*n.nn):
            h=step*scales[j];d=zero.copy();d[j]=h
            p,m,pp,mm=[s.residual(f*d,zero) for f in (1,-1,2,-2)]
            expected=(8*(p-m)-(pp-mm))/(12*h)
            error=np.max(abs(actual[:,j].toarray().ravel()-expected)/(1+abs(expected)))
            assert error<2e-8,(example,frame,step,j,error)
    assert diagnostics['geometry_columns']==6*n.nn
    assert diagnostics['direct_geometry_columns']==6*n.nn
    assert diagnostics['field_evaluations']==2
    np.testing.assert_array_equal(s.residual(zero,zero),baseline)
    assert n.iteration_fields is None


@pytest.mark.parametrize('frozen',[False,True])
def test_spatial_gust_driven_jet_geometry_in_both_influence_modes(frozen):
    test_complete_geometry_columns_match_refined_full_residual('jet-2','free',
        dict(powers={1:50000.},ground_effect=1,freeze_influences=frozen,
            gust=dict(type='sinusoid',amplitude=[.2,.1,.4],wavevector=[.21,.3,-.17],omega=.4)),.3)


@pytest.mark.parametrize('factor',[0.,.6,1.])
def test_steady_chart_including_continuation_and_frame_loads(factor):
    n=StaticNetwork(model_for('wing-body'),4,FlightCondition(mach=.2,alpha=7,beta=3),None,[],
        operating_constraints=time_load_constraints('free'))
    x=state_for(n,.08);zero=np.zeros(n.size);scales=np.maximum(1.,abs(x))
    n.tangent_influences=TangentInfluences(local_geometry=True)
    actual,diagnostics=geometry_columns(n,lambda d:n.residual(x+d,factor),lambda d:x+d,scales,factor=factor,_direct_geometry=True,_rotation_chart='absolute',_direct_vortex=True,_direct_volume=True)
    assert diagnostics['direct_geometry_columns']==6*n.nn
    n.tangent_influences=None;n.aero_key=None
    for j in range(6*n.nn):
        h=3e-6*scales[j];d=zero.copy();d[j]=h
        p,m,pp,mm=[n.residual(x+f*d,factor) for f in (1,-1,2,-2)]
        expected=(8*(p-m)-(pp-mm))/(12*h)
        assert np.max(abs(actual[:,j].toarray().ravel()-expected)/(1+abs(expected)))<2e-8


@pytest.mark.parametrize('example', ['wing-body','jet-2'])
def test_large_rotations_and_cached_pair_path_keep_complete_columns(example):
    n=StaticNetwork(model_for(example),16,FlightCondition(mach=.2,alpha=7,beta=3,
        ground_effect=1,position_earth=[0,0,30],rates=[.03,-.04,.02],
        powers={1:50000.} if example=='jet-2' else {}),None,[],
        operating_constraints=time_load_constraints('free'))
    x=state_for(n,.3);x[:6*n.nn].reshape(-1,6)[:,3:]+=[.5,-.2,.3]
    s=DynamicSystem(n,x,'free');zero=np.zeros(s.size)
    scales=np.r_[np.maximum(1.,abs(s.base)),np.ones(s.size-n.size)]
    n.tangent_influences=TangentInfluences(local_geometry=True)
    actual,diagnostics=geometry_columns(n,lambda d:s.residual(d,zero),lambda d:s.unpack(d,zero)[0].x,scales,_direct_geometry=True,_rotation_chart='spatial',_direct_vortex=True,_direct_volume=True)
    assert n.tangent_influences.local_entries
    assert diagnostics['direct_geometry_columns']==6*n.nn
    n.tangent_influences=None;n.aero_key=None
    columns=np.unique(np.r_[np.arange(6),(6*np.array([n.nn//2,n.nn-1])[:,None]+np.arange(6)).ravel()])
    for j in columns:
        h=3e-6*scales[j];d=zero.copy();d[j]=h
        p,m,pp,mm=[s.residual(f*d,zero) for f in (1,-1,2,-2)]
        expected=(8*(p-m)-(pp-mm))/(12*h)
        assert np.max(abs(actual[:,j].toarray().ravel()-expected)/(1+abs(expected)))<2e-8




@pytest.mark.parametrize('failure',['constructor','late-column'])
def test_unavailable_composition_restores_original_complete_matrix(monkeypatch,failure):
    from openswing.linear_dynamics import linearize,make_system
    from openswing.geometry_partials import GeometryPartialsUnavailable
    import openswing.geometry_field_partials as partials
    import openswing.geometry_tangent as geometry
    s,_=make_system(model_for('flexible'),FlightCondition(speed=30,alpha=7,beta=3,mach=.2),4,structured_base=True)
    n=s.network
    original=geometry.geometry_columns
    def stencil(*args,**kwargs):
        kwargs['_direct_geometry']=False
        return original(*args,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(geometry,'geometry_columns',stencil)
        reference,mass=linearize(s,sparse=True)
    if failure=='constructor':
        def unavailable(*args,**kwargs):raise GeometryPartialsUnavailable('unsupported composition')
        monkeypatch.setattr(partials,'GeometryFieldPartials',unavailable)
    else:
        method=partials.GeometryFieldPartials.columns
        def interrupted(self,columns):
            if min(columns)>=16:raise GeometryPartialsUnavailable('unsupported composition')
            return method(self,columns)
        monkeypatch.setattr(partials.GeometryFieldPartials,'columns',interrupted)
    actual,m=linearize(s,sparse=True,_output_fields=True)
    np.testing.assert_allclose(actual.toarray(),reference.toarray(),atol=2e-8,rtol=2e-8)
    np.testing.assert_array_equal(m.toarray(),mass.toarray())
    assert n.iteration_fields is None and n.tangent_influences is None
    if failure=='constructor':
        assert 'unsupported' in s.state_derivative_diagnostics['geometry_assembly']['direct_geometry_fallback']
        assert s._output_field_tangent.active
    else:
        assert 'unsupported' in s.state_derivative_diagnostics['geometry_fallback']
        assert not s._output_field_tangent.active and s._output_field_tangent.matrix is None
