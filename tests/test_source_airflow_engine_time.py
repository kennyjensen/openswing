"""A power step driving an exact two-mass spring through the airflow route."""
from copy import deepcopy
import json
import os
from pathlib import Path
import numpy as np
import pytest

from openswing.bridge import dispatch
from openswing.time_state import checkpoint
from openswing.source_airflow import AIRFLOW_POLICY
from test_source_airflow_engines import AXIAL_POWER_SOURCE
from test_source_airflow import PANELS
from test_source_moving_time import spring_state,earth_com


FORCING='time +E1\n0 0\n.01 0\n.01 1\n.2 1\n'


def request(frame='free',dt=.0025,duration=.08):
    return dict(action='time',mode='time',source=AXIAL_POWER_SOURCE,panels=deepcopy(PANELS),
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator=AIRFLOW_POLICY),
        condition=dict(speed=23.,alpha=0.,beta=0.,density=1.2,mach=0.,stall=False,
                       aero_lag=True,gravity_magnitude=0.,powers={'1':0.}),
        time=dict(frame=frame,dt=dt,duration=duration,order=2,forcing=FORCING,tolerance=1e-10))


def retain(name,result):
    directory=os.environ.get('SOURCE_AIRFLOW_ENGINE_ARTIFACTS')
    if directory:
        path=Path(directory);path.mkdir(parents=True,exist_ok=True)
        (path/(name+'.json')).write_text(json.dumps(result,allow_nan=False)+'\n')


@pytest.fixture(scope='module')
def histories():
    results={}
    for frame in ('prescribed','free'):
        for dt in (.005,.0025):
            value=request(frame,dt);before=deepcopy(value)
            out=dispatch(value)
            assert value==before and out['converged']
            assert out['structural_operator']==AIRFLOW_POLICY
            retain(f'time-{frame}-{dt}',out)
            results[frame,dt]=out
    return results


@pytest.mark.parametrize('frame',['prescribed','free'])
def test_engine_step_converges_to_exact_axial_motion(frame,histories):
    errors=[]
    for dt in (.005,.0025):
        out=histories[frame,dt];last=out['snapshots'][-1]
        elapsed=last['time']-.01
        k=100. if frame=='prescribed' else 250.
        frequency=np.sqrt(k/3)
        exact=np.array([(1-np.cos(frequency*elapsed))/k,
                        frequency*np.sin(frequency*elapsed)/k])
        observed=spring_state(last)
        error=np.linalg.norm((observed-exact)/np.array([1/k,frequency/k]))
        errors.append(error)
        assert max(s['residual'] for s in out['snapshots'])<1e-9
        assert all(len(s['engines'])==1 for s in out['snapshots'])
        assert last['engines'][0]['thrust']==pytest.approx(1.,abs=1e-13)
        if frame=='free':
            initial=earth_com(out['snapshots'][0])[0]
            position,velocity=earth_com(last)
            assert abs(position[1]-initial[1]-elapsed**2/10)<2e-5
            assert velocity[1]==pytest.approx(elapsed/5,abs=2e-8)
        retain(f'accuracy-{frame}-{dt}',dict(exact=exact.tolist(),observed=observed.tolist(),scaled_error=error))
    assert errors[1]<.002
    assert errors[1]<.6*errors[0]


def test_power_history_checkpoint_replays_same_motion(histories):
    first=dispatch(request(duration=.04))
    saved=json.loads(json.dumps(checkpoint(first)))
    resumed=dispatch(dict(action='resume_time',source=AXIAL_POWER_SOURCE,
        numerics=deepcopy(request()['numerics']),checkpoint=saved,time=dict(duration=.04)))
    assert resumed['converged'] and resumed['structural_operator']==AIRFLOW_POLICY
    actual=resumed['snapshots'][-1];expected=histories['free',.0025]['snapshots'][-1]
    for key in ('force','moment','local_velocity','local_rates','circulation_rate'):
        np.testing.assert_allclose(actual[key],expected[key],rtol=2e-9,atol=2e-11)
    np.testing.assert_allclose(spring_state(actual),spring_state(expected),rtol=2e-9,atol=2e-11)
    assert len(actual['engines'])==len(expected['engines'])==1
    for key in ('position','axes','force','moment','axial_velocity','thrust','torque'):
        np.testing.assert_allclose(actual['engines'][0][key],expected['engines'][0][key],
                                   rtol=2e-9,atol=2e-11,err_msg=key)
    retain('time-checkpoint',saved);retain('time-resumed',resumed)
