"""Closed-loop equilibrium derivatives against independent mechanics and re-solves."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import json
import numpy as np
import pytest
from openswing.aero import FlightCondition, AnalysisError
from openswing.asw import parse_asw
from openswing.network import solve_static
from openswing.operating import free_flight_constraints
from openswing.derivatives import linearize_equilibrium
from openswing.steady_feedback import solve_feedback_base
from openswing.frequency_response import solve_frequency_response
from test_feedback import configuration, condition, law, z
from test_time_integration import rigid_body


def feedback_row(result, name):
    d=result['derivatives']
    i=next(i for i,row in enumerate(d['feedback_rows']) if row['name']==name)
    return np.array(d['matrices']['feedback'][i])


@pytest.mark.parametrize('ki',[0.,100.])
def test_independent_spring_command_bias_and_integral_equilibrium_derivatives(ki):
    controller=law(kd=0,ki=ki);controller['commands']={'RY[2]':2.01}
    original=deepcopy(controller)
    r=solve_static(configuration(),condition(),4,gravity=[0,0,0],controller=controller,
        derivatives=dict(parameters=['command.E1','command.RY[2]']))
    dy=np.array([0.,1.]) if ki else np.array([1.,200.])/700
    np.testing.assert_allclose(np.array(r['derivatives']['matrices']['positions'])[-1,1],dy,atol=2e-9)
    np.testing.assert_allclose(feedback_row(r,'actuators.E1'),500*dy,atol=2e-6)
    np.testing.assert_allclose(feedback_row(r,'measurements.RY[2]'),dy,atol=2e-9)
    np.testing.assert_allclose(feedback_row(r,'errors.RY[2]'),dy-[0,1],atol=2e-9)
    np.testing.assert_allclose(feedback_row(r,'commands.E1'),[1,0],atol=2e-9)
    if ki:np.testing.assert_allclose(feedback_row(r,'integrals.RY[2]'),[1/ki,-500/ki],atol=2e-7)
    assert controller==original
    assert r['derivatives']['base_operating_values']==r['operating_values']
    assert r['derivatives']['controller']['commands']['RY[2]']==2.01
    json.dumps(r,allow_nan=False)


def test_custom_lag_equilibrium_state_response_matches_independent_dc_and_full_descriptor():
    controller=json.loads(Path('examples/actuator-lag-controller.json').read_text())
    inputs=['command.E1','command.RY[2]']
    r=solve_static(configuration(),condition(),4,gravity=[0,0,0],controller=controller,
        derivatives=dict(parameters=inputs))
    expected=np.array([1,200])/700
    np.testing.assert_allclose(feedback_row(r,'states.lag'),500*expected,atol=2e-6)
    np.testing.assert_allclose(feedback_row(r,'state_rates.lag'),0,atol=2e-5)
    dynamic=solve_frequency_response(configuration(),condition(),4,gravity=[0,0,0],controller=controller,
        frequencies=[0.],inputs=['power.1','command.RY[2]'])
    for j,response in enumerate(dynamic['samples'][0]['responses']):
        assert z(response['output']['sensors'][1]['displacement_body'])[1]==pytest.approx(expected[j],abs=2e-9)


def test_nonlinear_implicit_controller_derivative_matches_cubic_spring_formula():
    controller=dict(commands={'RY[2]':2.1},outputs=[dict(actuator='E1',
        residual="actuator('E1')-command('E1')+200*error('RY[2]')+10000*error('RY[2]')**3")])
    r=solve_static(configuration(),condition(),4,gravity=[0,0,0],controller=controller,
        derivatives=dict(parameters=['command.E1','command.RY[2]']))
    roots=np.roots([10000,0,700,50])
    error=next(v.real for v in roots if abs(v.imag)<1e-12)
    stiffness=200+30000*error**2
    assert r['feedback']['errors']['RY[2]']==pytest.approx(error,abs=1e-9)
    np.testing.assert_allclose(np.array(r['derivatives']['matrices']['positions'])[-1,1],
        np.array([1,stiffness])/(500+stiffness),rtol=1e-7,atol=2e-9)


def test_speed_schedule_derivative_keeps_nonzero_command_error_and_gain_slope():
    controller=dict(commands={'RY[2]':2.02},outputs=[dict(actuator='E1',terms=[dict(input='RY[2]',
        gain=dict(speed=[5,15],density=[0],values=[[-150,-250]]))])])
    r=solve_static(configuration(),condition(),4,gravity=[0,0,0],controller=controller,
        derivatives=dict(parameters=['speed','u']))
    dy=500*.02*10/700**2
    np.testing.assert_allclose(np.array(r['derivatives']['matrices']['positions'])[-1,1],dy*np.array([1,10]),rtol=2e-7,atol=1e-10)
    np.testing.assert_allclose(feedback_row(r,'actuators.E1'),500*dy*np.array([1,10]),rtol=2e-7,atol=1e-8)


def test_default_measurement_command_remains_fixed_when_flight_input_changes():
    controller=dict(outputs=[dict(actuator='E1',terms=[dict(input='V',gain=3)])])
    r=solve_static(configuration(),condition(),4,gravity=[0,0,0],controller=controller,
        derivatives=dict(parameters=['speed']))
    assert r['derivatives']['controller']['commands']['V']==10.
    assert feedback_row(r,'actuators.E1')[0]==pytest.approx(3.,abs=1e-8)
    assert feedback_row(r,'commands.V')[0]==pytest.approx(0.,abs=1e-10)
    assert r['derivatives']['matrices']['positions'][-1][1][0]==pytest.approx(3/500,abs=1e-9)


def test_offset_sensor_velocity_feedback_respects_the_selected_rate_reference():
    model=configuration();model.reference[3]=[.4,-.3,.2]
    r=solve_static(model,condition(),4,gravity=[0,0,0],controller=law(),
        derivatives=dict(parameters=['rates.z','origin_rates.z']))
    # Sensor 2 has x=.3. Holding U at x=.4 gives dUy/dWz=-.1;
    # holding body-origin U gives dUy/dWz=.3. Rates here use radians/T.
    sensor=np.array([-.1,.3]);dy=-20*sensor/700
    np.testing.assert_allclose(feedback_row(r,'measurements.UY[2]'),sensor,atol=2e-9)
    np.testing.assert_allclose(np.array(r['derivatives']['matrices']['positions'])[-1,1],dy,atol=2e-9)


def test_free_flight_acceleration_feedback_uses_closed_loop_effective_inertia():
    model=parse_asw(rigid_body().dumps()+'\nEngine\n1 0 1 0 0 0 0 1 0 0 1 0 -1 0 0\nEnd\n')
    controller=dict(commands={'V':10,'Ax':0},outputs=[dict(actuator='E1',terms=[
        dict(input='V',gain=3),dict(input='Ax',gain=-2)])])
    r=solve_static(model,condition(),4,gravity=[0,0,0],controller=controller,
        operating_constraints=free_flight_constraints(),
        derivatives=dict(response='free_flight',parameters=['speed','command.V','command.E1']))
    # m*a=3*(V-Vc)+bias-2*a, m=1.
    np.testing.assert_allclose(r['derivatives']['matrices']['accelerations'][0],[1,-1,1/3],atol=1e-8)
    np.testing.assert_allclose(feedback_row(r,'actuators.E1'),[1,-1,1/3],atol=1e-8)
    np.testing.assert_allclose(r['derivatives']['matrices']['net_wrench'],0,atol=1e-7)


def test_fourier_wing_closed_loop_flight_derivative_matches_fresh_nonlinear_solutions():
    source=Path('examples/flexible.asw').read_text().rsplit('End',1)[0]
    model=parse_asw(source+'t dCLdF1 dCMdF1\n0 .08 -.01\n8 .08 -.01\nEnd\n')
    c=FlightCondition(alpha=4.,mach=0.,circulation_modes={1:3},controls={1:2.})
    controller=dict(commands={'A':1.},outputs=[dict(actuator='F1',terms=[dict(input='A',gain=-.2)])])
    r=solve_static(model,c,4,gravity=[0,0,0],controller=controller,derivatives=dict(parameters=['alpha']))
    h=2e-4
    plus,minus=[solve_static(model,replace(c,alpha=c.alpha+np.rad2deg(sign*h)),4,gravity=[0,0,0],controller=controller) for sign in (1,-1)]
    d=r['derivatives']
    np.testing.assert_allclose(np.array(d['matrices']['fluid_wrench'])[:,0],
        (np.r_[plus['force'],plus['moment']]-np.r_[minus['force'],minus['moment']])/(2*h),rtol=5e-5,atol=5e-5)
    np.testing.assert_allclose(np.array(d['matrices']['positions'])[...,0],
        (np.array([n['position'] for n in plus['nodes']])-np.array([n['position'] for n in minus['nodes']]))/(2*h),rtol=5e-5,atol=1e-6)
    assert feedback_row(r,'actuators.F1')[0]==pytest.approx(-.2*180/np.pi,abs=1e-7)


def test_trimmed_bias_stays_at_solved_value_and_original_target_is_released():
    r=solve_static(configuration(),condition(),4,gravity=[0,0,0],controller=law(kd=0),
        operating_constraints=[dict(variable='command.E1',quantity='force.y',target=5)],
        derivatives=dict(parameters=['command.E1']))
    d=r['derivatives']
    assert d['controller']['bias']['E1']==pytest.approx(7,abs=1e-8)
    assert feedback_row(r,'actuators.E1')[0]==pytest.approx(500/700,abs=1e-8)
    assert d['matrices']['fluid_wrench'][1][0]==pytest.approx(500/700,abs=1e-8)
    assert r['operating_constraints'][0]['actual']==pytest.approx(5,abs=1e-8)


def test_linearization_does_not_mutate_network_controller_or_physical_base():
    n,state,control,_,_,_=solve_feedback_base(configuration(),condition(),4,gravity=[0,0,0],controller=law(ki=100))
    before=deepcopy((state.x,state.feedback,state.commands,control.commands,control.bias,control._linearization_reference))
    operating=n.operating;count=n.nfev
    linearize_equilibrium(n,state.x,feedback=control,feedback_state=state,parameters=['command.E1'])
    after=(state.x,state.feedback,state.commands,control.commands,control.bias,control._linearization_reference)
    for a,b in zip(before,after):
        if isinstance(a,np.ndarray):np.testing.assert_array_equal(a,b)
        else:assert a==b
    assert n.operating is operating and n.nfev==count and control.network is n


@pytest.mark.parametrize('expression,valid',[("abs(error('RY[2]'))",False),("abs(error('RY[2]'))**2",True)])
def test_complete_controller_residual_requires_a_unique_local_tangent(expression,valid):
    controller=dict(outputs=[dict(actuator='E1',expression="command('E1')-200*"+expression)])
    def solve():return solve_static(configuration(),condition(),4,gravity=[0,0,0],controller=controller,
        derivatives=dict(parameters=['command.E1']))
    if not valid:
        with pytest.raises(AnalysisError,match='one-sided'):solve()
    else:assert solve()['derivatives']['matrices']['positions'][-1][1][0]==pytest.approx(1/500,abs=1e-9)


def test_nonzero_feedback_at_gain_slope_break_and_actual_actuator_inputs_are_rejected():
    controller=dict(commands={'RY[2]':2.02},outputs=[dict(actuator='E1',terms=[dict(input='RY[2]',
        gain=dict(speed=[5,10,15],density=[0],values=[[-100,-200,-400]]))])])
    with pytest.raises(AnalysisError,match='gain-schedule slope'):
        solve_static(configuration(),condition(),4,gravity=[0,0,0],controller=controller,derivatives=dict(parameters=['speed']))
    with pytest.raises(AnalysisError,match='command.E'):
        solve_static(configuration(),condition(),4,gravity=[0,0,0],controller=law(),derivatives=dict(parameters=['power.1']))


def test_released_trim_with_unconstrained_integral_state_has_no_unique_steady_derivative():
    model=parse_asw(rigid_body().dumps()+'\nEngine\n1 0 1 0 0 0 0 1 0 0 1 0 -1 0 0\nEnd\n')
    controller=dict(commands={'V':10},outputs=[dict(actuator='E1',terms=[dict(input='V',gain=3),dict(input='V',gain=2,mode='integral')])])
    with pytest.raises(AnalysisError,match='tangent is singular'):
        solve_static(model,condition(),4,gravity=[0,0,0],controller=controller,
            operating_constraints=[dict(variable='speed',quantity='force.x',target=0)],
            derivatives=dict(parameters=['command.E1']))
