"""Independent mixed rigid-frame mechanics, forcing cutoff and restart checks."""
from pathlib import Path
from copy import deepcopy
import json
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.forcing import TimeForcing
from openswing.inertia import Motion
from openswing.operating import time_load_constraints
from openswing.network import solve_static
from openswing.time_integration import solve_time
from openswing.time_state import checkpoint,resume_time
from openswing.time_initialization import launch_time
from openswing.local_motion import rotation_matrix

SOURCE=Path('examples/guided-body.asw').read_text()

def body():return parse_asw(SOURCE)


@pytest.mark.parametrize('frame,targets,match',[
    ('mixed',None,'at least one'),('prescribed',{'force.x':0},'no load targets'),
    ('mixed',{'velocity.x':0},'map force'),('free',[], 'map force'),
    ('mixed',{'force.x':float('nan')},'finite numeric'),('free',{'moment.z':True},'finite numeric'),
])
def test_invalid_frame_selection_is_rejected(frame,targets,match):
    with pytest.raises(ValueError,match=match):time_load_constraints(frame,targets)


def test_mixed_forcing_channels_use_only_their_active_constraints_and_initial_targets():
    m=body();motion=Motion(acceleration=[0,2,0],angular_acceleration=[0,0,np.pi/6])
    f=TimeForcing('time +Fx Ay Gz\n0 1 3 4\n.1 2 5 6',m,None,motion,.2,'mixed',load_targets={'force.x':7})
    assert f.values(.05)==pytest.approx(dict(Fx=8.5,Ay=4,Gz=5))
    assert f.targets(.05)=={'force.x':8.5}
    _,actual=f.apply(.05,None,motion);np.testing.assert_allclose(actual.acceleration,[0,4,0]);assert actual.angular_acceleration[2]==pytest.approx(np.deg2rad(5))
    assert f.values(.1)==pytest.approx(dict(Fx=9,Ay=5,Gz=6))
    assert f.values(np.nextafter(.1,np.inf))==dict(Fx=0,Ay=0,Gz=0)
    assert f.targets(.2)=={'force.x':0}
    assert f.report()['end_time']==.1
    with pytest.raises(ValueError,match='before the first'):f.values(-.01)
    with pytest.raises(ValueError,match='conflicts'):
        TimeForcing('time Ax\n0 0\n1 0',m,None,motion,1,'mixed',load_targets={'force.x':0})
    with pytest.raises(ValueError,match='active frame'):
        TimeForcing('time Fy\n0 0\n1 0',m,None,motion,1,'mixed',load_targets={'force.x':0})
    with pytest.raises(ValueError,match='Duplicate'):
        TimeForcing('time Fx +fx\n0 0 0\n1 0 0',m,None,motion,1,'free')


def test_free_default_is_the_six_zero_targets_and_empty_prescribed_stays_empty():
    assert [(c.variable,c.quantity,c.target) for c in time_load_constraints('free')]==[
        (v+'.'+a,q+'.'+a,0) for v,q in [('acceleration','force'),('angular_acceleration','moment')] for a in 'xyz']
    assert time_load_constraints('prescribed')==[]


@pytest.mark.parametrize('channel,expected', [('Fx',-.5),('Mz',-.125)])
def test_finite_ramp_force_and_moment_pulses_converge_to_independent_integrals(channel,expected):
    # Input = t, net Fx=-m*ax and net Mz=-Izz*dOmega/dt, m=1, Izz=4.
    # Once the table ends at tau=.113, its actual specified value becomes zero.
    tau=.113;duration=.21;errors=[]
    target='force.x' if channel=='Fx' else 'moment.z'
    for dt in (.04,.02,.01):
        out=solve_time(body(),panels=4,frame='mixed',load_targets={target:0},duration=duration,dt=dt,
            gravity=[0,0,0],forcing=f'time {channel}\n0 0\n{tau} {tau}')
        error=0
        event=next(i for i,s in enumerate(out['snapshots']) if s['time']==tau)
        assert out['snapshots'][event]['forcing_side']=='left'
        assert out['snapshots'][event+1]['order']==1
        for s in out['snapshots']:
            t=s['time'];u=expected*min(t,tau)**2
            x=expected*(t**3/3 if t<=tau else tau**2*t-2*tau**3/3)
            if channel=='Fx':
                actual=s['frame']['velocity_origin_body'][0];position=s['frame']['position_earth'][0]
            else:
                actual=s['frame']['rates_body'][2]
                R=np.array(s['frame']['body_to_earth']);position=np.arctan2(R[1,0],R[0,0])
            error=max(error,abs(actual-u),abs(position-x))
            expected_target=t if t<=tau else 0
            assert s['forcing_values'][channel]==pytest.approx(expected_target)
            assert s['operating_constraints'][0]['actual']==pytest.approx(expected_target,abs=2e-8)
        errors.append(error)
    assert errors[1]<.45*errors[0] and errors[2]<.45*errors[1]


def mixed_case():
    m=body();m.reference[1]=[.7,.1,-.2];m.reference[2]=[.3,-.2,.4]
    motion=Motion(rates=[.2,-.3,.4],acceleration=[0,.7,0],angular_acceleration=[.1,0,-.2])
    targets={'force.x':.4,'force.z':-.7,'moment.y':.2}
    loads=[dict(beam=1,t=0,force=[1,2,3],moment=[.2,-.1,.3])]
    return m,motion,targets,loads


@pytest.fixture(scope='module')
def mixed_trajectory():
    m,motion,targets,loads=mixed_case()
    out=solve_time(m,panels=4,frame='mixed',load_targets=targets,motion=motion,loads=loads,
        duration=.08,dt=.02,gravity=[0,0,0],forcing='time Fx My\n0 .4 .2\n.04 .8 -.1')
    return m,out


def test_mixed_acceleration_loads_reference_offsets_and_gyroscopic_coupling(mixed_trajectory):
    m,out=mixed_trajectory;I=np.diag([2.,3.,4.]);rm=m.reference[1];ra=m.reference[2]
    for s in out['snapshots']:
        frame=s['frame'];omega=np.array(frame['rates_body'])
        targets=np.array([s['forcing_values']['Fx'],-.7,s['forcing_values']['My']])
        # Independent Newton-Euler equations at the mass center and moment ref.
        def wrench(x):
            acc=np.array([x[0],.7,x[1]]);angular=np.array([.1,x[2],-.2])
            acg=acc+np.cross(angular,-ra)+np.cross(omega,np.cross(omega,-ra))
            F=np.array([1,2,3])-acg
            M=np.array([.2,-.1,.3])-I@angular-np.cross(omega,I@omega)+np.cross(-rm,F)
            return np.r_[F,M]
        inds=[0,2,4];zero=wrench(np.zeros(3))
        A=np.column_stack([wrench(e)-zero for e in np.eye(3)])[inds]
        expected=np.linalg.solve(A,targets-zero[inds])
        actual=np.r_[np.array(frame['acceleration_reference_body'])[[0,2]],frame['angular_acceleration_body'][1]]
        np.testing.assert_allclose(actual,expected,atol=2e-8)
        np.testing.assert_allclose(s['applied_force'],wrench(expected)[:3],atol=2e-8)
        np.testing.assert_allclose(s['applied_moment'],wrench(expected)[3:],atol=2e-8)
        assert frame['acceleration_reference_body'][1]==pytest.approx(.7)
        np.testing.assert_allclose(np.array(frame['angular_acceleration_body'])[[0,2]],[.1,-.2],atol=1e-12)
        R=np.array(frame['body_to_earth']);np.testing.assert_allclose(R.T@R,np.eye(3),atol=1e-14)


@pytest.mark.parametrize('index',[1,2,3])
def test_checkpoint_continues_before_at_and_after_forcing_cutoff(mixed_trajectory,index):
    m,out=mixed_trajectory;saved=json.loads(json.dumps(checkpoint(out,index)));before=deepcopy(saved)
    resumed=resume_time(m,saved,duration=.08-saved['state']['time'])
    assert saved==before
    assert resumed['frame_load_targets']==out['frame_load_targets']
    for a,b in zip(resumed['snapshots'][0]['operating_constraints'],out['snapshots'][index]['operating_constraints']):
        assert {k:a[k] for k in ('variable','quantity','target','specified_target')}=={k:b[k] for k in ('variable','quantity','target','specified_target')}
        np.testing.assert_allclose([a['actual'],a['normalized_residual']],[b['actual'],b['normalized_residual']],atol=1e-12)
    for a,b in zip(resumed['snapshots'],out['snapshots'][index:]):
        for key in ('position_earth','velocity_origin_body','rates_body','acceleration_reference_body','angular_acceleration_body','body_to_earth'):
            np.testing.assert_allclose(a['frame'][key],b['frame'][key],atol=3e-9)
        assert a['forcing_values']==b['forcing_values']
    if index==2:assert resumed['snapshots'][1]['order']==1


def test_saved_steady_launch_accepts_mixed_constraints_and_applies_targets_after_zero_snapshot():
    m,motion,targets,loads=mixed_case()
    seed=solve_static(m,panels=4,motion=motion,loads=loads,gravity=[0,0,0],
        operating_constraints=time_load_constraints('mixed',targets))['equilibrium_state']
    out=launch_time(m,seed,frame='mixed',load_targets=targets,duration=.04,dt=.02,
        forcing='time Fx\n0 2\n.02 2')
    assert out['continuation_steps']==0
    assert out['snapshots'][0]['forcing_values']['Fx']==.4
    assert out['snapshots'][1]['forcing_values']['Fx']==2
    assert out['snapshots'][2]['forcing_values']['Fx']==0
    for s,v in zip(out['snapshots'],[.4,2,0]):
        assert s['operating_constraints'][0]['actual']==pytest.approx(v,abs=2e-8)
    again=resume_time(m,checkpoint(out,0),duration=.04)
    for a,b in zip(again['snapshots'],out['snapshots']):np.testing.assert_allclose(a['frame']['velocity_origin_body'],b['frame']['velocity_origin_body'],atol=2e-8)


def test_legacy_endpoint_checkpoint_discards_predecessor_at_new_cutoff():
    m=body();out=solve_time(m,panels=4,duration=.08,dt=.02,gravity=[0,0,0],forcing='time Ay\n0 2\n.04 2')
    old=checkpoint(out,2)
    # The older schema retained BDF history at the final, non-doubled sample.
    old['older']=checkpoint(out,1)['state'];old['forcing_side']='right'
    del old['context']['setup']['load_targets'];del old['options']['operating_targets']
    # A current checkpoint's recorded discrete step is binding: changing its
    # endpoint side is corruption. The legacy schema predates that record.
    with pytest.raises(ValueError,match='saved endpoint side disagrees'):
        resume_time(m,old,duration=.04)
    del old['accepted_method']
    resumed=resume_time(m,old,duration=.04)
    assert resumed['snapshots'][1]['order']==1
    for a,b in zip(resumed['snapshots'],out['snapshots'][2:]):
        np.testing.assert_allclose(a['frame']['velocity_origin_body'],b['frame']['velocity_origin_body'],atol=1e-10)
        assert a['forcing_values']==b['forcing_values']


@pytest.mark.parametrize('override',[{'force.y':0},{'force.x':float('nan')},{'force.x':True},{'force.x':'bad'}])
def test_checkpoint_rejects_inactive_or_nonfinite_applied_target_overrides(mixed_trajectory,override):
    m,out=mixed_trajectory;saved=checkpoint(out,2);saved['options']['operating_targets']=override
    with pytest.raises(ValueError,match='Operating target overrides'):resume_time(m,saved,duration=.02)
