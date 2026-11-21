"""Source feedback against independent mechanical and circulation equations."""
from copy import deepcopy
import json
import os
from pathlib import Path

import numpy as np
import pytest
from scipy.linalg import expm

from openswing.aero import FlightCondition
from openswing.asw import parse_asw
from openswing.bridge import dispatch
from openswing.frequency_response import solve_frequency_response
from openswing.linear_dynamics import make_system, solve_modes
from openswing.source_airflow import AIRFLOW_POLICY, SourceAirflowNetwork
from openswing.time_state import checkpoint
from test_feedback import law, roots_match, z
from test_source_airflow_time import SOURCE, CONDITION, POLICY


OSCILLATOR = Path('examples/instrumented-oscillator.asw').read_text()
# Sensor anchors are mandatory mesh nodes. Use the existing root so the
# independent four-strip mesh remains exact; the root samples the first strip.
STRIP = SOURCE + 'Sensor\n1 1 1 0 0 0\nEnd\n'
PANELS = {'default': 4, 'beams': {'1': {'count': 4, 'spacing': 'uniform'}}}


def retain(name, value):
    folder = os.environ.get('SOURCE_FEEDBACK_ARTIFACTS')
    if folder:
        p = Path(folder); p.mkdir(parents=True, exist_ok=True)
        (p/(name+'.json')).write_text(json.dumps(value, allow_nan=False)+'\n')


def model(source):
    return parse_asw(source, beam_interpolation='drela-segspl-v1')


def strip_law(ki=.15):
    return dict(outputs=[dict(actuator='F1', terms=[dict(input='Cr[1]', gain=-.1),
        *([dict(input='Cr[1]', gain=-ki, mode='integral')] if ki else [])])])


def strip_coefficients():
    # Four finite bound segments at x=0, y=-1..1; Glauert receivers x=chord/2.
    # Integrate Biot-Savart analytically, including both trailing rays.
    speed, h = 23., .4
    edges = np.linspace(-1.,1.,5); theta = np.arccos(edges)
    receivers = np.cos((theta[:-1]+theta[1:])/2)
    ya,yb = receivers[:,None]-edges[:-1],receivers[:,None]-edges[1:]
    ra,rb = np.sqrt(h*h+ya*ya),np.sqrt(h*h+yb*yb)
    influence = -(ya/ra-yb/rb)/(4*np.pi*h)+((1+h/rb)/yb-(1+h/ra)/ya)/(4*np.pi)
    return -influence, 2/(np.pi*speed), np.full(4,speed/(2*np.pi))


@pytest.mark.parametrize('ki,ka', [(0.,0.),(100.,0.),(0.,3.)])
def test_source_closed_loop_mechanics_preserve_operator_and_exact_poles(ki, ka):
    control = law(ki=ki,ka=ka); before = deepcopy(control)
    m = model(OSCILLATOR); c = FlightCondition(speed=10.,alpha=0.,mach=0.)
    system, _ = make_system(m,c,4,gravity=[0,0,0],controller=control,
                            structural_operator=AIRFLOW_POLICY)
    assert type(system.network) is SourceAirflowNetwork
    zero = np.zeros(system.size)
    assert np.max(abs(system.residual(zero,zero))) < 1e-9
    result = solve_modes(m,c,4,count=3 if ki else 2,gravity=[0,0,0],controller=control,
                         structural_operator=AIRFLOW_POLICY)
    roots_match(result,np.roots([2+ka,30,700,ki] if ki else [2+ka,30,700]),2e-6)
    assert result['base']['structural_operator'] == AIRFLOW_POLICY
    response = solve_frequency_response(m,c,4,frequencies=[0.,3.,10.,30.],
        inputs=['power.1','command.RY[2]'],gravity=[0,0,0],controller=control,
        structural_operator=AIRFLOW_POLICY)
    for row in response['samples']:
        s = 1j*row['omega']; den = (2+ka)*s*s+30*s+700
        exact = [s/(s*den+ki), (200*s+ki)/(s*den+ki)] if ki else [1/den,200/den]
        for r,q in zip(row['responses'],exact):
            output = r['output']
            assert z(output['sensors'][1]['displacement_body'])[1] == pytest.approx(q,rel=2e-6,abs=3e-9)
            assert z(output['feedback']['actuators_E1']) == pytest.approx((2*s*s+10*s+500)*q,rel=2e-6,abs=3e-7)
    assert control == before
    retain(f'mechanical-modes-{ki}-{ka}',result)
    retain(f'mechanical-frequency-{ki}-{ka}',response)


def test_nonzero_feedback_equilibrium_uses_source_balances():
    control = law(); control['commands'] = {'RY[2]':2.01}
    system, result = make_system(model(OSCILLATOR),FlightCondition(speed=10.,alpha=0.,mach=0.),4,
        controller=control,gravity=[0,0,0],structural_operator=AIRFLOW_POLICY)
    assert type(system.network) is SourceAirflowNetwork
    r, *_ = system.network.unpack(system.base)
    assert r[-1,1]-2 == pytest.approx(2/700,rel=2e-9)
    assert system.feedback.base[0] == pytest.approx(500*2/700,rel=2e-9)


@pytest.mark.parametrize('lag', [False,True])
@pytest.mark.parametrize('ki', [0.,.15])
def test_circulation_feedback_matches_independent_closed_loop_transfer(lag, ki):
    control = strip_law(ki); c = FlightCondition(**dict(CONDITION,aero_lag=lag))
    result = solve_frequency_response(model(STRIP),c,PANELS,controller=control,
        structural_operator=AIRFLOW_POLICY,gravity=[0,0,0],frequencies=[.2,3.,20.,100.],
        inputs=['control.1'],frame='fixed')
    assert len(result['base']['strips']) == 4
    a,d,b = strip_coefficients(); d = d if lag else 0.
    for row in result['samples']:
        s = 1j*row['omega']
        operator = a+d*s*np.eye(4)+np.outer(b,[.1+ki/s,0.,0.,0.])
        gamma = np.linalg.solve(operator,b)
        out = row['responses'][0]['output']
        lift = 2*(23.+(.8*s if lag else 0.))*.5*gamma.sum()/(23.**2*2*.8)
        assert z(out['sensors'][0]['circulation']) == pytest.approx(gamma[0],rel=5e-8,abs=2e-10)
        assert z(out['global']['CL']) == pytest.approx(lift,rel=5e-8,abs=2e-10)
        assert z(out['feedback']['actuators_F1']) == pytest.approx(1-(.1+ki/s)*gamma[0],rel=5e-8,abs=2e-10)
    assert result['controller']['definition'] == control
    retain(f'strip-frequency-{lag}-{ki}',result)


def strip_time_request(dt=.001,duration=.04):
    return dict(action='time',mode='time',source=STRIP,panels=deepcopy(PANELS),
        numerics=deepcopy(POLICY),condition=deepcopy(CONDITION),
        time=dict(frame='prescribed',duration=duration,dt=dt,order=2,tolerance=1e-11,
            controller=strip_law(),forcing='time +F1\n0 0\n.004 0\n.004 .0001\n.1 .0001\n'))


def test_circulation_feedback_history_refines_and_checkpoint_preserves_controller():
    a,d,b = strip_coefficients()
    matrix = np.zeros((5,5)); matrix[:4,:4] = -(a+np.outer(b,[.1,0.,0.,0.]))/d
    matrix[:4,4] = -b*.15/d; matrix[4,0] = 1.
    load = np.r_[b*1e-4/d,0.]; stationary = np.linalg.solve(matrix,-load)
    errors=[]; histories=[]
    for dt in (.002,.001):
        request=strip_time_request(dt); result=dispatch(request)
        assert result['converged']
        assert len(result['snapshots'][0]['strips']) == 4
        t = result['snapshots'][-1]['time']-.004
        exact = stationary-expm(matrix*t)@stationary
        rate = matrix@exact+load
        cl = 2*.5*np.sum(23.*exact[:4]+.8*rate[:4])/(23.**2*2*.8)
        final = result['snapshots'][-1]
        errors.append(abs(final['CL']-cl)/abs(cl)); histories.append(result)
        assert max(row['residual'] for row in result['snapshots']) < 1e-9
        retain(f'strip-time-{dt}',result); retain(f'strip-time-request-{dt}',request)
    assert errors[1] < .35*errors[0] and errors[1] < .002
    first=dispatch(strip_time_request(duration=.02)); saved=checkpoint(first,len(first['snapshots'])-1)
    resumed=dispatch(dict(action='resume_time',mode='time',source=STRIP,numerics=POLICY,
                         checkpoint=saved,time=dict(duration=.02)))
    assert resumed['restart_context']['setup']['controller'] == strip_law()
    for key in ('CL','circulation_rate'):
        np.testing.assert_allclose(resumed['snapshots'][-1][key],histories[-1]['snapshots'][-1][key],rtol=2e-8,atol=2e-11)
    retain('strip-checkpoint',saved); retain('strip-resumed',resumed)
    retain('strip-time-accuracy',dict(relative_errors=errors))
    system,_=make_system(model(STRIP),FlightCondition(**CONDITION),PANELS,
        controller=strip_law(),frame='prescribed',structural_operator=AIRFLOW_POLICY)
    launch_request=dict(action='launch_time',mode='time',source=STRIP,numerics=POLICY,
        equilibrium_state=system.equilibrium_state,
        time={k:v for k,v in strip_time_request()['time'].items() if k!='controller'})
    launched=dispatch(launch_request)
    assert launched['restart_context']['setup']['controller'] == strip_law()
    np.testing.assert_allclose(launched['snapshots'][-1]['CL'],histories[-1]['snapshots'][-1]['CL'],rtol=2e-8,atol=2e-11)
    retain('strip-launch-request',launch_request); retain('strip-launched',launched)


def free_body_request(action='frequency',dt=.0025,duration=.08):
    from test_source_fuselage_time import request as body_request
    value=body_request(dt,duration)
    value['source']+='Sensor\n1 1 3 2 0 0\nEnd\n'
    control=dict(outputs=[dict(actuator='E1',terms=[dict(input='rx[1]',gain=-60.),
                                                  dict(input='ux[1]',gain=-10.)])])
    if action=='frequency':
        del value['time'];value.update(action=action,mode=action,
            frequency=dict(frame='free',controller=control,frequencies=[3.,10.],inputs=['power.1']))
    else:
        value['time']['controller']=control
    return value


def test_free_frame_feedback_preserves_total_inertia_and_relative_motion():
    # Root mass 2, tip mass 3, axial spring k=100. Eliminating the moving
    # root gives 3*q'' + 250*q = F; feedback adds 10*q' + 60*q.
    value=free_body_request(); result=dispatch(value)
    for row in result['samples']:
        s=1j*row['omega'];exact=1/(3*s*s+10*s+310)
        out=row['responses'][0]['output']
        assert z(out['sensors'][0]['displacement_body'])[0] == pytest.approx(exact,rel=2e-6,abs=3e-9)
        assert z(out['feedback']['actuators_E1']) == pytest.approx((3*s*s+250)*exact,rel=2e-6,abs=3e-7)
    retain('free-frequency-request',value);retain('free-frequency',result)
    matrix=np.array([[0.,1.],[-310/3,-10/3]]);steady=np.array([1/310,0.]);errors=[]
    for dt in (.005,.0025):
        request=free_body_request('time',dt);history=dispatch(request)
        maximum=0.
        for row in history['snapshots']:
            t=max(0.,row['time']-.01);exact=steady-expm(matrix*t)@steady
            actual=np.array([row['nodes'][-1]['position'][0]-2,row['local_velocity'][-1][0]])
            maximum=max(maximum,float(np.linalg.norm((actual-exact)/[1/310,1/np.sqrt(930)])))
            assert row['residual']<1e-9
        errors.append(maximum)
        retain(f'free-time-request-{dt}',request);retain(f'free-time-{dt}',history)
    assert errors[1]<.35*errors[0] and errors[1]<.002
    retain('free-time-accuracy',dict(normalized_errors=errors))
