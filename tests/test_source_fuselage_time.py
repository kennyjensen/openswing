"""Body-beam power-step history and checkpoint against an exact oscillator."""
from copy import deepcopy
import json
import os
from pathlib import Path
import numpy as np
import pytest

from openswing.bridge import dispatch
from openswing.time_state import checkpoint
from openswing.source_airflow import AIRFLOW_POLICY
from test_source_fuselage import BODY_SOURCE, ENGINE, PANELS
from test_source_airflow_engine_time import FORCING


def request(dt=.0025,duration=.08):
    return dict(action='time',mode='time',source=BODY_SOURCE+ENGINE,panels=deepcopy(PANELS),
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator=AIRFLOW_POLICY),
        condition=dict(speed=23.,alpha=0.,beta=0.,density=1.2,mach=0.,stall=False,
                       aero_lag=True,gravity_magnitude=0.,powers={'1':0.}),
        time=dict(frame='free',dt=dt,duration=duration,order=2,forcing=FORCING,tolerance=1e-11))


def retain(name,result):
    directory=os.environ.get('SOURCE_FUSELAGE_ARTIFACTS')
    if directory:
        path=Path(directory);path.mkdir(parents=True,exist_ok=True)
        (path/(name+'.json')).write_text(json.dumps(result,allow_nan=False)+'\n')


@pytest.fixture(scope='module')
def histories():
    results=[]
    for dt in (.005,.0025):
        value=request(dt);before=deepcopy(value);result=dispatch(value)
        assert value==before and result['converged'];retain(f'time-{dt}',result);results.append(result)
    return results


def test_fuselage_power_step_refines_to_exact_two_mass_response(histories):
    omega=np.sqrt(250/3);errors=[]
    for result in histories:
        maximum=0.
        for row in result['snapshots']:
            tau=max(0.,row['time']-.01)
            exact=np.array([(1-np.cos(omega*tau))/250,omega*np.sin(omega*tau)/250])
            actual=np.array([row['nodes'][-1]['position'][0]-2,row['local_velocity'][-1][0]])
            maximum=max(maximum,float(np.linalg.norm((actual-exact)/[1/250,omega/250])))
            assert row['residual']<1e-9
            np.testing.assert_allclose(row['nodes'][-1]['position'][1:],0,atol=2e-10)
        errors.append(maximum)
    assert errors[1]<.35*errors[0] and errors[1]<.002
    retain('time-accuracy',dict(errors=errors))


def test_body_checkpoint_preserves_euler_chart_and_continues_exact_history(histories):
    first=dispatch(request(duration=.04));saved=checkpoint(first,len(first['snapshots'])-1)
    result=dispatch(dict(action='resume_time',mode='time',source=BODY_SOURCE+ENGINE,
        numerics=request()['numerics'],checkpoint=saved,time=dict(duration=.04)))
    assert result['converged']
    actual=result['snapshots'][-1];expected=histories[1]['snapshots'][-1]
    for key in ('local_velocity','local_rates','force','moment'):
        np.testing.assert_allclose(actual[key],expected[key],rtol=3e-8,atol=3e-10)
    np.testing.assert_allclose([n['position'] for n in actual['nodes']],
                               [n['position'] for n in expected['nodes']],atol=3e-10)
    retain('checkpoint',saved);retain('resumed',result)
