"""Saved steady launch checks against mechanics, trim and checkpoint histories."""
from copy import deepcopy
from pathlib import Path
import json
import numpy as np
import pytest
from openswing.aero import FlightCondition,AnalysisError
from openswing.asw import parse_asw
from openswing.bridge import dispatch
from openswing.ground import body_to_earth
from openswing.inertia import Motion
from openswing.linear_dynamics import make_system
from openswing.network import solve_static
from openswing.operating import free_flight_constraints
from openswing.time_initialization import launch_time
from openswing.time_integration import solve_time
from openswing.time_state import checkpoint,resume_time
from test_feedback import configuration,condition,law
from test_custom_feedback import lag_law
from test_time_integration import rigid_body,oscillator


@pytest.fixture(scope='module')
def pi_seed():
    control=law(kd=0,ki=100);control['commands']={'RY[2]':2}
    return solve_static(configuration(),condition(),4,gravity=[0,0,0],controller=control,
        operating_constraints=[dict(variable='command.RY[2]',quantity='force.y',target=5)])['equilibrium_state']


def test_trimmed_pi_state_holds_solved_command_integral_and_actuator_without_resolving(pi_seed):
    saved=json.loads(json.dumps(pi_seed));before=deepcopy(saved)
    out=dispatch(dict(action='launch_time',source=configuration().dumps(),equilibrium_state=saved,
        condition=dict(speed=99,powers={1:999}),panels=8,time=dict(duration=.04,dt=.02)))
    assert out['continuation_steps']==0 and not out['initialization']['equilibrium_recomputed']
    for s in out['snapshots']:
        f=s['feedback'];assert f['commands']['RY[2]']==pytest.approx(2.01,abs=1e-10)
        assert f['actuators']['E1']==pytest.approx(5,abs=1e-8)
        assert f['integrals']['RY[2]']==pytest.approx(-.05,abs=1e-9)
        np.testing.assert_allclose(s['local_velocity'],0,atol=1e-9)
        assert s['frame']['position_earth'][0]==pytest.approx(-10*s['time'],abs=1e-8)
        assert s['operating_constraints']==[]
    assert saved==before
    json.dumps(out,allow_nan=False)


def test_relative_engine_table_uses_solved_bias_not_actual_actuator():
    seed=solve_static(configuration(),condition(),4,gravity=[0,0,0],controller=law(kd=0),
        operating_constraints=[dict(variable='command.E1',quantity='force.y',target=5)])['equilibrium_state']
    out=launch_time(configuration(),seed,duration=.02,dt=.01,forcing='time +E1\n0 0\n.04 0')
    assert out['forcing']['channels'][0]['initial']==pytest.approx(7,abs=1e-8)
    for s in out['snapshots']:
        assert s['forcing_values']['E1']==pytest.approx(7,abs=1e-8)
        assert s['feedback']['actuators']['E1']==pytest.approx(5,abs=1e-8)
        assert s['feedback']['commands']['E1']==pytest.approx(7,abs=1e-8)


def test_solved_open_loop_power_and_nonzero_absolute_time_survive_launch():
    c=condition();c.time=2;c.position_earth=[1,2,3]
    seed=solve_static(configuration(),c,4,gravity=[0,0,0],
        operating_constraints=[dict(variable='power.1',quantity='force.y',target=3)])['equilibrium_state']
    out=launch_time(configuration(),seed,duration=.02,dt=.01,forcing='time +E1\n2 0\n2.1 0')
    assert out['start_time']==2 and out['end_time']==2.02
    for s in out['snapshots']:
        assert s['operating_values']['power.1']==pytest.approx(3,abs=1e-8)
        assert s['sensors'][1]['displacement_body'][1]==pytest.approx(.006,abs=1e-9)
        np.testing.assert_allclose(s['frame']['position_earth'],[1-10*(s['time']-2),2,3],atol=1e-8)
    with pytest.raises(AnalysisError,match='start at or before'):
        launch_time(configuration(),seed,duration=.02,dt=.01,forcing='time +E1\n2.01 0\n2.1 0')


def test_custom_controller_state_is_retained_before_new_forcing_and_checkpoint_restart():
    control=lag_law();control['commands']={'RY[2]':2.01}
    seed=solve_static(configuration(),condition(),4,gravity=[0,0,0],controller=control)['equilibrium_state']
    out=launch_time(configuration(),seed,duration=.04,dt=.01,forcing='time +RY[2]\n0 .01\n.08 .01')
    start=out['snapshots'][0]
    assert start['feedback']['states']['lag']==pytest.approx(10/7,abs=1e-8)
    assert start['feedback']['commands']['RY[2]']==2.01
    assert start['forcing_values']['RY[2]']==2.01
    assert start['initial_phase']=='saved_equilibrium_before_time_inputs'
    assert out['snapshots'][1]['feedback']['commands']['RY[2]']==pytest.approx(2.02)
    assert out['snapshots'][1]['feedback']['states']['lag']>10/7
    # The pre-input checkpoint must also preserve the unmodified initial state.
    for index in (0,2):
        resumed=resume_time(configuration(),json.loads(json.dumps(checkpoint(out,index))),duration=.04-out['snapshots'][index]['time'])
        for a,b in zip(resumed['snapshots'],out['snapshots'][index:]):
            np.testing.assert_allclose(a['restart']['state']['feedback'],b['restart']['state']['feedback'],atol=1e-8)
            np.testing.assert_allclose(a['local_velocity'],b['local_velocity'],atol=1e-8)


def test_absolute_time_in_controller_expressions_is_not_reset_at_launch():
    c=condition();c.time=2
    seed=solve_static(configuration(),c,4,gravity=[0,0,0],
        controller=dict(outputs=[dict(actuator='E1',expression='time')]))['equilibrium_state']
    out=launch_time(configuration(),seed,duration=.02,dt=.01)
    for s in out['snapshots']:
        assert s['feedback']['actuators']['E1']==pytest.approx(s['time'],abs=1e-8)
    assert out['snapshots'][0]['nodes'][-1]['position'][1]==pytest.approx(2.004,abs=1e-10)


def test_aerodynamic_trim_launch_preserves_lifting_circulation():
    m=parse_asw(Path('examples/rectangular.asw').read_text());c=FlightCondition(speed=20,alpha=1,mach=0)
    steady=solve_static(m,c,4,gravity=[0,0,0],operating_constraints=[dict(variable='alpha',quantity='CL',target=.4)])
    out=launch_time(m,steady['equilibrium_state'],duration=.02,dt=.01)
    assert abs(steady['operating_values']['alpha']-1)>.5
    assert max(abs(np.array(steady['equilibrium_state']['circulation'])))>1
    for s in out['snapshots']:
        assert s['CL']==pytest.approx(.4,abs=2e-8)
        np.testing.assert_allclose(s['restart']['state']['network']['circulation'],steady['equilibrium_state']['circulation'],atol=1e-8)
        np.testing.assert_allclose(s['circulation_rate'],0,atol=1e-7)


def test_saved_loads_hold_by_default_and_explicit_release_matches_cold_release():
    m=oscillator(.02);loads=[dict(beam=1,t=2,force=[0,1,0])]
    seed=solve_static(m,panels=4,gravity=[0,0,0],loads=loads)['equilibrium_state']
    held=launch_time(m,seed,duration=.02,dt=.01)
    assert held['snapshots'][-1]['nodes'][-1]['position'][1]==pytest.approx(2.002,abs=1e-10)
    released=launch_time(m,seed,duration=.04,dt=.01,loads=[])
    reference=solve_time(m,panels=4,duration=.04,dt=.01,gravity=[0,0,0],initial_loads=loads)
    for a,b in zip(released['snapshots'],reference['snapshots']):
        np.testing.assert_allclose(a['local_velocity'],b['local_velocity'],atol=1e-9)
        np.testing.assert_allclose([n['position'] for n in a['nodes']],[n['position'] for n in b['nodes']],atol=1e-10)


def test_free_vacuum_base_retains_pose_custom_earth_gravity_and_reference_velocity_through_restart():
    m=rigid_body();m.reference[2]=[.2,.3,.4];m.reference[3]=[.8,.5,.6]
    attitude=[17,28,-41];R=body_to_earth(attitude);velocity=[.2,-.3,.4]
    system,_=make_system(m,panels=4,frame='free',gravity_magnitude=3,attitude=attitude,
        position=[1,2,3],velocity=velocity,motion=Motion(rates=[0,0,.2]))
    seed=system.equilibrium_state
    assert seed['launch']['gravity'] is None
    out=launch_time(m,seed,duration=.04,dt=.01,frame='free')
    np.testing.assert_allclose(out['snapshots'][0]['frame']['velocity_origin_body'],velocity,atol=1e-12)
    for s in out['snapshots']:
        f=s['frame'];r=np.array(f['body_to_earth'])
        np.testing.assert_allclose(s['gravity_body'],r.T@[0,0,-3],atol=1e-10)
        # BDF1 startup incurs a finite inertial-velocity error in rotating axes.
        np.testing.assert_allclose(r@f['velocity_origin_body'],R@velocity+[0,0,-3*s['time']],atol=5e-5)
    resumed=resume_time(m,checkpoint(out,2),duration=.02)
    np.testing.assert_allclose(resumed['snapshots'][-1]['frame']['position_earth'],out['snapshots'][-1]['frame']['position_earth'],atol=1e-9)
    assert resumed['restart_context']['setup']['gravity_magnitude']==3


def test_free_launch_requires_consistent_zero_net_loads():
    m=rigid_body();seed=solve_static(m,panels=4)['equilibrium_state']
    with pytest.raises(AnalysisError,match='net loads must satisfy'):
        launch_time(m,seed,duration=.02,dt=.01,frame='free')
    free=solve_static(m,panels=4,operating_constraints=free_flight_constraints())['equilibrium_state']
    out=launch_time(m,free,duration=.02,dt=.01,frame='free')
    np.testing.assert_allclose(out['snapshots'][-1]['frame']['velocity_origin_body'],[0,0,-.02*9.80665],atol=1e-8)


@pytest.mark.parametrize('edit,match',[
    (lambda s:s.pop('launch'),'recompute'),
    (lambda s:s['identity'].update(model_sha256='wrong'),'match'),
    (lambda s:s['launch'].update(panels=8),'match'),
    (lambda s:s['feedback']['layout'].update(signals=[]),'layout'),
    (lambda s:s['feedback']['values'].__setitem__(-1,0),'inconsistent'),
    (lambda s:s['feedback']['commands'].update({'RY[2]':2.02}),'inconsistent'),
    (lambda s:s['launch'].update(controller=None),'requires'),
])
def test_incompatible_legacy_or_nonsteady_saved_state_is_rejected(pi_seed,edit,match):
    seed=deepcopy(pi_seed);edit(seed)
    with pytest.raises(AnalysisError,match=match):launch_time(configuration(),seed,duration=.02,dt=.01)
