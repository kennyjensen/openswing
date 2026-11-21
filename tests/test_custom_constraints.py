"""User trim against independent spring, sensor kinematics and control laws."""
from copy import deepcopy
from pathlib import Path
import json
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition,AnalysisError
from openswing.network import solve_static


def setup(two=False):
    source=Path('examples/instrumented-oscillator.asw').read_text()
    if two:source=source.replace('1 0 1 2 0 2 0 0 1 0 1 0 -1 0 0','1 0 1 2 0 2 0 0 1 0 1 0 -1 0 0\n2 0 1 2 0 2 0 0 1 0 2 0 -1 0 0')
    return parse_asw(source),FlightCondition(speed=10,alpha=0,mach=0)


def target(expression='sensor("2.displacement_body.y")',value=.01,**kwargs):
    return dict(variable='power.1',quantity='user.tip',expression=expression,target=value,residual_scale=.01,unit='input L',**kwargs)


def solve(m,c,constraints,**kwargs):
    return solve_static(m,c,4,gravity=[0,0,0],operating_constraints=constraints,**kwargs)


@pytest.mark.parametrize('expression,value,unit',[
    ('sensor("2.displacement_body.y")',.01,'input L'),
    ('sensor("2.strain.s")',.005,'dimensionless'),
    ('sensor("1.force_local.s")',5,'input F'),
    ('sensor("2.position_earth.y")-sensor("1.position_earth.y")',2.01,'input L'),
    ('load("force.y")+variable("power.1")',10,'input F'),
    ('exp(sensor("2.displacement_body.y"))',np.exp(.01),'dimensionless'),
])
def test_custom_targets_match_axial_compliance_and_actual_trial_loads(expression,value,unit):
    m,c=setup();t=target(expression,value);t['unit']=unit
    out=solve(m,c,[t])
    assert out['operating_values']['power.1']==pytest.approx(5,abs=2e-7)
    assert out['sensors'][1]['displacement_body'][1]==pytest.approx(.01,abs=1e-9)
    assert out['sensors'][1]['strain'][1]==pytest.approx(.005,abs=1e-9)
    np.testing.assert_allclose(out['support_force'],[0,-5,0],atol=2e-7)
    assert out['operating_constraints'][0]['actual']==pytest.approx(value,abs=1e-9)
    assert out['custom_trim']['column_scaled_reciprocal_condition']>1e-10
    assert out['equilibrium_state']['launch']['released_constraints'][0]['expression']==expression
    json.dumps(out,allow_nan=False)


def test_sensor_gust_air_angle_target_solves_the_reference_velocity_vector():
    m,c=setup();c.gust={'type':'uniform','velocity':[0,0,2]}
    t=target('sensor("2.alpha")',20);t.update(variable='alpha',unit='deg',residual_scale=10)
    out=solve(m,c,[t])
    expected=20-np.rad2deg(np.arcsin(.2*np.cos(np.deg2rad(20))))
    assert out['operating_values']['alpha']==pytest.approx(expected,abs=1e-7)
    assert out['sensors'][1]['alpha']==pytest.approx(20,abs=1e-8)


def test_custom_equation_uses_controller_actual_setting_and_can_trim_command():
    m,c=setup();t=target();t['variable']='command.E1'
    controller=dict(commands={'RY[2]':2},outputs=[dict(actuator='E1',terms=[dict(input='RY[2]',gain=-200)])])
    out=solve(m,c,[t],controller=controller)
    assert out['feedback']['actuators']['E1']==pytest.approx(5,abs=1e-8)
    assert out['feedback']['commands']['E1']==pytest.approx(7,abs=1e-8)
    t=target('variable("power.1")',5);t.update(variable='command.E1',unit='setting',residual_scale=1)
    again=solve(m,c,[t],controller=controller)
    assert again['feedback']['commands']['E1']==pytest.approx(7,abs=1e-8)


def test_custom_displacement_target_retains_weighted_allocation_hard_equations():
    m,c=setup(True)
    out=solve(m,c,[target(),dict(variable='power.2',quantity='minimum_control',weight=4)])
    np.testing.assert_allclose([out['operating_values'][f'power.{k}'] for k in (1,2)],[2.5,1.25],atol=3e-6)
    assert out['sensors'][1]['displacement_body'][1]==pytest.approx(.01,abs=1e-9)
    assert out['control_allocation']['equality_residual']<1e-8
    assert out['custom_trim']['one_sided_tangent_ratio']<1


def test_saved_custom_trim_continues_new_target_and_releases_for_physical_frequency_response():
    from openswing.frequency_response import solve_frequency_response
    m,c=setup();a=solve(m,c,[target()]);saved=deepcopy(a['equilibrium_state'])
    b=solve(m,c,[target(value=.02)],initial_state=saved)
    assert b['operating_values']['power.1']==pytest.approx(10,abs=1e-8)
    assert b['equilibrium_initialization']['initialization']=='saved physical equilibrium'
    f=solve_frequency_response(m,c,4,gravity=[0,0,0],operating_constraints=[target()],initial_state=saved,frequencies=[0,10],inputs=['power.1'])
    for row in f['samples']:
        d=row['responses'][0]['output']['sensors'][1]['displacement_body'];w=row['omega']
        assert d['real'][1]+1j*d['imag'][1]==pytest.approx(1/(500+10j*w-2*w*w),abs=1e-9)
    assert saved==a['equilibrium_state']


@pytest.mark.parametrize('edit,match',[
    ({'expression':'sensor("3.strain.s")'},'sensor reference'),
    ({'expression':'sensor("2.strain.y")'},'component'),
    ({'expression':'sensor("2.strain")'},'component'),
    ({'expression':'variable("power.9")'},'operating variable'),
    ({'expression':'load("lift")'},'load reference'),
    ({'expression':'__import__("os")'},'syntax'),
    ({'expression':'sensor("2.strain.s").real'},'syntax'),
    ({'residual_scale':0},'positive'),
    ({'residual_scale':True},'positive'),
    ({'unit':''},'unit label'),
    ({'quantity':'user.2wrong'},'user.<name>'),
    ({'quantity':'force.y'},'apply only'),
])
def test_invalid_custom_definitions_reject_before_solving(edit,match):
    m,c=setup()
    with pytest.raises(ValueError,match=match):solve(m,c,[{**target(),**edit}])


def test_undefined_section_measurement_and_nonsmooth_target_are_explicit_failures():
    m,c=setup()
    with pytest.raises(AnalysisError,match='undefined'):solve(m,c,[target('sensor("2.shell_strain")')])
    with pytest.raises(AnalysisError,match='one-sided'):solve(m,c,[target('abs(sensor("2.displacement_body.y"))',0)])


def test_differently_named_dependent_equations_fail_even_at_zero_residual():
    m,c=setup(True);a=target(value=0);b=dict(a,variable='power.2',quantity='user.other')
    with pytest.raises(AnalysisError,match='singular'):solve(m,c,[a,b])
