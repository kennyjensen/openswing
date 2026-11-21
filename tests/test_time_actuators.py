"""Inverse time constraints against independent rigid mechanics and section loads."""
from pathlib import Path
from copy import deepcopy
import json
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.forcing import TimeForcing
from openswing.operating import time_operating_constraints
from openswing.network import solve_static
from openswing.time_integration import solve_time
from openswing.time_initialization import launch_time
from openswing.time_state import checkpoint, resume_time


def source():
    # One kilogram, diagonal inertia (2,3,4). Unit-setting force +x and
    # unit-setting torque +z, applied at the mass center. No aerodynamic loads.
    return Path('examples/guided-body.asw').read_text()+'''\nEngine
1 0 1 0 0 0 0 1 0 0 1 0 -1 0 0
2 0 1 0 0 0 0 0 0 1 0 1 -1 0 0
End
'''


def model():
    return parse_asw(source())


def condition(**kwargs):
    return FlightCondition(speed=10, alpha=0, mach=0, **kwargs)


def target(quantity='acceleration.x', variable='power.1', value=0.):
    return dict(variable=variable, quantity=quantity, target=value)


@pytest.mark.parametrize('frame,rows,match', [
    ('free', {}, 'must be a list'),
    ('free', [dict(variable='speed',quantity='force.x')], 'declared flap'),
    ('free', [target('speed')], 'velocity and pose'),
    ('free', [target(value=True)], 'finite number'),
    ('free', [target(value=float('nan'))], 'finite number'),
    ('free', [target(),target()], 'Duplicate'),
    ('free', [target(),target(variable='power.2')], 'Duplicate'),
    ('free', [target('force.x')], 'Duplicate'),
    ('prescribed', [target()], 'frame component'),
    ('free', [{**target(),'weight':2}], 'only variable'),
])
def test_invalid_or_dependent_inverse_targets_are_rejected(frame,rows,match):
    with pytest.raises(ValueError,match=match):
        time_operating_constraints(frame,actuator_constraints=rows)


def test_target_forcing_units_relative_offsets_and_conflicts():
    c=condition();rows=[target(),target('angular_acceleration.z','power.2',np.pi/6)]
    f=TimeForcing('time +Ax +Gz\n0 1 10\n1 3 30',model(),c,c.motion(),2,'free',actuator_constraints=rows)
    assert f.values(.5)==pytest.approx(dict(Ax=2,Gz=50))
    assert f.targets(.5)==pytest.approx({'acceleration.x':2,'angular_acceleration.z':np.deg2rad(50)})
    _,motion=f.apply(.5,c,c.motion())
    np.testing.assert_array_equal(motion.acceleration,[0,0,0])
    np.testing.assert_array_equal(motion.angular_acceleration,[0,0,0])
    assert f.targets(1.1)=={'acceleration.x':0,'angular_acceleration.z':0}
    with pytest.raises(ValueError,match='solved actuator'):
        TimeForcing('time E1\n0 0\n1 1',model(),c,c.motion(),1,'free',actuator_constraints=rows)
    with pytest.raises(ValueError,match='active actuator'):
        TimeForcing('time L\n0 0\n1 1',model(),c,c.motion(),1,'free')


@pytest.mark.parametrize('order',[2,5])
def test_inverse_engine_acceleration_ramp_preserves_force_balance_and_motion(order):
    rows=[target(value=.2)];before=deepcopy(rows)
    out=solve_time(model(),condition(),4,duration=.12,dt=.02,order=order,frame='free',
        gravity=[0,0,0],actuator_constraints=rows,forcing='time +Ax\n0 0\n.12 .12')
    errors=[]
    for s in out['snapshots']:
        t=s['time'];a=.2+t
        assert s['operating_values']['power.1']==pytest.approx(a,abs=2e-8)
        assert s['frame']['acceleration_reference_body'][0]==pytest.approx(a,abs=2e-8)
        np.testing.assert_allclose(s['applied_force'],0,atol=2e-8)
        np.testing.assert_allclose(s['support_force'],0,atol=2e-8)
        # Independent integrals of a(t), including the initial velocity -10.
        exact_u=-10+.2*t+.5*t*t;exact_x=-10*t+.1*t*t+t**3/6
        errors.append(max(abs(s['frame']['velocity_origin_body'][0]-exact_u),abs(s['frame']['position_earth'][0]-exact_x)))
    assert max(errors)<(4e-4 if order==2 else 2e-8)
    assert out['actuator_constraints']==rows and rows==before
    assert set(out['frame_load_targets'])=={k+'.'+a for k in ('force','moment') for a in 'xyz'}
    json.dumps(out,allow_nan=False)


def test_inverse_torque_target_uses_degrees_and_inertia_through_a_jump_and_cutoff():
    out=solve_time(model(),condition(),4,duration=.1,dt=.02,frame='free',gravity=[0,0,0],
        actuator_constraints=[target('angular_acceleration.z','power.2')],
        forcing='time Gz\n0 0\n.033 0\n.033 12\n.073 12')
    for s in out['snapshots']:
        t=s['time'];g=np.deg2rad(12) if .033<t<=.073 else 0
        assert s['operating_values']['power.2']==pytest.approx(4*g,abs=2e-8)
        assert s['frame']['angular_acceleration_body'][2]==pytest.approx(g,abs=2e-8)
        assert s['frame']['rates_body'][2]==pytest.approx(np.deg2rad(12)*max(0,min(t,.073)-.033),abs=2e-8)
        np.testing.assert_allclose(s['applied_moment'],0,atol=2e-8)
    for event in [.033,.073]:
        i=next(i for i,s in enumerate(out['snapshots']) if s['time']==event)
        assert out['snapshots'][i]['forcing_side']=='left'
        assert out['snapshots'][i+1]['order']==1


def test_prescribed_motion_can_solve_engine_from_net_load_history():
    out=solve_time(model(),condition(acceleration=[.4,0,0]),4,duration=.08,dt=.02,
        gravity=[0,0,0],actuator_constraints=[target('force.x',value=.1)],
        forcing='time +Fx\n0 0\n.08 .2')
    assert out['frame_load_targets']=={}
    for s in out['snapshots']:
        net=.1+2.5*s['time']
        assert s['operating_values']['power.1']==pytest.approx(.4+net,abs=2e-8)
        assert s['applied_force'][0]==pytest.approx(net,abs=2e-8)
        assert s['frame']['acceleration_reference_body'][0]==pytest.approx(.4,abs=2e-8)


def test_checkpoint_continuation_keeps_targets_and_original_relative_offsets():
    rows=[target(value=.2)];forcing='time +Ax\n0 0\n.16 .16'
    out=solve_time(model(),condition(),4,duration=.16,dt=.02,frame='free',gravity=[0,0,0],
        actuator_constraints=rows,forcing=forcing)
    saved=json.loads(json.dumps(checkpoint(out,4)));before=deepcopy(saved)
    resumed=resume_time(model(),saved,duration=.08)
    assert saved==before and resumed['actuator_constraints']==rows
    for a,b in zip(out['snapshots'][4:],resumed['snapshots']):
        for key in ('velocity_origin_body','position_earth','acceleration_reference_body'):
            np.testing.assert_allclose(a['frame'][key],b['frame'][key],atol=2e-9)
        assert b['operating_values']['power.1']==pytest.approx(.2+b['time'],abs=2e-8)


def test_saved_equilibrium_launch_retains_solved_power_and_applies_new_history_later():
    rows=[target(value=.2)];constraints=time_operating_constraints('free',actuator_constraints=rows)
    steady=solve_static(model(),condition(),4,gravity=[0,0,0],operating_constraints=constraints)
    saved=steady['equilibrium_state'];before=deepcopy(saved)
    out=launch_time(model(),saved,duration=.04,dt=.02,frame='free',actuator_constraints=rows,
        forcing='time Ax\n0 .4\n.04 .6')
    assert out['snapshots'][0]['operating_values']['power.1']==pytest.approx(.2,abs=2e-8)
    for s in out['snapshots'][1:]:
        assert s['operating_values']['power.1']==pytest.approx(.4+5*s['time'],abs=2e-8)
    assert saved==before


def test_controller_and_inverse_target_cannot_solve_the_same_actuator():
    with pytest.raises(ValueError,match='both a time target and a controller'):
        solve_time(model(),condition(),4,duration=.02,dt=.02,frame='free',gravity=[0,0,0],
            actuator_constraints=[target()],controller=dict(outputs=[dict(actuator='E1',terms=[dict(input='V',gain=1)])]))


def test_flap_solved_from_pitch_load_matches_independent_section_moment():
    m=parse_asw(Path('examples/inertial.asw').read_text());c=condition()
    out=solve_time(m,c,4,duration=.06,dt=.02,gravity=[0,0,0],
        actuator_constraints=[target('moment.y','control.1')],forcing='time My\n0 0\n.06 3')
    # Rigid unswept wing: span 12, chord 1, cm=(-.03-.012 F)/sqrt(1-M²).
    q=.5*m.constants[1]*100;pg=np.sqrt(1-(10/m.constants[2])**2)
    for s in out['snapshots']:
        moment=50*s['time'];expected=(-moment*pg/(q*12)-.03)/.012
        assert s['operating_values']['control.1']==pytest.approx(expected,abs=2e-7)
        assert s['applied_moment'][1]==pytest.approx(moment,abs=2e-7)


def test_radial_target_solves_engine_with_reference_offsets_and_rotating_axes():
    m=model();m.records['engine'][0][7:10]=[0,1,0]
    m.reference[2]=[.3,-.2,.4];m.reference[3]=[-.4,.2,.1]
    c=condition(attitude=[17,-9,38],rates=[.2,-.3,.4],acceleration=[.1,0,-.2],angular_acceleration=[.04,-.05,.06])
    out=solve_time(m,c,4,duration=.06,dt=.02,frame='mixed',load_targets={'force.y':0},gravity=[0,0,0],tolerance=1e-10,
        actuator_constraints=[target('radial_acceleration',value=.2)],forcing='time +Ar\n0 0\n.06 .3')
    for s in out['snapshots']:
        f=s['frame'];R=np.array(f['body_to_earth']);omega=np.array(f['rates_body']);angular=np.array(f['angular_acceleration_body'])
        U=np.array(f['velocity_origin_body']);ra,rv=np.array(m.reference[2]),np.array(m.reference[3])
        # Derive reference acceleration from rigid-body transport, then invert
        # Earth-y acceleration minus UX*WZ. No production kinematics helper.
        extra=np.cross(angular,rv-ra)+np.cross(omega,np.cross(omega,rv-ra))
        earth_velocity=R@(U+np.cross(omega,rv));earth_rates=R@omega
        expected_ay=(.2+5*s['time']+earth_velocity[0]*earth_rates[2]-(R@(np.array([.1,0,-.2])+extra))[1])/R[1,1]
        cg_acc=np.array([.1,expected_ay,-.2])+np.cross(angular,-ra)+np.cross(omega,np.cross(omega,-ra))
        assert f['acceleration_reference_body'][1]==pytest.approx(expected_ay,abs=2e-8)
        assert s['operating_values']['power.1']==pytest.approx(cg_acc[1],abs=2e-8)
        assert s['applied_force'][1]==pytest.approx(0,abs=2e-8)


def test_lift_history_retains_load_factor_and_excludes_apparent_mass():
    text=Path('examples/inertial.asw').read_text().replace('t Cdf Cm dCMdF1','t Cdf Cm dCMdF1 dCLdF1').replace('.008 -.03 -.012','.008 -.03 -.012 .1')
    m=parse_asw(text);c=condition(load_factor=2,acceleration=[0,0,.3])
    out=solve_time(m,c,4,duration=.04,dt=.02,gravity=[0,0,0],
        actuator_constraints=[target('lift','control.1',value=20)],forcing='time +L\n0 0\n.04 10')
    for s in out['snapshots']:
        # A flat span-12, chord-1 plate has normal added mass rho*pi*c²*b/4.
        # The total aerodynamic force contains this acceleration reaction;
        # the specified lift uses circulatory/profile forces alone.
        speed=np.linalg.norm(s['frame']['velocity_origin_body']);uz=s['frame']['velocity_origin_body'][2]
        lift_axis=np.array([uz/speed,0,10/speed])
        added=np.array([0,0,-m.constants[1]*np.pi*12/4*.3])
        expected=2*(20+250*s['time'])
        actual=(np.array(s['force'])-added)@lift_axis
        assert actual==pytest.approx(expected,abs=2e-6)


def test_checked_time_steps_preserve_inverse_constraints_and_checkpoint():
    rows=[target(value=.2)]
    out=solve_time(model(),condition(),4,duration=.04,dt=.02,frame='free',gravity=[0,0,0],
        actuator_constraints=rows,forcing='time +Ax\n0 0\n.08 .08',accuracy=dict(rtol=.001,atol=1e-6))
    assert out['actuator_constraints']==rows and out['accuracy']['maximum_accepted_ratio']<=1
    assert all('actuator_settings' in s['accuracy']['group_ratios'] for s in out['snapshots'][1:])
    resumed=resume_time(model(),checkpoint(out),duration=.02)
    for s in out['snapshots']+resumed['snapshots']:
        assert s['operating_values']['power.1']==pytest.approx(.2+s['time'],abs=2e-8)


@pytest.mark.parametrize('saved',[False,True])
def test_zero_target_does_not_hide_absent_actuator_authority(saved):
    rows=[target('acceleration.y')]
    if saved:
        equilibrium=solve_static(model(),condition(),4,gravity=[0,0,0])['equilibrium_state']
        with pytest.raises(ValueError,match='locally unique'):
            launch_time(model(),equilibrium,duration=.02,dt=.02,frame='free',actuator_constraints=rows)
    else:
        with pytest.raises(ValueError,match='mechanism or redundant'):
            solve_time(model(),condition(),4,duration=.02,dt=.02,frame='free',gravity=[0,0,0],actuator_constraints=rows)


@pytest.mark.parametrize('name',['Ax','ax','AX'])
def test_forcing_channel_cannot_own_an_inverse_target_and_controller_command(name):
    from openswing.feedback import FeedbackSystem
    from openswing.network import StaticNetwork
    c=condition();m=model();rows=[target()]
    n=StaticNetwork(m,4,c,[0,0,0],(),None,time_operating_constraints('free',actuator_constraints=rows),'bilateral')
    f=FeedbackSystem(n,dict(outputs=[dict(actuator='E2',terms=[dict(input='Ax',gain=1)])]))
    with pytest.raises(ValueError,match='both an inverse target and a controller command'):
        TimeForcing(f'time {name}\n0 0\n1 1',m,c,c.motion(),1,'free',f,actuator_constraints=rows)
