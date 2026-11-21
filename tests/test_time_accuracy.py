"""Temporal refinement against independent mechanics, units and checkpoint paths."""
from copy import deepcopy
import json
import numpy as np
import pytest
from openswing.aero import AnalysisError
from openswing.asw import parse_asw
from openswing.time_accuracy import settings
from openswing.time_integration import solve_time
from openswing.time_state import checkpoint,resume_time


def spring(units=(1.,1.,1.)):
    L,T,F=units
    return parse_asw(f'''Name
Temporal accuracy spring
End
Unit
L {L} m
T {T} s
F {F} N
End
Constant
{9.80665*T*T/L} {1.225*L**4/(F*T*T)} {340.294*T/L}
End
Reference
{2/L**2} {1/L} {2/L}
End
Ground
1 0 0
End
Weight
1 2 0 {2/L} 0 {19.6133/F}
End
Beam 1
Axial spring
t y EA tdeps
0 0 {1000/F} {.02/T}
2 {2/L} {1000/F} {.02/T}
End
''')


def released(order,atol,units=(1.,1.,1.)):
    L,T,F=units
    return solve_time(spring(units),panels=4,duration=.12/T,dt=.06/T,order=order,gravity=[0,0,0],
        initial_loads=[dict(beam=1,t=2,force=[0,1/F,0])],accuracy=dict(rtol=atol*1000,atol=atol))


def physical_error(result,units=(1.,1.,1.)):
    L,T,F=units;t=np.array([s['time']*T for s in result['snapshots']]);wd=np.sqrt(243.75)
    q=np.array([s['nodes'][-1]['position'][1]*L-2 for s in result['snapshots']])
    v=np.array([s['local_velocity'][-1][1]*L/T for s in result['snapshots']])
    exact=.002*np.exp(-2.5*t)*(np.cos(wd*t)+2.5/wd*np.sin(wd*t))
    exactv=-.5/wd*np.exp(-2.5*t)*np.sin(wd*t)
    return max(np.max(abs(q-exact))/.002,np.max(abs(v-exactv))/(.002*np.sqrt(250)))


@pytest.mark.parametrize('value',[True,False,[],{'unknown':1},{'rtol':-1},{'atol':0},{'rtol':float('nan')},{'atol':True},{'minimum_step':0}])
def test_invalid_time_accuracy_is_rejected(value):
    with pytest.raises(AnalysisError):settings(value)


@pytest.fixture(scope='module')
def bdf2_study():
    return [released(2,a) for a in [1e-5,2.5e-6]]


@pytest.fixture(scope='module')
def spring_study(bdf2_study):
    return {1:[released(1,a) for a in [1e-5,2.5e-6]],2:bdf2_study,
            5:[released(5,a) for a in [1e-8,2.5e-9]]}


@pytest.mark.parametrize('order',[1,2,5])
def test_tighter_accuracy_improves_exact_damped_oscillator_and_retains_physical_steps(spring_study,order):
    loose,tight=spring_study[order]
    assert physical_error(tight)<.8*physical_error(loose)
    assert tight['accuracy']['rejected_accuracy_steps']>0
    assert tight['accuracy']['maximum_accepted_ratio']<=1
    assert tight['internal_steps']==2*tight['accepted_steps']
    for previous,row in zip(tight['snapshots'],tight['snapshots'][1:]):
        assert row['time']-previous['time']==pytest.approx(row['accuracy']['trial_step'])
        assert row['step']==pytest.approx(row['time']-row['accuracy']['midpoint_time'])
        assert row['accuracy']['maximum_ratio']<=1
        if order!=5:assert row['restart']['older']['time']==row['accuracy']['midpoint_time']
    assert tight['snapshots'][-1]['time']==.12


def test_bdf_checkpoint_keeps_internal_midpoint_and_accuracy_policy(bdf2_study):
    original=bdf2_study[1];index=len(original['snapshots'])//2
    saved=json.loads(json.dumps(checkpoint(original,index)));before=deepcopy(saved)
    resumed=resume_time(spring(),saved,duration=.12-saved['state']['time'])
    assert saved==before
    assert resumed['restart_context']['method']['accuracy']==original['restart_context']['method']['accuracy']
    assert len(resumed['snapshots'])==len(original['snapshots'])-index
    for a,b in zip(resumed['snapshots'],original['snapshots'][index:]):
        assert a['time']==pytest.approx(b['time'],abs=2e-8)
        np.testing.assert_allclose(a['local_velocity'],b['local_velocity'],atol=2e-8)
        np.testing.assert_allclose([n['position'] for n in a['nodes']],[n['position'] for n in b['nodes']],atol=2e-8)
    fixed=resume_time(spring(),saved,duration=.002,dt=.001,accuracy=None)
    assert 'accuracy' not in fixed and 'accuracy' not in fixed['restart_context']['method']


def test_refinement_is_invariant_to_consistent_length_time_and_force_units(bdf2_study):
    units=(.3048,2.,4.4482216152605);scaled=released(2,2.5e-6,units);base=bdf2_study[1]
    assert physical_error(scaled,units)==pytest.approx(physical_error(base),rel=3e-5,abs=2e-8)
    assert scaled['accepted_steps']==base['accepted_steps']
    np.testing.assert_allclose([s['time']*units[1] for s in scaled['snapshots']],[s['time'] for s in base['snapshots']],atol=2e-8,rtol=2e-6)


def test_minimum_step_failure_never_accepts_a_failed_accuracy_check():
    with pytest.raises(AnalysisError,match='minimum step.*Temporal refinement ratio'):
        solve_time(spring(),panels=4,duration=.12,dt=.06,order=2,gravity=[0,0,0],
            initial_loads=[dict(beam=1,t=2,force=[0,1,0])],accuracy=dict(rtol=.01,atol=1e-5,minimum_step=.06))


def test_radau_refinement_preserves_exact_forcing_events_and_large_earth_origin():
    from test_time_integration import rigid_body
    origin=np.array([1e6,-2e6,3e6]);m=rigid_body()
    result=solve_time(m,panels=4,duration=.06,dt=.013,order=5,gravity=[0,0,0],position=origin,
        forcing='time Ay\n0 1\n.02 1\n.02 -2\n.04 -2',accuracy=dict(rtol=1e-3,atol=1e-6))
    for row in result['snapshots']:
        t=row['time']
        if t<=.02:p=.5*t*t;v=t
        elif t<=.04:u=t-.02;p=.0002+.02*u-u*u;v=.02-2*u
        else:p=.0002-.02*(t-.04);v=-.02
        np.testing.assert_allclose(np.asarray(row['frame']['position_earth'])-origin,[0,p,0],atol=2e-8,rtol=0)
        np.testing.assert_allclose(row['frame']['velocity_origin_body'],[0,v,0],atol=2e-9,rtol=0)
    jump=next(i for i,row in enumerate(result['snapshots']) if row['time']==.02)
    assert result['snapshots'][jump]['forcing_side']=='left'
    assert result['snapshots'][jump]['forcing_values']['Ay']==1
    assert result['snapshots'][jump+1]['forcing_values']['Ay']==-2
    resumed=resume_time(m,checkpoint(result,jump),duration=.04)
    np.testing.assert_allclose(resumed['snapshots'][-1]['frame']['position_earth'],result['snapshots'][-1]['frame']['position_earth'],atol=2e-8,rtol=0)


def test_radau_orientation_comparison_crosses_global_pi_without_false_rotation_error():
    from test_time_integration import rigid_body
    from openswing.inertia import Motion
    from openswing.ground import body_to_earth
    from openswing.local_motion import rotation_matrix
    attitude=[0,0,-179];initial=body_to_earth(attitude)
    result=solve_time(rigid_body(),panels=4,duration=.04,dt=.04,order=5,gravity=[0,0,0],attitude=attitude,
        motion=Motion(rates=[0,0,4],angular_acceleration=[0,0,2]),accuracy=dict(rtol=1e-4,atol=1e-7))
    for row in result['snapshots']:
        t=row['time'];exact=initial@rotation_matrix(np.array([0,0,4*t+t*t]))
        np.testing.assert_allclose(row['frame']['body_to_earth'],exact,atol=2e-8,rtol=0)
        np.testing.assert_allclose(row['frame']['rates_body'],[0,0,4+2*t],atol=2e-9,rtol=0)
        np.testing.assert_allclose(row['applied_moment'],[0,0,-8],atol=2e-7,rtol=0)
