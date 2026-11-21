"""Full physical input stencils with retained, owned influence coefficients."""
import numpy as np
import pytest
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.operating import time_load_constraints
from openswing.linear_dynamics import DynamicSystem
from openswing.frequency_response import HarmonicInput, InputInfluences, input_partials, FrequencyAnalysis
from openswing.tangent_influences import TangentInfluences
from test_direct_circulation import model_for, state_for
from test_frequency_reuse import mixed_aircraft, mixed_inputs


def system_for(example, frame='fixed'):
    model=model_for(example)
    model.reference[1]=[.7,-.2,.3];model.reference[2]=[.1,.2,-.1]
    extra=dict(ground_effect=-1 if example=='stepped-wing-body' else 1,
        powers={1:50000.} if example.startswith('jet-') else {},
        freeze_influences=example=='stepped-wing-body')
    condition=FlightCondition(speed=30,alpha=7,beta=3,mach=.2,rates=[.03,-.04,.02],
        position_earth=[0,0,30],attitude=[13,-7,21],
        gust=dict(type='expression',components=['0','0','0.01*x']),**extra)
    net=StaticNetwork(model,8,condition,None,[],
        operating_constraints=time_load_constraints('prescribed' if frame=='fixed' else frame))
    return DynamicSystem(net,state_for(net,.08),frame)


@pytest.mark.parametrize('example,frame',[
    ('rectangular','fixed'),('wing-body','free'),('stepped-wing-body','free'),
    ('jet-0','free'),('jet-1','fixed'),('jet-2','free')])
@pytest.mark.parametrize('wave',['convected','uniform'])
def test_complete_input_columns_match_uncached_fields_across_frequencies(example,frame,wave):
    system=system_for(example,frame);n=system.network
    specs=[f'control.{k}' for k in n.model.controls]+[f'power.{k}' for k in n.model.engine_controls]
    if frame=='free':specs+=['target.force.z']
    specs+=[dict(kind='gust',name='spatial',span_mode=1,symmetry='sine',wave=wave)]
    channels=[HarmonicInput(system,spec,i) for i,spec in enumerate(specs)]
    cache=InputInfluences(system);columns={};gust=[]
    for w in [.3,7.1,19.]:
        expected,_,profiles=input_partials(system,channels,w,1e-5)
        actual,_,current=input_partials(system,channels,w,1e-5,
            influence_cache=cache,constant_inputs=columns)
        np.testing.assert_array_equal(actual,expected)
        assert current==profiles
        assert n.tangent_influences is None and n.aero_key is None
        gust.append(actual[:,-1].copy())
        actual[:]=99
    if wave=='convected':assert np.linalg.norm(gust[0]-gust[-1])>1e-3
    else:np.testing.assert_array_equal(gust[0],gust[-1])
    assert 0<cache.tangent.bytes<=64*1024**2
    assert cache.tangent.static_bytes<=16*1024**2


def test_input_influence_owner_and_exception_cleanup(monkeypatch):
    s=system_for('wing-body');other=system_for('wing-body')
    channels=[HarmonicInput(s,dict(kind='gust'),0)]
    cache=InputInfluences(s)
    with pytest.raises(ValueError,match='different dynamic system'):
        input_partials(other,channels,1.,1e-5,influence_cache=cache)
    original=s.residual;calls=0
    outer=TangentInfluences();s.network.tangent_influences=outer
    def fail(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls==2:raise ValueError('interrupted stencil')
        return original(*args,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(s,'residual',fail)
        with pytest.raises(ValueError,match='interrupted stencil'):
            input_partials(s,channels,1.,1e-5,influence_cache=cache)
    assert s.network.tangent_influences is outer and s.network.aero_key is None
    s.network.tangent_influences=None
    expected,_,profiles=input_partials(s,channels,1.,1e-5)
    actual,_,current=input_partials(s,channels,1.,1e-5,influence_cache=cache)
    np.testing.assert_array_equal(actual,expected);assert profiles==current


def test_controller_commands_retain_original_side_and_load_evaluations():
    from test_feedback import configuration,condition,law
    from openswing.linear_dynamics import make_system
    s,_=make_system(configuration(),condition(),4,gravity=[0,0,0],controller=law(ki=100,ka=3))
    channels=[HarmonicInput(s,spec,i) for i,spec in enumerate([
        'power.1','command.RY[2]',dict(kind='gust',name='gust',span_mode=1)])]
    cache=InputInfluences(s)
    for w in [.4,9.]:
        expected,_,profiles=input_partials(s,channels,w,1e-5)
        actual,_,current=input_partials(s,channels,w,1e-5,influence_cache=cache)
        np.testing.assert_array_equal(actual,expected);assert profiles==current
    assert s.network.tangent_influences is None


def test_reselected_inputs_share_only_the_matching_owned_model(monkeypatch):
    model=mixed_aircraft();condition=FlightCondition(speed=20,alpha=0,mach=.1,powers={1:2})
    settings=dict(gravity=[0,0,0])
    original=FrequencyAnalysis(model,condition,4,inputs=mixed_inputs(),**settings)
    original.solve([.3])
    import openswing.frequency_response as module
    def fail(*args,**kwargs):raise AssertionError('unexpected new matrix construction')
    with monkeypatch.context() as patch:
        patch.setattr(module,'make_system',fail);patch.setattr(module,'linearize',fail)
        reused=FrequencyAnalysis(model,condition,4,inputs=list(reversed(mixed_inputs())),
            _base_analysis=original,**settings)
    assert reused.input_influences is original.input_influences
    actual=reused.solve([.3])
    reused.input_influences=InputInfluences(reused.system)
    reused.constant_inputs={}
    assert reused.solve([.3])==actual
