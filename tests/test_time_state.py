"""Physical checkpoint equivalence, BDF history and independent trajectories."""
from copy import deepcopy
from pathlib import Path
import json
import numpy as np
import pytest
from openswing.aero import AnalysisError,FlightCondition
from openswing.asw import parse_asw
from openswing.inertia import Motion
from openswing.time_integration import solve_time
from openswing.time_state import checkpoint,resume_time
from test_time_integration import oscillator,rigid_body
from test_feedback import configuration,condition,law
from test_custom_feedback import lag_law


def same(a,b,tol=2e-8):
    assert a['time']==pytest.approx(b['time'],abs=1e-12)
    for field in ('local_velocity','local_rates','local_acceleration','local_rate_derivative','circulation_rate'):
        np.testing.assert_allclose(a[field],b[field],atol=tol,rtol=tol)
    for field in a['frame']:np.testing.assert_allclose(a['frame'][field],b['frame'][field],atol=tol,rtol=tol)
    for x,y in zip(a['nodes'],b['nodes']):
        np.testing.assert_allclose(x['position'],y['position'],atol=tol,rtol=tol)
        np.testing.assert_allclose(x['rotation'],y['rotation'],atol=tol,rtol=tol)
    if 'feedback' in a:
        for key in ('actuators','integrals','states','state_rates'):
            for name in a['feedback'].get(key,{}):assert a['feedback'][key][name]==pytest.approx(b['feedback'][key][name],abs=tol,rel=tol)


@pytest.fixture(scope='module')
def released():
    m=oscillator(.02)
    out=solve_time(m,panels=4,duration=.08,dt=.01,gravity=[0,0,0],initial_loads=[dict(beam=1,t=2,force=[0,1,0])])
    return m,out


@pytest.mark.parametrize('index',[0,1,4])
def test_elastic_velocity_and_bdf_predecessor_survive_json_checkpoint(released,index):
    m,out=released;saved=json.loads(json.dumps(checkpoint(out,index)));original=deepcopy(saved)
    continued=resume_time(m,saved,duration=.08-saved['state']['time'])
    assert continued['continuation_steps']==0 and continued['start_time']==saved['state']['time']
    for a,b in zip(continued['snapshots'],out['snapshots'][index:]):same(a,b)
    assert len(continued['snapshots'])==len(out['snapshots'])-index
    assert continued['snapshots'][1]['order']==(1 if index==0 else 2)
    if index:assert np.linalg.norm(saved['state']['local_velocity'])>0
    assert saved==original
    json.dumps(continued,allow_nan=False)


@pytest.mark.parametrize('edit',[
    lambda s:s.update(version=2),
    lambda s:s['context']['identity'].update(model_sha256='bad'),
    lambda s:s['state'].update(local_velocity=[[0,0,0]]),
    lambda s:s['state'].update(time=float('nan')),
    lambda s:s['state']['body_to_earth'][0].__setitem__(0,-1),
    lambda s:s['older'].update(time=100),
    lambda s:s['state']['network']['internal_force'][0].__setitem__(1,99),
])
def test_malformed_or_inconsistent_checkpoint_is_rejected(released,edit):
    m,out=released;saved=checkpoint(out,4);edit(saved)
    with pytest.raises(AnalysisError):resume_time(m,saved,duration=.02)


def test_free_rotating_frame_preserves_motion_through_restart():
    m=rigid_body();out=solve_time(m,panels=4,duration=.08,dt=.02,frame='free',gravity=[0,0,0],motion=Motion([.8,1.2,.6]),velocity=[-3,1,2])
    resumed=resume_time(m,checkpoint(out,2),duration=.04)
    for a,b in zip(resumed['snapshots'],out['snapshots'][2:]):same(a,b)


@pytest.mark.parametrize('index',[1,2,3])
def test_relative_command_offsets_and_doubled_time_bdf_reset_survive(index):
    m=configuration();c=condition();control=law(kd=0,ki=100)
    forcing='time +RY[2]\n0 0\n.04 0\n.04 .01\n.08 .01\n'
    out=solve_time(m,c,4,duration=.08,dt=.02,gravity=[0,0,0],controller=control,forcing=forcing)
    saved=checkpoint(out,index);resumed=resume_time(m,saved,duration=.08-saved['state']['time'])
    assert resumed['forcing']['channels'][0]['initial']==pytest.approx(2)
    for a,b in zip(resumed['snapshots'],out['snapshots'][index:]):same(a,b)
    assert resumed['snapshots'][1]['order']==(1 if index==2 else 2)
    assert out['snapshots'][-1]['feedback']['actuators']['E1']>0


def test_custom_controller_state_and_replaced_future_table_continue_without_re_equilibrating():
    m=configuration();c=condition();control=lag_law()
    out=solve_time(m,c,4,duration=.06,dt=.02,gravity=[0,0,0],controller=control,
        forcing='time +RY[2]\n0 0\n.02 0\n.02 .01\n.1 .01\n')
    saved=checkpoint(out);resumed=resume_time(m,saved,duration=.04,forcing='time +RY[2]\n.06 .02\n.1 .02\n')
    same(resumed['snapshots'][0],out['snapshots'][-1])
    assert resumed['snapshots'][1]['order']==1
    assert resumed['forcing']['channels'][0]['initial']==pytest.approx(2)
    assert resumed['snapshots'][1]['feedback']['commands']['RY[2]']==pytest.approx(2.02)
    assert resumed['snapshots'][0]['feedback']['states']['lag']>0
    # The resulting checkpoint must itself be resumable at the pre-switch state.
    again=resume_time(m,checkpoint(resumed,0),duration=.04)
    for a,b in zip(again['snapshots'],resumed['snapshots']):same(a,b)


def test_gust_circulation_frame_phase_and_bridge_restart_are_retained():
    from openswing.bridge import run_json
    source=Path('examples/rectangular.asw').read_text();m=parse_asw(source)
    c=FlightCondition(speed=10,alpha=0,mach=0,gust=dict(type='expression',components=['0','0','.1*sin(3*t)']))
    out=solve_time(m,c,4,duration=.06,dt=.02,gravity=[0,0,0])
    assert max(abs(np.array(out['snapshots'][1]['circulation_rate'])))>0
    request=dict(action='resume_time',source=source,checkpoint=checkpoint(out,1),time=dict(duration=.04))
    resumed=json.loads(run_json(json.dumps(request)))
    for a,b in zip(resumed['snapshots'],out['snapshots'][1:]):same(a,b)
    assert resumed['snapshots'][-1]['gust']['reference_velocity_body'][2]==pytest.approx(.1*np.sin(.18))


def test_changed_step_preserves_variable_bdf2_dynamics_against_independent_matrix_recurrence(released):
    from openswing.time_integration import bdf_coefficients
    m,out=released;saved=checkpoint(out,4)
    resumed=resume_time(m,saved,duration=.04,dt=.005)
    old=np.array([saved['older']['network']['positions'][-1][1]-2,saved['older']['local_velocity'][-1][1]])
    previous=np.array([saved['state']['network']['positions'][-1][1]-2,saved['state']['local_velocity'][-1][1]])
    hp=saved['state']['time']-saved['older']['time']
    dynamics=np.array([[0.,1.],[-250.,-5.]])
    for s in resumed['snapshots'][1:]:
        h=s['step'];k0,k1,k2=bdf_coefficients(h,hp)
        exact=np.linalg.solve(k0*np.eye(2)-dynamics,-k1*previous-k2*old)
        actual=[s['nodes'][-1]['position'][1]-2,s['local_velocity'][-1][1]]
        np.testing.assert_allclose(actual,exact,atol=2e-9)
        old,previous,hp=previous,exact,h
    larger=resume_time(m,saved,duration=.07,dt=.04)
    steps=[s['step'] for s in larger['snapshots'][1:]]
    assert steps[0]<=saved['next_step']*(1+1e-12)
    assert all(b<=1.5*a*(1+1e-12) for a,b in zip(steps,steps[1:]))
