"""Steady OPER targets and time launch under one source-airflow identity."""
from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path
import numpy as np
import pytest

from openswing.bridge import dispatch
from openswing.source_airflow import AIRFLOW_POLICY, SourceAirflowNetwork
from openswing.time_state import checkpoint
from test_source_steady_trim import engine_request
from test_source_coupled import model, condition
from openswing.source_coupled import solve_source_coupled


POLICY = dict(beam_interpolation='drela-segspl-v1', structural_operator=AIRFLOW_POLICY)


def retain(name, value):
    if folder := os.environ.get('SOURCE_AIRFLOW_TRIM_EVIDENCE'):
        path=Path(folder);path.mkdir(parents=True,exist_ok=True)
        (path/(name+'.json')).write_text(json.dumps(value,allow_nan=False)+'\n')


def trim_request():
    return dict(engine_request(), numerics=deepcopy(POLICY))


def launch_request(source, saved, dt):
    return dict(action='launch_time', mode='time', source=source, numerics=deepcopy(POLICY),
        equilibrium_state=saved, time=dict(duration=.08, dt=dt, order=2,
            frame='prescribed', tolerance=1e-10,
            forcing='time +E1\n0 0\n.01 0\n.01 3\n.2 3\n'))


def test_trim_launch_releases_force_target_and_refines_to_damped_oscillator(monkeypatch):
    value=trim_request(); original=deepcopy(value); trimmed=dispatch(value)
    retain('engine-trim',dict(request=value,result=trimmed))
    assert value==original
    saved=trimmed['equilibrium_state']; before=deepcopy(saved)
    assert saved['identity']['structural_operator']==AIRFLOW_POLICY
    assert saved['launch']['condition']['powers'][1]==pytest.approx(5.)
    assert saved['launch']['released_constraints'][0]['quantity']=='force.y'
    # Launch must validate/reuse the state, not obtain another steady branch.
    def forbidden(*args,**kwargs):pytest.fail('Steady equilibrium recomputed during launch')
    monkeypatch.setattr('openswing.network.equilibrate',forbidden)
    monkeypatch.setattr('openswing.source_discrete.equilibrate',forbidden)
    monkeypatch.setattr('openswing.time_integration.initial_equilibrium',forbidden)
    errors=[]
    for dt in (.005,.0025):
        result=dispatch(launch_request(value['source'],saved,dt))
        retain('engine-time-'+str(dt),dict(request=launch_request(value['source'],saved,dt),result=result))
        assert result['converged'] and not result['initialization']['equilibrium_recomputed']
        assert result['initialization']['released_constraints']==saved['launch']['released_constraints']
        assert result['restart_context']['identity']['structural_operator']==AIRFLOW_POLICY
        for sample in result['snapshots']:
            assert sample['residual']<1e-9
            if sample['time']<=.01:
                assert sample['nodes'][-1]['position'][1]==pytest.approx(2.01,abs=2e-10)
        final=result['snapshots'][-1]; t=final['time']-.01
        a=2.5; w=np.sqrt(250-a*a); amplitude=3/500
        exact=np.array([.01+amplitude*(1-np.exp(-a*t)*(np.cos(w*t)+a/w*np.sin(w*t))),
                        amplitude*250/w*np.exp(-a*t)*np.sin(w*t)])
        actual=np.array([final['nodes'][-1]['position'][1]-2,final['local_velocity'][-1][1]])
        error=float(np.linalg.norm((actual-exact)/[amplitude,amplitude*np.sqrt(250)]));errors.append(error)
        assert final['engines'][0]['thrust']==pytest.approx(8.,abs=1e-9)
        assert final['operating_constraints']==[]
        assert saved==before
    assert errors[1]<.003 and errors[1]<.6*errors[0],errors
    retain('engine-accuracy',dict(scaled_errors=errors,gate=.003,contraction_gate=.6,
        exact=exact.tolist(),fine_actual=actual.tolist()))
    packet=json.loads(json.dumps(checkpoint(result)))
    assert packet['context']['setup']['condition']['powers']['1']==pytest.approx(5.)


def test_airflow_operating_stack_retains_solved_settings_and_rejects_changed_launch_load():
    value=trim_request();value['action']='operating_points'
    value['operating_points']=dict(initialization='previous',points=[{},dict(
        operating_constraints=[dict(variable='power.1',quantity='force.y',target=8.)])])
    output=dispatch(value)
    assert output['converged_points']==2
    for target,row in zip((5.,8.),output['points']):
        result=row['result'];saved=result['equilibrium_state']
        assert saved['identity']['structural_operator']==AIRFLOW_POLICY
        assert saved['launch']['condition']['powers'][1]==pytest.approx(target,abs=1e-8)
        assert result['nodes'][-1]['position'][1]==pytest.approx(2+target/500,abs=2e-9)
    bad=deepcopy(saved);bad['launch']['condition']['powers'][1]=5.
    with pytest.raises(ValueError,match='inconsistent with the time equations'):
        dispatch(launch_request(value['source'],bad,.005))


def test_lifting_trim_matches_stationary_source_and_zero_rate_dynamic_residual():
    m=model(); c=condition(); gravity=[1.,-2.,-10.]
    targets=[dict(variable='alpha',quantity='CL',target=.4)]
    steady=solve_source_coupled(m,c,4,gravity=gravity,operating_constraints=targets,tolerance=1e-10)
    result=dispatch(dict(action='solve',mode='mounted',source=m.dumps(),panels=4,numerics=POLICY,
        condition=asdict(c),gravity=gravity,operating_constraints=targets,tolerance=1e-10))
    np.testing.assert_allclose([n['position'] for n in result['nodes']],
                               [n['position'] for n in steady['nodes']],rtol=0,atol=2e-9)
    assert result['operating_values']['alpha']==pytest.approx(steady['operating_values']['alpha'],abs=2e-7)
    saved=result['equilibrium_state']
    out=dispatch(dict(action='launch_time',mode='time',source=m.dumps(),numerics=POLICY,
        equilibrium_state=saved,time=dict(duration=.001,dt=.001,frame='prescribed',tolerance=1e-9)))
    assert out['initialization']['residual']<1e-9
    assert not out['initialization']['equilibrium_recomputed']
    np.testing.assert_allclose([s['circulation'] for s in out['snapshots'][0]['strips']],saved['circulation'],rtol=0,atol=1e-12)
    retain('lifting-trim',dict(source=steady,result=result,time=out))


def test_dynamic_network_still_rejects_trim_constraints_without_steady_mode():
    with pytest.raises(ValueError,match='canonical|force|moment'):
        SourceAirflowNetwork(model(),4,condition(),None,[],operating_constraints=[dict(variable='alpha',quantity='CL',target=.4)])


@pytest.mark.parametrize('field',['rates','acceleration','angular_acceleration'])
@pytest.mark.parametrize('bad',[[0.,0.], [True,0.,0.], [float('inf'),0.,0.], ['1',0.,0.]])
def test_steady_airflow_rejects_invalid_motion(field,bad):
    value=trim_request();value['condition'][field]=bad
    with pytest.raises(ValueError,match='finite xyz'):
        dispatch(value)
