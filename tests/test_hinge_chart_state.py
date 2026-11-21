"""Independent analytic static spring equilibria, persistence and validation."""
from copy import deepcopy
import json
from pathlib import Path
import numpy as np
import pytest
from openswing.aero import AnalysisError
from openswing.asw import parse_asw
from openswing.network import StaticNetwork,solve_static
from openswing.equilibrium_state import capture,restore,correct

FIXTURES=Path(__file__).resolve().parent/'fixtures'/'hinge-history'
SOURCE=(FIXTURES/'source'/'dead-couple.asw').read_text()


def network(angle):
    return StaticNetwork(parse_asw(SOURCE),4,None,[0,0,0],
                         [dict(beam=2,t=2,moment=[angle,0,0])])


def solve(angle,seed=None):
    return solve_static(parse_asw(SOURCE),panels=4,gravity=[0,0,0],
                        loads=[dict(beam=2,t=2,moment=[angle,0,0])],initial_state=seed)


def check(out,angle):
    theta=np.deg2rad(angle);c,s=np.cos(theta),np.sin(theta)
    q=np.array([[1,0,0],[0,c,-s],[0,s,c]])
    outer=[n for n in out['nodes'] if n['beam']==2]
    np.testing.assert_allclose(outer[-1]['position'],[0,2+2*c,2*s],atol=2e-8)
    np.testing.assert_allclose(outer[0]['rotation'],q,atol=2e-8)
    assert out['hinges'][0]['angle_deg']==pytest.approx(angle,abs=2e-7)
    state=out['equilibrium_state']
    assert state['version']==2
    assert state['hinge_charts'][0]['joint']==1
    assert np.rad2deg(state['hinge_charts'][0]['angle_rad'])==pytest.approx(angle,abs=2e-7)
    assert out['residual']<=1e-8
    np.testing.assert_allclose(out['force_balance'],0,atol=1e-8)
    np.testing.assert_allclose(out['moment_balance'],0,atol=1e-8)


@pytest.fixture(scope='module')
def seeds():
    return {a:solve(a) for a in [-720.,-400.,-200.,-150.,150.,200.,400.,720.]}


@pytest.mark.parametrize('angle',[-720.,-400.,-200.,200.,400.,720.])
def test_hinge_exact_fresh_network_roundtrip_retains_winding(seeds,angle):
    seed=json.loads(json.dumps(seeds[angle]['equilibrium_state'],allow_nan=False))
    n=network(angle);x=restore(n,seed)
    assert max(abs(n.residual(x)))<1e-12
    roundtrip=capture(n,x)
    assert roundtrip['hinge_charts']==seed['hinge_charts']
    check(solve(angle,seed),angle)


@pytest.mark.parametrize('start,finish',[(150,200),(200,400),(400,720),(720,940),
                                      (-150,-200),(-200,-400),(-400,-720),(-720,-940)])
def test_hinge_changed_load_crosses_node_and_hinge_chart_boundaries(seeds,start,finish):
    seed=deepcopy(seeds[start]['equilibrium_state']);original=deepcopy(seed)
    out=solve(finish,seed);check(out,finish)
    assert seed==original
    assert out['equilibrium_initialization']['hinge_chart_updates']
    fresh=network(finish);x=restore(fresh,out['equilibrium_state'])
    assert max(abs(fresh.residual(x)))<=1e-8


EDITS=[
    lambda s:s.pop('hinge_charts'),
    lambda s:s.update(hinge_charts=None),
    lambda s:s.update(hinge_charts=[]),
    lambda s:s['hinge_charts'].append(deepcopy(s['hinge_charts'][0])),
    lambda s:s['hinge_charts'][0].update(joint=2),
    lambda s:s['hinge_charts'][0].update(joint=True),
    lambda s:s['hinge_charts'][0].update(angle_rad=float('nan')),
    lambda s:s['hinge_charts'][0].update(angle_rad=float('inf')),
    lambda s:s['hinge_charts'][0].update(angle_rad=True),
    lambda s:s['hinge_charts'][0].update(angle_rad='3.49'),
    lambda s:s['hinge_charts'][0].update(angle_rad=10**400),
    lambda s:s['hinge_charts'][0].update(angle_rad=1e308),
    lambda s:s['hinge_charts'][0].update(angle_rad=s['hinge_charts'][0]['angle_rad']+.1),
    lambda s:s['hinge_charts'][0].update(extra=0),
    lambda s:s.update(version=3),
    lambda s:s.update(version=True),
]


@pytest.mark.parametrize('edit',EDITS)
def test_hinge_malformed_chart_rejects_without_mutating_network(seeds,edit):
    seed=deepcopy(seeds[200]['equilibrium_state']);edit(seed)
    n=network(200);joint=next(c for c in n.constraints if c['type']==3)
    joint['angle_chart']=-7.
    with pytest.raises(AnalysisError):restore(n,seed)
    assert joint['angle_chart']==-7.


@pytest.mark.parametrize('keep_field',[False,True])
def test_hinge_legacy_hinge_state_requires_original_setup_and_unambiguous_version(seeds,keep_field):
    seed=deepcopy(seeds[200]['equilibrium_state']);seed['version']=1
    if not keep_field:seed.pop('hinge_charts')
    if keep_field:
        with pytest.raises(AnalysisError,match='unambiguous'):restore(network(200),seed)
    else:
        n=network(200);x=restore(n,seed)
        assert max(abs(n.residual(x)))<1e-8
        assert np.rad2deg(capture(n,x)['hinge_charts'][0]['angle_rad'])==pytest.approx(200)


def test_hinge_whole_turn_edit_is_not_an_equilibrium_of_the_original_spring(seeds):
    seed=deepcopy(seeds[200]['equilibrium_state'])
    seed['hinge_charts'][0]['angle_rad']+=2*np.pi
    n=network(200);x=restore(n,seed)
    # Geometry is identical, but the full original law rejects a spurious turn.
    assert max(abs(n.residual(x)))>6.
    out=solve(200,seed);check(out,200)
    assert out['equilibrium_initialization']['newton_iterations']>0


def test_hinge_exception_after_accepted_recenter_restores_original_charts(seeds,monkeypatch):
    n=network(400);joint=next(c for c in n.constraints if c['type']==3)
    joint['angle_chart']=.321
    original=n.residual;seed=seeds[200]['equilibrium_state'];seed_angle=seed['hinge_charts'][0]['angle_rad']
    def fail_after_recenter(x,*args,**kwargs):
        if abs(joint['angle_chart']-seed_angle)>1e-5:
            raise RuntimeError('injected failure after an accepted recenter')
        return original(x,*args,**kwargs)
    monkeypatch.setattr(n,'residual',fail_after_recenter)
    with pytest.raises(RuntimeError,match='injected failure'):
        correct(n,seed,1e-8,{})
    assert joint['angle_chart']==.321


def test_hinge_no_hinge_archive_stays_version_one():
    source=SOURCE.replace('Joint\n1 2 2 0 3\nEnd\nJangle\n1 1 0 0\n-100 -100\n100 100\nEnd',
                          'Joint\n1 2 2 0 0\nEnd')
    m=parse_asw(source);out=solve_static(m,panels=4,gravity=[0,0,0])
    seed=out['equilibrium_state'];assert seed['version']==1 and 'hinge_charts' not in seed
    n=StaticNetwork(m,4,None,[0,0,0],());x=restore(n,json.loads(json.dumps(seed)))
    assert max(abs(n.residual(x)))<1e-12


@pytest.mark.parametrize('bad',[None,[],False,1,'state'])
def test_hinge_invalid_top_level_state_raises_analysis_error(bad):
    with pytest.raises(AnalysisError):correct(network(200),bad,1e-8,{})


def test_hinge_rejected_trial_does_not_advance_chart(seeds,monkeypatch):
    n=network(400);joint=next(c for c in n.constraints if c['type']==3)
    seed=seeds[200]['equilibrium_state'];base=restore(n,seed)
    center=joint['angle_chart'];original=n.residual;events=[]
    def reject_first_trial(x,*args,**kwargs):
        value=original(x,*args,**kwargs)
        if np.max(abs(x-base))>.01 and len(events)<2:
            events.append(joint['angle_chart'])
            if len(events)==1:return value*1e6
        return value
    monkeypatch.setattr(n,'residual',reject_first_trial)
    x,_=correct(n,seed,1e-8,{})
    assert events==[center,center]
    assert max(abs(original(x)))<=1e-8
    assert np.rad2deg(capture(n,x)['hinge_charts'][0]['angle_rad'])==pytest.approx(400,abs=2e-7)


@pytest.mark.parametrize('sign',[-1,1])
def test_hinge_oblique_hinge_warm_continuation_has_independent_rotation(sign):
    axis=np.array([2.,1.,3.]);axis/=np.linalg.norm(axis)
    source=SOURCE.replace('Jangle\n1 1 0 0','Jangle\n1 2 1 3');m=parse_asw(source)
    out=None
    for angle in [sign*200,sign*400,sign*720]:
        out=solve_static(m,panels=4,gravity=[0,0,0],loads=[dict(beam=2,t=2,moment=angle*axis)],
                         initial_state=None if out is None else out['equilibrium_state'])
        a,b,c=axis;k=np.array([[0,-c,b],[c,0,-a],[-b,a,0]])
        theta=np.deg2rad(angle);q=np.cos(theta)*np.eye(3)+(1-np.cos(theta))*np.outer(axis,axis)+np.sin(theta)*k
        outer=[n for n in out['nodes'] if n['beam']==2]
        np.testing.assert_allclose(outer[0]['rotation'],q,atol=2e-8)
        np.testing.assert_allclose(outer[-1]['position'],[0,2,0]+q@np.array([0,2,0]),atol=2e-8)
        assert np.rad2deg(out['equilibrium_state']['hinge_charts'][0]['angle_rad'])==pytest.approx(angle,abs=2e-7)
        assert out['residual']<=1e-8
