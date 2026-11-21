"""Exact geometry reuse and mixed control/gust derivative ownership."""
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.linear_dynamics import DynamicSystem, make_system
from openswing.tangent_influences import TangentInfluences
from openswing.frequency_response import HarmonicInput, FrequencyAnalysis, input_partials


@pytest.mark.parametrize('example', ['wing-body', 'powered'])
@pytest.mark.parametrize('frame', ['fixed', 'free'])
@pytest.mark.parametrize('panels',[4,16])
def test_cached_node_and_element_rotations_preserve_complete_moving_residual(example, frame, panels):
    model=parse_asw(Path('examples', example+'.asw').read_text())
    c=FlightCondition(speed=20,alpha=3,mach=.1,powers={1:7} if example=='powered' else {},ground_effect=1,
                      position_earth=[0,0,30],rates=[.003,-.002,.001])
    n=StaticNetwork(model,panels,c,None,())
    x=np.zeros(n.size);x[n.gamma_start:n.operating_start]=.03
    system=DynamicSystem(n,x,frame)
    cache=TangentInfluences(local_geometry=True)
    rng=np.random.default_rng(21)
    zero=np.zeros(system.size)
    trials=[(zero,zero)]
    for column in [3,6*(n.nn//2)+4,6*n.nn-1,n.gamma_start,system.velocity_start+9]:
        z=zero.copy();z[column]=1e-5
        trials.extend([(z,zero),(-z,zero),(zero,zero)])
    # Broad changes take the full-map fallback; returning to the base must
    # still recover the originally cached state, not the last trial's maps.
    trials += [(rng.normal(size=system.size)*1e-6,rng.normal(size=system.size)*1e-6),
               (zero,zero)]
    for z,zdot in trials:
        n.tangent_influences=None;n.aero_key=None
        expected,state,_=system.residual(z,zdot,detail=True)
        reference=n.deformed_meshes(state.r,state.Q,n.geometry(state.r,state.Q))
        n.tangent_influences=cache;n.aero_key=None
        actual,current,_=system.residual(z,zdot,detail=True)
        meshes=n.deformed_meshes(current.r,current.Q,n.geometry(current.r,current.Q))
        np.testing.assert_array_equal(actual,expected)
        np.testing.assert_array_equal(current.Q,state.Q)
        for a,b in zip(meshes,reference):
            for name in ['r0','r1','rm','frames','length']:
                np.testing.assert_array_equal(getattr(a,name),getattr(b,name))
    names={key[1] for key in cache.local_entries if key[0]=='network'}
    assert {'node_rotation','constitutive_frame'} <= names
    assert any(isinstance(key,tuple) and key[0]=='dynamic_chart' for key in names)
    assert any(isinstance(key,tuple) and key[0]=='mesh_frame' for key in names)
    assert cache.bytes<=64*1024**2


@pytest.mark.parametrize('dtype',[np.float16,np.float32,np.float64])
@pytest.mark.parametrize('count',[1,2,4,8,32])
def test_row_keys_preserve_signed_zero_on_noncontiguous_views(dtype,count):
    values=np.zeros((count,6),dtype=dtype)[:,::2]
    cache=TangentInfluences(local_geometry=True)
    def evaluate():
        return cache.local_rows('signed',(values,),
            lambda rows:(np.copysign(np.ones_like(values[rows]),values[rows]),))[0]
    np.testing.assert_array_equal(evaluate(),np.ones_like(values))
    values[min(7,count-1),1]=-0.
    np.testing.assert_array_equal(evaluate(),np.copysign(np.ones_like(values),values))
    values[min(7,count-1),1]=0.
    np.testing.assert_array_equal(evaluate(),np.ones_like(values))


def mixed_aircraft():
    return parse_asw(Path('examples/rectangular.asw').read_text()+
        '\nEngine\n1 0 1 0 0 0 0 -1 0 0 1 0 -1 0 0\nEnd\n')


def mixed_inputs():
    return ['control.1','power.1',dict(kind='gust',name='traveling',span_mode=1)]


def test_mixed_inputs_keep_uncached_physical_columns_and_gust_phase():
    s,_=make_system(mixed_aircraft(),FlightCondition(speed=20,alpha=0,mach=.1,powers={1:2}),
                    4,gravity=[0,0,0],structured_base=True)
    channels=[HarmonicInput(s,spec,i) for i,spec in enumerate(mixed_inputs())]
    cache={};gust=[]
    for index,w in enumerate([.3,3.7,21.]):
        count=s.network.nfev
        expected,original_forcings,profiles=input_partials(s,channels,w,1e-5)
        reference_calls=s.network.nfev-count
        count=s.network.nfev
        actual,forcings,current=input_partials(s,channels,w,1e-5,constant_inputs=cache)
        cached_calls=s.network.nfev-count
        np.testing.assert_array_equal(actual,expected)
        assert current==profiles
        if index:assert cached_calls<reference_calls
        gust.append(actual[:,-1].copy())
        for a,b in zip(forcings,original_forcings):
            for part in [0,1]:
                zero=np.zeros(s.size)
                np.testing.assert_array_equal(s.residual(zero,zero,forcing=a(part,.001)),
                                              s.residual(zero,zero,forcing=b(part,.001)))
        # A returned matrix is caller-owned; it cannot corrupt later samples.
        actual[:]=99
    assert len(cache)==2
    assert all(not entry[0].flags.writeable for entry in cache.values())
    assert np.linalg.norm(gust[0]-gust[-1])>1e-3


def test_mixed_sweep_matches_uncached_complete_outputs_and_extends_safely(monkeypatch):
    import openswing.frequency_response as module
    analysis=FrequencyAnalysis(mixed_aircraft(),FlightCondition(speed=20,alpha=0,mach=.1,powers={1:2}),
        4,inputs=mixed_inputs(),gravity=[0,0,0],matrices=True)
    original=module.input_partials
    expected=analysis.solve([.3,3.7])
    saved={key:entry[0].copy() for key,entry in analysis.constant_inputs.items()}
    extension=analysis.solve([21.])
    for key,entry in analysis.constant_inputs.items():np.testing.assert_array_equal(entry[0],saved[key])
    def uncached(system,channels,omega,step,**ignored):
        return original(system,channels,omega,step,_field_tangent=ignored.get('_field_tangent'))
    monkeypatch.setattr(module,'input_partials',uncached)
    assert analysis.solve([.3,3.7])==expected
    assert analysis.solve([21.])==extension


def test_failed_sweep_does_not_commit_partial_input_columns(monkeypatch):
    import openswing.frequency_response as module
    analysis=FrequencyAnalysis(mixed_aircraft(),FlightCondition(speed=20,alpha=0,mach=.1,powers={1:2}),
        4,inputs=mixed_inputs(),gravity=[0,0,0])
    original=module.output_perturbation
    def fail(*args,**kwargs):raise ValueError('output failure')
    monkeypatch.setattr(module,'output_perturbation',fail)
    with pytest.raises(ValueError,match='output failure'):analysis.solve([.3])
    assert analysis.constant_inputs=={}
    monkeypatch.setattr(module,'output_perturbation',original)
    assert analysis.solve([.3])['converged']
