"""Moving output-field derivatives share existing physical A and B probes."""
from pathlib import Path
from copy import copy
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.linear_dynamics import make_system,linearize,output_perturbation
from openswing.frequency_response import HarmonicInput,input_partials,harmonic_solve,InputInfluences,FrequencyAnalysis
from openswing.output_fields import FieldTangent,FieldUnavailable


def difference(a,b):
    if isinstance(a,dict):
        assert a.keys()==b.keys();return max((difference(a[k],b[k]) for k in a),default=0.)
    if isinstance(a,list):
        assert len(a)==len(b);return max((difference(v,u) for v,u in zip(a,b)),default=0.)
    if isinstance(a,(int,float)) and not isinstance(a,bool):return abs(a-b)/(1+abs(b))
    assert a==b,(a,b);return 0.


def system_for(example='rectangular',frame='fixed',extra=None,panels=4):
    return make_system(parse_asw(Path('examples',example+'.asw').read_text()),
        FlightCondition(speed=20,alpha=3,beta=2,mach=.1,position_earth=[0,0,30],
            attitude=[13,-7,21],rates=[.003,-.002,.001],**(extra or {})),panels,frame=frame,structured_base=True)[0]


@pytest.mark.parametrize('example,frame,extra',[
    ('rectangular','fixed',{}),('flexible','free',{'circulation_modes':{1:3}}),
    ('wing-body','free',{'ground_effect':1}),('wing-body','fixed',{'freeze_influences':True}),
    ('powered','fixed',{'powers':{1:7}}),('articulated','fixed',{})])
def test_shared_state_and_input_probes_preserve_full_matrices_and_physical_outputs(example,frame,extra):
    s=system_for(example,frame,extra);n=s.network;s.base_report()
    count=n.nfev;reference,mass=linearize(s,sparse=True);reference_calls=n.nfev-count
    count=n.nfev;a,m=linearize(s,sparse=True,_output_fields=True);calls=n.nfev-count
    np.testing.assert_array_equal(a.toarray(),reference.toarray())
    np.testing.assert_array_equal(m.toarray(),mass.toarray())
    assert calls<=reference_calls+1,(calls,reference_calls)
    fields=s._output_field_tangent
    assert fields is not None and fields.active and fields.matrix is not None, None if fields is None else fields.report()
    assert not fields.pending and fields.bytes<=fields.limit
    specs=[*['control.'+str(k) for k in n.model.controls],*['power.'+str(k) for k in n.model.engine_controls],dict(kind='gust',name='wave',span_mode=1)]
    channels=[HarmonicInput(s,v,i) for i,v in enumerate(specs)]
    constant={};influences=InputInfluences(s)
    for omega in [.3,7.]:
        before=n.nfev;expected,_,profiles=input_partials(s,channels,omega,1e-5);original_calls=n.nfev-before
        before=n.nfev;b,forcing,current=input_partials(s,channels,omega,1e-5,constant_inputs=constant,influence_cache=influences,_field_tangent=fields)
        assert n.nfev-before<=original_calls
        np.testing.assert_array_equal(b,expected);assert current==profiles
        x,_=harmonic_solve(a,m,b,omega)
        for j,ch in enumerate(channels):
            d=fields.input_column(forcing[j]);assert d is not None and not d.flags.writeable
            old=output_perturbation(s,x[:,j],1j*omega*x[:,j],forcing=forcing[j],input_scale=ch.scale)
            new=output_perturbation(s,x[:,j],1j*omega*x[:,j],forcing=forcing[j],input_scale=ch.scale,_field_tangent=fields)
            errors={key:difference(new[key],old[key]) for key in old}
            assert max(errors.values())<2e-6,(example,frame,omega,ch.report,errors)
            for key in ['nodes','geometry','sections','sensors']:assert new[key]==old[key]
        assert n.iteration_fields is None and n.tangent_influences is None


def test_owned_columns_step_and_memory_guards_and_exception_cleanup():
    s=system_for();linearize(s,sparse=True,_output_fields=True);fields=s._output_field_tangent
    assert fields.matches(s,1e-5)
    assert not fields.matches(copy(s),1e-5) and not fields.matches(s,3e-6)
    original=s.base[0];s.base[0]+=1e-8
    assert not fields.matches(s,1e-5)
    s.base[0]=original;assert fields.matches(s,1e-5)
    with pytest.raises(ValueError):fields.matrix.data[0]=99
    with pytest.raises(FieldUnavailable,match='budget'):FieldTangent(s,1e-5,limit=1)
    assert s.network.iteration_fields is None
    channels=[HarmonicInput(s,'control.1',0)]
    with pytest.raises(ValueError,match='different system'):
        input_partials(copy(s),channels,1.,1e-5,_field_tangent=fields)
    zero=np.zeros(s.size)
    def fail():raise RuntimeError('interrupted probe')
    with pytest.raises(RuntimeError,match='interrupted'):
        fields.probe(fail,zero,zero)
    assert s.network.iteration_fields is None


def test_warm_equilibrium_keeps_stationary_fields_and_only_completes_motion_columns():
    model=parse_asw(Path('examples/wing-body.asw').read_text());condition=FlightCondition(speed=20,alpha=3,mach=.1)
    base,_=make_system(model,condition,8,structured_base=True)
    analysis=FrequencyAnalysis(model,condition,8,inputs=[dict(kind='gust')],initial_state=base.equilibrium_state)
    fields=analysis.output_fields
    assert fields is not None and fields.active and fields.matrix is not None, None if fields is None else fields.report()
    assert analysis.system.state_derivative_diagnostics['equilibrium_columns_reused']==analysis.system.network.size
    before=fields.matrix.copy();result=analysis.solve([.3,3.])
    assert result['converged']
    reused=FrequencyAnalysis(model,condition,8,inputs=[dict(kind='gust',span_mode=1)],initial_state=base.equilibrium_state,_base_analysis=analysis)
    assert reused.output_fields is fields and reused.a is analysis.a
    assert reused.solve([1.])['converged']
    np.testing.assert_array_equal(before.toarray(),fields.matrix.toarray())


def test_geometry_fallback_does_not_publish_partial_output_fields(monkeypatch):
    import openswing.geometry_tangent as geometry
    s=system_for();a,m=linearize(s,sparse=True)
    def fail(*args,**kwargs):raise geometry.GeometryDerivativeUnavailable('unsupported field branch')
    monkeypatch.setattr(geometry,'geometry_columns',fail)
    full,mass=linearize(s,sparse=True,_output_fields=True)
    assert s._output_field_tangent.matrix is None
    assert 'unsupported' in s._output_field_tangent.reason
    expected,expected_mass=linearize(s,sparse=True)
    np.testing.assert_array_equal(full.toarray(),expected.toarray())
    np.testing.assert_array_equal(mass.toarray(),expected_mass.toarray())


def test_unknown_receiver_restarts_all_output_stencils_on_the_original_path(monkeypatch):
    from openswing.output_fields import Replay
    s=system_for();s.base_report();a,m=linearize(s,sparse=True,_output_fields=True)
    fields=s._output_field_tangent
    channels=[HarmonicInput(s,'control.1',0)]
    b,forcing,_=input_partials(s,channels,3.,1e-5,_field_tangent=fields)
    x,_=harmonic_solve(a,m,b,3.);v=x[:,0];rate=3j*v
    expected=output_perturbation(s,v,rate,forcing=forcing[0])
    original=Replay.get;count=0
    def fail(self,key,compute):
        nonlocal count
        count+=1
        if count==19:raise FieldUnavailable('new receiver')
        return original(self,key,compute)
    monkeypatch.setattr(Replay,'get',fail)
    actual=output_perturbation(s,v,rate,forcing=forcing[0],_field_tangent=fields)
    assert actual==expected and not fields.active and fields.matrix is None
    assert s.network.iteration_fields is None


def test_input_stencil_failure_restores_fields_without_committing_columns(monkeypatch):
    s=system_for();linearize(s,sparse=True,_output_fields=True);fields=s._output_field_tangent
    channels=[HarmonicInput(s,'control.1',0)];original=s.residual;count=0;constant={}
    def fail(*args,**kw):
        nonlocal count
        count+=1
        if count==3:raise RuntimeError('interrupted input')
        return original(*args,**kw)
    monkeypatch.setattr(s,'residual',fail)
    with pytest.raises(RuntimeError,match='interrupted input'):
        input_partials(s,channels,1.,1e-5,constant_inputs=constant,_field_tangent=fields)
    assert constant=={} and s.network.iteration_fields is None


@pytest.mark.parametrize('point',[[1,2,0],[-1,.1,0],[1,-.1,0]])
def test_jet_boundary_and_swirl_axis_changes_disable_the_linear_field(point):
    from openswing.output_fields import check_jets
    engine=dict(jet_enabled=True,position=np.zeros(3),radius=1.,axial_velocity=20.,delta_velocity=1.,thrust=3.,torque=.3)
    regions={};direction=np.array([1.,0,0])
    check_jets(regions,True,'test',np.array([[1.,.1,0]]),[engine],direction,1.2)
    with pytest.raises(FieldUnavailable,match='jet boundary or swirl axis'):
        check_jets(regions,False,'test',np.array([point]),[engine],direction,1.2)
