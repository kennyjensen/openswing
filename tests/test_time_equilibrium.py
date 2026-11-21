"""Stationary time initialization preserves the original unsteady equations."""
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, AnalysisError
from openswing.network import StaticNetwork, _equilibrate_full
import openswing.time_integration as time


@pytest.mark.parametrize('example,extra,forcing', [
    ('stress-wing', {}, ''),
    ('wing-body', dict(beta=2, rates=[.003,-.002,.001], attitude=[15,-8,20],
                       ground_effect=1, position_earth=[0,0,30]), ''),
    ('powered', dict(powers={1:5}), 'time E1\n0 7\n.02 9'),
    ('flexible', dict(circulation_modes={1:3}), ''),
])
def test_initialization_and_moving_response_match_dense_unsteady_equations(monkeypatch,example,extra,forcing):
    model=parse_asw(Path(f'examples/{example}.asw').read_text())
    condition=FlightCondition(mach=0,**extra)
    events=[]
    actual=time.solve_time(model,condition,4,duration=.02,dt=.01,forcing=forcing,
                           progress=lambda *row:events.append(row))
    assert any(row[0]=='static_tangent' for row in events)
    assert events[-1]==(.02,2)
    def reference(network,options,tolerance,continuation_steps,progress=None):
        return _equilibrate_full(network,min(tolerance,1e-12),continuation_steps,**options)
    monkeypatch.setattr(time,'initial_equilibrium',reference)
    expected=time.solve_time(model,condition,4,duration=.02,dt=.01,forcing=forcing)
    for a,b in zip(actual['snapshots'],expected['snapshots']):
        assert a['residual'] <= 1e-8
        for key in ['force','moment','local_velocity','local_acceleration','circulation_rate']:
            np.testing.assert_allclose(a[key],b[key],rtol=2e-6,atol=2e-7,err_msg=key)
        np.testing.assert_allclose([n['position'] for n in a['nodes']],
                                   [n['position'] for n in b['nodes']],rtol=1e-8,atol=1e-9)


@pytest.mark.parametrize('change',['motion','circulation','operating','future_option'])
def test_nonstationary_or_extended_context_keeps_original_solver(monkeypatch,change):
    n=StaticNetwork(parse_asw(Path('examples/flexible.asw').read_text()),4,FlightCondition(),None,[])
    z=np.zeros_like(n.rj)
    options=dict(elastic_motion=tuple(z.copy() for _ in range(4)),circulation_rate=np.zeros(n.ng))
    if change=='motion':options['elastic_motion'][0][0,0]=1e-100
    if change=='circulation':options['circulation_rate'][0]=1e-100
    if change=='operating':options['operating_targets']={'force.x':1}
    if change=='future_option':options['operating_factor']=.5
    calls=[]
    def original(net,tolerance,steps,**kwargs):
        calls.append((net,kwargs));return 'original',steps
    monkeypatch.setattr(time,'equilibrate',original)
    assert time.initial_equilibrium(n,options,1e-8,4)==('original',4)
    assert calls[0][0] is n
    assert calls[0][1].keys()==options.keys()|{'progress'}


def test_invalid_unsteady_damping_is_not_hidden_by_steady_initialization():
    n=StaticNetwork(parse_asw(Path('examples/flexible.asw').read_text()),4,FlightCondition(),None,[])
    n.damping_times[0,0]=-1
    z=np.zeros_like(n.rj)
    with pytest.raises(AnalysisError,match='damping times'):
        time.initial_equilibrium(n,dict(elastic_motion=(z,z,z,z),circulation_rate=np.zeros(n.ng)),1e-8,4)


def test_newton_reports_assembly_and_residual_without_changing_root():
    events=[]
    def function(x):return np.array([x[0]**2-2,x[1]-3])
    function.progress=lambda *row:events.append(row)
    root,*_=time.newton(function,np.ones(2),1e-10,check_rank=True)
    np.testing.assert_allclose(root,[np.sqrt(2),3],atol=1e-10)
    for stage in ['time_tangent','time_rank']:
        assert (stage,0,2) in events and (stage,2,2) in events
    assert any(row[0]=='time_iteration' for row in events)
