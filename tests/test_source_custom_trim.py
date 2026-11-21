"""Source custom trim and allocation against independent mechanical targets."""
from copy import deepcopy
import json
import os
from pathlib import Path
import numpy as np
import pytest

from openswing.bridge import dispatch
from test_source_steady_trim import engine_request


OPERATORS = ('drela-steady-coupled-v1', 'drela-moving-airflow-v1')


def request(operator, *, two=False):
    value = deepcopy(engine_request())
    value['numerics']['structural_operator'] = operator
    if two:
        line = '1 0 1 2 0 2 0 0 1 0 1 0 -1 0 0'
        value['source'] = value['source'].replace(line, line+'\n2 0 1 2 0 2 0 0 1 0 2 0 -1 0 0')
    return value


def target(expression, value, *, variable='power.1', unit='dimensionless', scale=.01):
    return dict(variable=variable, quantity='user.tip', expression=expression,
                target=value, unit=unit, residual_scale=scale)


def retain(name, value, result):
    if folder := os.environ.get('SOURCE_CUSTOM_TRIM_EVIDENCE'):
        p=Path(folder);p.mkdir(parents=True,exist_ok=True)
        (p/(name+'.json')).write_text(json.dumps(dict(request=value,result=result),allow_nan=False)+'\n')


@pytest.mark.parametrize('operator', OPERATORS)
def test_variable_section_strain_target_uses_actual_sensor_anchor(operator):
    value=request(operator)
    value['source']=value['source'].replace('0 0 1000 .02\n2 2 1000 .02',
                                           '0 0 1000 0\n2 2 2000 0')
    value['operating_constraints']=[target('sensor("2.strain.s")',.005)]
    before=deepcopy(value);out=dispatch(value)
    # Constant axial load: strain at the tip is F / EA(tip), independent of
    # interval constitutive averaging or the adjacent midpoint's stiffness.
    assert out['operating_values']['power.1']==pytest.approx(10.,abs=2e-7)
    assert out['sensors'][1]['strain'][1]==pytest.approx(.005,abs=2e-10)
    assert out['sensors'][1]['strain_sample_t']==2.
    assert out['sensors'][1]['strain_sample_location']=='one-sided sensor anchor section'
    assert out['operating_constraints'][0]['actual']==pytest.approx(out['sensors'][1]['strain'][1],abs=2e-11)
    assert out['custom_trim']['column_scaled_reciprocal_condition']>1e-10
    assert out['residual']<1e-9
    assert value==before
    retain('endpoint-'+operator,value,out)


def test_damped_source_strain_target_uses_declared_adjacent_interval():
    value=request(OPERATORS[1])
    value['source']=value['source'].replace('2 2 1000 .02','2 2 2000 .02')
    value['operating_constraints']=[target('sensor("2.strain.s")',.005)]
    out=dispatch(value)
    # The damped source chart has an interval strain rate, not an endpoint
    # rate. At zero rate, its last interval strain is F / average(EA).
    final=out['elements'][-1]
    stiffness=1000+500*(final['t0']+final['t1'])/2
    assert out['operating_values']['power.1']==pytest.approx(.005*stiffness,abs=2e-7)
    assert out['sensors'][1]['strain'][1]==pytest.approx(.005,abs=2e-10)
    assert out['sensors'][1]['strain_sample_location']=='selected adjacent element constitutive average'
    assert final['endpoint_traces'][-1]['strain'] is None
    retain('damped-interval',value,out)


@pytest.mark.parametrize('operator', OPERATORS)
def test_custom_sensor_target_and_redundant_controls_share_exact_equilibrium(operator):
    value=request(operator,two=True)
    value['operating_constraints']=[target('sensor("2.displacement_body.y")',.01,unit='input L'),
        dict(variable='power.2',quantity='minimum_control',weight=4)]
    out=dispatch(value)
    # Minimize E1^2 + 4*E2^2 subject to E1 + 2*E2 = k*.01 = 5.
    np.testing.assert_allclose([out['operating_values'][f'power.{k}'] for k in (1,2)],
                               [2.5,1.25],atol=3e-6,rtol=0)
    assert out['sensors'][1]['displacement_body'][1]==pytest.approx(.01,abs=2e-10)
    assert out['support_force'][1]==pytest.approx(-5.,abs=2e-8)
    report=out['control_allocation']
    assert report['objective']==pytest.approx(6.25,abs=1e-8)
    assert report['equality_residual']<1e-9
    assert report['normalized_stationarity']<2e-6
    assert min(report['reduced_curvatures'])>0
    assert out['custom_trim']['one_sided_tangent_ratio']<1
    retain('allocated-'+operator,value,out)


def test_custom_controller_command_uses_actual_control_and_sensor_state():
    value=request(OPERATORS[1])
    value['controller']=dict(commands={'RY[2]':2},outputs=[dict(actuator='E1',
        terms=[dict(input='RY[2]',gain=-200)])])
    value['operating_constraints']=[target('sensor("2.strain.s")',.005,variable='command.E1')]
    out=dispatch(value)
    assert out['feedback']['actuators']['E1']==pytest.approx(5.,abs=2e-8)
    assert out['feedback']['commands']['E1']==pytest.approx(7.,abs=2e-8)
    assert out['operating_values']['power.1']==pytest.approx(5.,abs=2e-8)
    assert out['sensors'][1]['strain'][1]==pytest.approx(.005,abs=2e-10)
    assert out['custom_trim']['one_sided_tangent_ratio']<1
    retain('controller-command',value,out)


@pytest.mark.parametrize('kind,match', [('undefined','undefined'),('nonsmooth','one-sided'),('dependent','singular')])
def test_invalid_custom_physics_is_rejected(kind,match):
    value=request(OPERATORS[1],two=kind=='dependent')
    row=target('sensor("2.displacement_body.y")',0.,unit='input L')
    if kind=='undefined':row['expression']='sensor("2.shell_strain")'
    if kind=='nonsmooth':row['expression']='abs(sensor("2.displacement_body.y"))'
    value['operating_constraints']=[row]
    if kind=='dependent':value['operating_constraints'].append(dict(row,variable='power.2',quantity='user.other'))
    with pytest.raises(ValueError,match=match):dispatch(value)


def test_saved_custom_allocation_changes_target_then_launches_without_trim(monkeypatch):
    value=request(OPERATORS[1],two=True)
    value['operating_constraints']=[target('sensor("2.displacement_body.y")',.01,unit='input L'),
        dict(variable='power.2',quantity='minimum_control',weight=4)]
    first=dispatch(value);saved=deepcopy(first['equilibrium_state'])
    warm=deepcopy(value);warm['initial_state']=saved
    warm['operating_constraints'][0]['target']=.016
    second=dispatch(warm)
    np.testing.assert_allclose([second['operating_values'][f'power.{k}'] for k in (1,2)],
                               [4.,2.],atol=3e-6,rtol=0)
    assert second['sensors'][1]['displacement_body'][1]==pytest.approx(.016,abs=2e-10)
    def forbidden(*a,**k):pytest.fail('Saved custom trim was recomputed during launch')
    monkeypatch.setattr('openswing.network.equilibrate',forbidden)
    monkeypatch.setattr('openswing.source_discrete.equilibrate',forbidden)
    launch=dict(action='launch_time',mode='time',source=value['source'],numerics=value['numerics'],
        equilibrium_state=saved,time=dict(duration=.002,dt=.002,order=2,frame='prescribed',tolerance=1e-10))
    time=dispatch(launch)
    assert not time['initialization']['equilibrium_recomputed']
    assert time['initialization']['released_constraints']==saved['launch']['released_constraints']
    assert time['initialization']['residual']<1e-9
    assert time['snapshots'][-1]['nodes'][-1]['position'][1]==pytest.approx(2.01,abs=2e-9)
    assert saved==first['equilibrium_state']
    retain('warm-allocation',warm,second);retain('time-launch',launch,time)


def test_elastic_airflow_allocation_preserves_full_loaded_wing():
    value=request(OPERATORS[1])
    value['source']=Path('examples/flexible.asw').read_text().rsplit('End',1)[0]+(
        't dCLdF1 dCMdF1 dCLdF2 dCMdF2 dCLdF3 dCMdF3\n'
        '0 .03 -.004 .06 -.008 -.03 .004\n8 .03 -.004 .06 -.008 -.03 .004\nEnd\n')
    value['condition'].update(speed=18.,alpha=3.,controls={1:1.5})
    value['operating_constraints']=[]
    forward=dispatch(value)
    value['condition']['controls']={}
    value['operating_constraints']=[target('aero("CL")',forward['CL'],variable='control.1',scale=1.),
        dict(variable='control.2',quantity='minimum_control',weight=4),
        dict(variable='control.3',quantity='minimum_control',weight=2)]
    out=dispatch(value)
    # All three section laws depend on F1+2*F2-F3. Thus the full nonlinear
    # wing at 1.5 is unchanged at the independent weighted projection below.
    np.testing.assert_allclose([out['operating_values'][f'control.{k}'] for k in (1,2,3)],
                               [.6,.3,-.3],atol=4e-6,rtol=0)
    assert out['max_displacement']>1e-3
    for key in ('CL','CD','Cm'):assert out[key]==pytest.approx(forward[key],abs=2e-9)
    np.testing.assert_allclose([n['position'] for n in out['nodes']],
                              [n['position'] for n in forward['nodes']],atol=2e-7,rtol=0)
    np.testing.assert_allclose([s['circulation'] for s in out['strips']],
                              [s['circulation'] for s in forward['strips']],atol=2e-7,rtol=0)
    assert out['control_allocation']['equality_residual']<1e-9
    assert out['custom_trim']['one_sided_tangent_ratio']<1
    retain('elastic-wing',value,out)
