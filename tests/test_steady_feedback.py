"""Steady controller/trim checks against independent mechanics and open-loop trim."""
from pathlib import Path
import json
import numpy as np
import pytest
from openswing.aero import FlightCondition, AnalysisError
from openswing.asw import parse_asw
from openswing.network import solve_static
from openswing.linear_dynamics import solve_modes
from openswing.frequency_response import solve_frequency_response
from openswing.bridge import dispatch
from test_feedback import configuration, condition, law, roots_match, z


def test_static_proportional_control_solves_actual_actuator_and_elastic_error_together():
    control=law(kd=0);control['commands']={'RY[2]':2.01}
    out=solve_static(configuration(),condition(),4,gravity=[0,0,0],controller=control)
    # k*y = Kp*(yc-y), k=500, Kp=200, yc=.01.
    y=2/700
    assert out['sensors'][1]['displacement_body'][1]==pytest.approx(y,abs=1e-10)
    assert out['feedback']['actuators']['E1']==pytest.approx(500*y,abs=1e-8)
    assert out['feedback']['errors']['RY[2]']==pytest.approx(y-.01,abs=1e-10)
    assert out['operating_values']['power.1']==pytest.approx(500*y,abs=1e-8)
    np.testing.assert_allclose(out['support_force'],[0,-500*y,0],atol=1e-8)
    assert out['residual']<1e-9


@pytest.mark.parametrize('variable,ki,command,integral',[
    ('command.E1',0,7,None),('command.RY[2]',0,2.035,None),('command.RY[2]',100,2.01,-.05)])
def test_command_trim_reaches_force_target_with_correct_bias_and_integral(variable,ki,command,integral):
    control=law(kd=0,ki=ki)
    out=solve_static(configuration(),condition(),4,gravity=[0,0,0],controller=control,
        operating_constraints=[dict(variable=variable,quantity='force.y',target=5)])
    assert out['sensors'][1]['displacement_body'][1]==pytest.approx(.01,abs=1e-10)
    assert out['feedback']['actuators']['E1']==pytest.approx(5,abs=1e-8)
    assert out['feedback']['commands'][variable.removeprefix('command.')]==pytest.approx(command,abs=1e-8)
    assert out['operating_constraints'][0]['actual']==pytest.approx(5,abs=1e-8)
    assert out['controller_equilibrium']['solved_commands'][variable]==pytest.approx(command,abs=1e-8)
    if integral is not None:
        assert out['feedback']['integrals']['RY[2]']==pytest.approx(integral,abs=1e-9)
        assert out['feedback']['errors']['RY[2]']==pytest.approx(0,abs=1e-10)
    json.dumps(out,allow_nan=False)


def test_trimmed_commands_are_frozen_in_modes_and_bode_but_actuators_remain_dynamic():
    targets=[dict(variable='command.RY[2]',quantity='force.y',target=5)]
    modes=solve_modes(configuration(),condition(),4,gravity=[0,0,0],controller=law(),
        operating_constraints=targets,count=2)
    roots_match(modes,np.roots([2,30,700]))
    assert modes['controller']['commands']['RY[2]']==pytest.approx(2.035,abs=1e-8)
    assert modes['controller']['bias']['E1']==0
    assert modes['base']['feedback']['actuators']['E1']==pytest.approx(5,abs=1e-8)
    assert modes['base']['steady_trim']['operating_constraints'][0]['actual']==pytest.approx(5,abs=1e-8)
    response=solve_frequency_response(configuration(),condition(),4,gravity=[0,0,0],controller=law(),
        operating_constraints=targets,frequencies=[0,10],inputs=['power.1','command.RY[2]'])
    for point in response['samples']:
        s=1j*point['omega'];den=2*s*s+30*s+700
        for i,numerator in enumerate((1,200)):
            assert z(point['responses'][i]['output']['sensors'][1]['displacement_body'])[1]==pytest.approx(numerator/den,abs=2e-8)


def test_feedback_can_make_a_trim_target_solvable_when_open_loop_is_rank_deficient():
    from test_time_integration import rigid_body
    source=rigid_body().dumps()+'\nEngine\n1 0 1 0 0 0 0 1 0 0 1 0 -1 0 0\nEnd\n'
    model=parse_asw(source)
    control={'commands':{'V':8},'outputs':[{'actuator':'E1','terms':[{'input':'V',
        'gain':{'speed':[5,15],'density':[0],'values':[[2.5,3.5]]}}]}]}
    targets=[dict(variable='speed',quantity='force.x',target=0)]
    with pytest.raises(AnalysisError,match='mechanism|redundant'):
        solve_static(model,condition(),4,gravity=[0,0,0],operating_constraints=targets)
    out=solve_modes(model,condition(),4,gravity=[0,0,0],controller=control,
        operating_constraints=targets,frame='free',count=16,tolerance=1e-11)
    assert out['base']['operating_values']['speed']==pytest.approx(8,abs=1e-8)
    assert out['base']['feedback']['actuators']['E1']==pytest.approx(0,abs=1e-8)
    assert min(abs(complex(*m['eigenvalue'])+2.8) for m in out['modes'])<2e-6


def test_aerodynamic_lift_and_pitch_trim_keep_the_control_law_in_the_coupled_solve():
    source=Path('examples/rectangular.asw').read_text().split('t dCLdF1')[0]
    source+='t Cm dCMdF1\n0 -.04 -.012\n6 -.04 -.012\nEnd\n'
    model=parse_asw(source);c=FlightCondition(alpha=1,mach=0)
    open_loop=solve_static(model,c,8,operating_constraints=[dict(variable='alpha',quantity='lift',target=2000),
        dict(variable='control.1',quantity='moment.y',target=0)])
    control={'commands':{'A':1},'outputs':[{'actuator':'F1','terms':[{'input':'A','gain':-2}]}]}
    out=solve_static(model,c,8,controller=control,operating_constraints=[dict(variable='alpha',quantity='lift',target=2000),
        dict(variable='command.F1',quantity='moment.y',target=0)])
    alpha=out['operating_values']['alpha']
    assert alpha==pytest.approx(open_loop['operating_values']['alpha'],abs=1e-7)
    assert out['feedback']['actuators']['F1']==pytest.approx(-.04/.012,abs=1e-8)
    assert out['feedback']['commands']['F1']==pytest.approx(-.04/.012+2*(alpha-1),abs=1e-8)
    np.testing.assert_allclose(out['force'],open_loop['force'],atol=1e-6)
    assert out['operating_constraints'][0]['actual']==pytest.approx(2000,abs=1e-6)


def test_pose_unknown_is_seen_by_global_and_sensor_controller_measurements():
    control=law(ki=100);control['commands']={'RY[2]':2.01}
    out=solve_static(configuration(),condition(),4,controller=control,gravity=[0,0,0],
        operating_constraints=[dict(variable='position_earth.y',quantity='power.1',target=2)])
    assert out['operating_values']['position_earth.y']==pytest.approx(.006,abs=1e-9)
    assert out['feedback']['measurements']['RY[2]']==pytest.approx(2.01,abs=1e-9)
    assert out['feedback']['integrals']['RY[2]']==pytest.approx(-.02,abs=1e-8)


def test_four_control_commands_preserve_all_six_load_targets_in_elastic_climbing_turn():
    from openswing.operating import steady_turn_constraints
    from dataclasses import replace
    model=parse_asw(Path('examples/trim-aircraft.asw').read_text())
    c=FlightCondition(alpha=4,mach=0,powers={1:120},attitude=(0,4,57))
    targets=steady_turn_constraints(np.deg2rad(3),2,trim_controls=[2,1,3],engine_control=1)
    reference=solve_static(model,c,4,operating_constraints=targets,tolerance=1e-11)
    control={'outputs':[dict(actuator=actuator,terms=[dict(input=signal,gain=gain)])
        for actuator,signal,gain in [('F1','A',-.7),('F2','Ex',-.3),('F3','Wz',-.1),('E1','V',.5)]]}
    command_targets=[replace(t,variable='command.F'+t.variable.split('.')[1]) if t.variable.startswith('control.')
        else replace(t,variable='command.E'+t.variable.split('.')[1]) if t.variable.startswith('power.') else t for t in targets]
    out=solve_static(model,c,4,controller=control,operating_constraints=command_targets,tolerance=1e-11)
    assert len(out['operating_constraints'])==16
    assert max(abs(t['normalized_residual']) for t in out['operating_constraints'])<1e-8
    np.testing.assert_allclose(out['applied_force'],0,atol=1e-5)
    np.testing.assert_allclose(out['applied_moment'],0,atol=1e-5)
    for axis in 'xyz':
        assert out['operating_values']['rates.'+axis]==pytest.approx(reference['operating_values']['rates.'+axis],abs=1e-8)
    for actuator in ('F1','F2','F3','E1'):
        key=('control.' if actuator[0]=='F' else 'power.')+actuator[1:]
        assert out['feedback']['actuators'][actuator]==pytest.approx(reference['operating_values'][key],abs=1e-6)
    np.testing.assert_allclose([n['position'] for n in out['nodes']],[n['position'] for n in reference['nodes']],atol=1e-7)
    assert abs(out['feedback']['commands']['F1']-out['feedback']['actuators']['F1'])>.01


def test_redundant_pi_bias_trim_is_rejected_even_at_zero_residual():
    with pytest.raises(AnalysisError,match='singular|nonunique'):
        solve_static(configuration(),condition(),4,controller=law(ki=100),gravity=[0,0,0],
            operating_constraints=[dict(variable='command.E1',quantity='force.y',target=0)])


def test_actuator_constraint_cannot_silently_overwrite_the_controller():
    with pytest.raises(AnalysisError,match='command.E1'):
        solve_static(configuration(),condition(),4,controller=law(),gravity=[0,0,0],
            operating_constraints=[dict(variable='power.1',quantity='force.y',target=1)])


def test_bridge_steady_controller_result_and_unsupported_combination_diagnostics():
    request=dict(action='solve',mode='mounted',source=configuration().dumps(),panels=4,
        condition=dict(speed=10,alpha=0,mach=0,gravity_magnitude=0),controller=law(ki=100))
    out=dispatch(request)
    assert out['feedback']['integrals']['RY[2]']==pytest.approx(0,abs=1e-9)
    assert out['controller']['integral_channels']==['RY[2]']
    derivative=dispatch({**request,'derivatives':dict(parameters=['command.E1'])})['derivatives']
    assert derivative['controller']['integral_channels']==['RY[2]']
    np.testing.assert_allclose(derivative['matrices']['positions'],0,atol=1e-8)
    with pytest.raises(ValueError,match='requires mounted'):
        dispatch({**request,'mode':'rigid'})
