"""Documented broken-loop display against independently derived mechanics."""
from copy import deepcopy
from decimal import Decimal,localcontext
import json
from pathlib import Path
import numpy as np
import pytest
from openswing.bridge import dispatch
from openswing.frequency_response import broken_loop_gain
from test_feedback import law,z
from test_custom_feedback import lag_law


def oscillator_request(kind='pd',step=1e-5):
    source=Path('examples/instrumented-oscillator.asw').read_text()
    control=lag_law() if kind=='lag' else law(ki=100 if kind=='pi' else 0,ka=3 if kind=='acceleration' else 0)
    inputs=['power.1','command.RY[2]']
    if kind=='none':control=None;inputs=['power.1',dict(kind='gust',wave='uniform')]
    if kind=='cross':
        source+='\nEngine\n2 0 1 2 0 2 0 0 1 0 1 0 -1 0 0\nEnd\n'
        control={'outputs':[dict(actuator='E1',residual="actuator('E1')+.2*actuator('E2')+200*error('RY[2]')-command('E1')"),
                            dict(actuator='E2',residual="actuator('E2')-.3*actuator('E1')-command('E2')")]}
        inputs=['power.1','power.2']
    return dict(action='frequency',source=source,panels=4,gravity=[0,0,0],condition=dict(speed=10,alpha=0,mach=0),
        frequency=dict(controller=control,frequencies=[.3,3,10,30] if kind=='pi' else [0,3,10,30],inputs=inputs,step=step,matrices=True))


def compare_oscillator(result,kind,time_scale=1.):
    error=0.
    for point in result['samples']:
        assert point['converged'];s=1j*point['omega']/time_scale;plant=2*s*s+10*s+500
        if kind=='cross':
            # Solve the independent coupled actuator + mechanical equations,
            # with the other command held at zero for each input column.
            actual=np.linalg.solve(np.array([[1+200/plant,.2+200/plant],[-.3,1]],complex),np.eye(2))
            expected=[1-1/actual[j,j] for j in range(2)]
        elif kind=='none':expected=[0,None]
        else:
            ki=100 if kind=='pi' else 0;ka=3 if kind=='acceleration' else 0;tau=.05 if kind=='lag' else 0
            feedback=200+20*s+ka*s*s+(ki/s if ki else 0)
            # H_engine=P/(P*(1+tau*s)+feedback).
            # H_position=(200+ki/s)/(P*(1+tau*s)+feedback).
            expected=[-tau*s-feedback/plant,-((1+tau*s)*plant+20*s+ka*s*s)/(200+(ki/s if ki else 0))]
        for j,wanted in enumerate(expected):
            response=point['responses'][j];broken=response['broken_loop']
            if wanted is None:
                assert not broken['available'] and result['inputs'][j]['broken_loop_output'] is None
                continue
            assert broken['available']
            got=complex(z(broken['value']));error=max(error,abs(got-wanted))
            assert got==pytest.approx(wanted,rel=3e-6,abs=3e-7)
            match=result['inputs'][j]['broken_loop_output']
            physical=z(response['output'][match['group']][match['key']])
            assert z(broken['response_gain'])==physical
    json.dumps(result,allow_nan=False)
    return float(error)


@pytest.mark.parametrize('kind',['none','pd','pi','acceleration','lag','cross'])
def test_broken_loop_preserves_matching_units_direct_response_and_controller_coupling(kind):
    request=oscillator_request(kind);before=deepcopy(request)
    compare_oscillator(dispatch(request),kind)
    assert request==before


@pytest.mark.parametrize('value',[0j,complex(float('nan'),0),complex(0,float('inf')),1e-320+1e-320j])
def test_undefined_broken_loop_ratios_are_serializable_gaps(value):
    report=broken_loop_gain(value)
    assert not report['available'] and 'value' not in report and report['error']
    json.dumps(report,allow_nan=False)


@pytest.mark.parametrize('h',[1+0j,1+1e-15j,complex(1+2e-14,-3e-14),1e-250+2e-250j,1e250-2e250j,5e-309+5e-309j])
def test_complex_reciprocal_keeps_small_responses_and_avoids_intermediate_overflow(h):
    with localcontext() as context:
        context.prec=80
        a,b=Decimal(h.real),Decimal(h.imag);den=a*a+b*b
        expected=complex(float(1-a/den),float(b/den))
    report=broken_loop_gain(h)
    assert report['available']
    got=complex(z(report['value']))
    assert got.real==pytest.approx(expected.real,rel=3e-15,abs=1e-70)
    assert got.imag==pytest.approx(expected.imag,rel=3e-15,abs=1e-300)
    json.dumps(report,allow_nan=False)


def test_unresponsive_measurement_command_is_an_explicit_gap():
    request=oscillator_request()
    request['frequency']['controller']={'outputs':[{'actuator':'E1','terms':[{'input':'RY[2]','gain':0}]}]}
    request['frequency'].update(inputs=['command.RY[2]'],frequencies=[0,10])
    result=dispatch(request)
    for point in result['samples']:
        assert point['converged']
        broken=point['responses'][0]['broken_loop']
        assert not broken['available'] and 'zero' in broken['error']


def scaled_request():
    request=oscillator_request('lag')
    request['source']=request['source'].replace('T 1 s','T 2 s').replace('9.80665 1.225 340.294','39.2266 .30625 680.588').replace('1000 .02','1000 .01')
    request['condition']['speed']=20
    request['frequency']['controller']['parameters'].update(kd=10,tau=.025)
    request['frequency']['frequencies']=[2*w for w in request['frequency']['frequencies']]
    return request


def test_dimensionless_broken_loop_is_invariant_to_input_time_units():
    compare_oscillator(dispatch(scaled_request()),'lag',time_scale=2.)


def test_leading_zero_actuator_index_matches_the_canonical_physical_output():
    request=oscillator_request('pd');request['frequency']['inputs'][0]='power.01'
    result=dispatch(request)
    assert result['inputs'][0]['name']=='power.01'
    assert result['inputs'][0]['broken_loop_output']['key']=='power.1'
    compare_oscillator(result,'pd')


def test_frame_inputs_match_their_actual_net_load_or_prescribed_acceleration():
    request=dict(action='frequency',source=Path('examples/guided-body.asw').read_text(),panels=4,gravity=[0,0,0],
        condition=dict(speed=10,alpha=0,mach=0),frequency=dict(frame='mixed',load_targets={'force.x':0,'moment.z':0},
            frequencies=[0,.7,3.],inputs=['target.force.x','acceleration.y','acceleration.z','angular_acceleration.x','angular_acceleration.y','target.moment.z']))
    result=dispatch(request)
    assert not result['samples'][0]['converged'] and not result['samples'][0]['responses']
    for point in result['samples'][1:]:
        for response in point['responses']:
            assert response['broken_loop']['available']
            assert z(response['broken_loop']['value'])==pytest.approx(0,abs=3e-8)
