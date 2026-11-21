"""Independent custom-controller state, nonlinear and implicit-loop references."""
from pathlib import Path
from copy import deepcopy
import json
import numpy as np
import pytest
from scipy.linalg import expm
from scipy.integrate import solve_ivp
from openswing.asw import parse_asw
from openswing.aero import AnalysisError
from openswing.network import solve_static
from openswing.linear_dynamics import solve_modes
from openswing.frequency_response import solve_frequency_response
from openswing.time_integration import solve_time
from openswing.control_expressions import Expression
from test_feedback import configuration,condition,roots_match,z


def lag_law(implicit=False):
    output=dict(actuator='E1',expression="state('lag')")
    if implicit:output=dict(actuator='E1',residual="actuator('E1')+.1*actuator('E1')**3-state('lag')-.1*state('lag')**3",residual_scale=1.)
    return dict(outputs=[output],parameters={'kp':200,'kd':20,'tau':.05},
        states=[dict(name='lag',initial=0,scale=10,unit='file engine setting',
            rate="(command('E1')-parameter('kp')*error('RY[2]')-parameter('kd')*error('UY[2]')-state('lag'))/parameter('tau')")])


def antiwindup_law():
    desired="command('E1')-200*error('RY[2]')-100*state('I')"
    return dict(outputs=[dict(actuator='E1',expression=f'clip({desired},-5,5)')],
        states=[dict(name='I',initial=0,scale=.1,unit='input L · input T',
            rate=f"error('RY[2]')-.1*(actuator('E1')-({desired}))")])


@pytest.mark.parametrize('implicit',[False,True])
def test_actuator_lag_poles_and_transfers_include_custom_state_and_implicit_output(implicit):
    control=lag_law(implicit);control['commands']={'RY[2]':2.01};before=deepcopy(control)
    modes=solve_modes(configuration(),condition(),4,count=3,gravity=[0,0,0],controller=control)
    roots_match(modes,np.roots([.1,2.5,55,700]),tolerance=2e-6)
    assert modes['base']['feedback']['states']['lag']==pytest.approx(500*2/700,abs=1e-7)
    assert modes['diagnostics']['state_layout']['feedback']['states']==['lag']
    assert modes['controller']['state_units']['lag']=='file engine setting'
    response=solve_frequency_response(configuration(),condition(),4,frequencies=[0,3,10,30],
        inputs=['power.1','command.RY[2]'],gravity=[0,0,0],controller=control)
    for point in response['samples']:
        s=1j*point['omega'];plant=2*s*s+10*s+500;den=(1+.05*s)*plant+200+20*s
        for i,numerator in enumerate((1,200)):
            output=point['responses'][i]['output'];y=numerator/den
            assert z(output['sensors'][1]['displacement_body'])[1]==pytest.approx(y,abs=2e-8)
            assert z(output['feedback']['states_lag'])==pytest.approx(plant*y,rel=1e-6,abs=1e-7)
            assert z(output['feedback']['state_rates_lag'])==pytest.approx(s*plant*y,rel=1e-6,abs=2e-6)
    assert control==before
    json.dumps(response,allow_nan=False)


def test_custom_expression_can_use_builtin_integrals_without_extra_filter_states():
    control={'parameters':{'kp':200},'outputs':[{'actuator':'E1','expression':
        "command('E1')-parameter('kp')*error('RY[2]')-20*error('UY[2]')-100*integral('RY[2]')"}]}
    out=solve_modes(configuration(),condition(),4,count=3,gravity=[0,0,0],controller=control)
    roots_match(out,np.roots([2,30,700,100]))
    assert out['controller']['integral_channels']==['RY[2]']


def test_custom_state_modes_preserve_physical_frequency_with_a_different_input_time_unit():
    # One input T is now two seconds. Preserve the physical aircraft and law:
    # accelerations scale by four, speeds by two, density by one quarter,
    # damping times/tau by one half, and the rate-feedback coefficient by half.
    source=Path('examples/instrumented-oscillator.asw').read_text().replace('T 1 s','T 2 s')
    source=source.replace('9.80665 1.225 340.294','39.2266 .30625 680.588').replace('1000 .02','1000 .01')
    from dataclasses import replace
    control=lag_law();control['parameters'].update(kd=10,tau=.025)
    out=solve_modes(parse_asw(source),replace(condition(),speed=20),4,count=3,gravity=[0,0,0],controller=control)
    roots_match(out,2*np.roots([.1,2.5,55,700]),tolerance=2e-6)


def test_lag_state_time_solution_refines_to_independent_matrix_exponential():
    control=lag_law();control['commands']={'RY[2]':2.}
    matrix=np.array([[0,1,0],[-250,-5,.5],[-4000,-400,-20]])
    errors=[]
    for dt in (.02,.01,.005):
        out=solve_time(configuration(),condition(),4,duration=.12,dt=dt,gravity=[0,0,0],controller=control,
            initial_loads=[dict(beam=1,t=2,force=[0,1,0])])
        error=[]
        assert out['snapshots'][0]['feedback']['states']['lag']==0
        for snapshot in out['snapshots']:
            sensor=snapshot['sensors'][1]
            actual=np.array([sensor['displacement_body'][1],sensor['anchor_velocity_body'][1],snapshot['feedback']['states']['lag']])
            reference=expm(matrix*snapshot['time'])@np.array([.002,0,0])
            error.append(np.linalg.norm((actual-reference)*[1,.05,.002]))
        errors.append(max(error))
    assert errors[1]<.5*errors[0] and errors[2]<.5*errors[1],errors


def test_saturated_antiwindup_equilibrium_and_linear_response_match_piecewise_physics():
    control=antiwindup_law();control['commands']={'RY[2]':2.02}
    result=solve_static(configuration(),condition(),4,gravity=[0,0,0],controller=control)
    assert result['feedback']['actuators']['E1']==pytest.approx(5,abs=1e-8)
    assert result['sensors'][1]['displacement_body'][1]==pytest.approx(.01,abs=1e-10)
    assert result['feedback']['states']['I']==pytest.approx(-.031,abs=1e-9)
    assert abs(result['feedback']['state_rates']['I'])<1e-9
    modes=solve_modes(configuration(),condition(),4,count=3,gravity=[0,0,0],controller=control)
    roots_match(modes,np.r_[np.roots([2,10,500]),-10],tolerance=2e-6)
    response=solve_frequency_response(configuration(),condition(),4,frequencies=[0,7],inputs=['command.RY[2]'],
        gravity=[0,0,0],controller=control)
    for point in response['samples']:
        output=point['responses'][0]['output'];s=1j*point['omega']
        assert abs(z(output['sensors'][1]['displacement_body'])[1])<1e-9
        assert z(output['feedback']['states_I'])==pytest.approx(19/(s+10),abs=1e-7)


def test_saturation_and_antiwindup_time_refine_to_an_independent_piecewise_ode():
    references=[];initial=np.zeros(3)
    for start,end,command in [(0,.02,0),(.02,.12,.05),(.12,.2,0)]:
        def rate(t,q):
            y,v,integral=q;error=y-command;desired=-200*error-100*integral;actual=np.clip(desired,-5,5)
            return [v,(actual-10*v-500*y)/2,error-.1*(actual-desired)]
        reference=solve_ivp(rate,(start,end),initial,rtol=2e-12,atol=2e-14,dense_output=True,max_step=.001)
        references.append((end,reference));initial=reference.y[:,-1]
    errors=[];forcing='time +RY[2]\n0 0\n.02 0\n.02 .05\n.12 .05\n.12 0\n.2 0'
    for dt in (.02,.01,.005):
        out=solve_time(configuration(),condition(),4,duration=.2,dt=dt,gravity=[0,0,0],controller=antiwindup_law(),forcing=forcing)
        error=[]
        for snapshot in out['snapshots']:
            sensor=snapshot['sensors'][1]
            actual=np.array([sensor['displacement_body'][1],sensor['anchor_velocity_body'][1],snapshot['feedback']['states']['I']])
            reference=next(solution for end,solution in references if snapshot['time']<=end+1e-12).sol(snapshot['time'])
            error.append(np.linalg.norm((actual-reference)*[1,.05,2]))
            assert abs(snapshot['feedback']['actuators']['E1'])<=5+1e-8
        errors.append(max(error))
    assert errors[1]<.65*errors[0] and errors[2]<.65*errors[1],errors


def test_two_implicit_actuators_retain_cross_coupling_and_direct_input_effects():
    source=Path('examples/instrumented-oscillator.asw').read_text()+'\nEngine\n2 0 1 2 0 2 0 0 1 0 1 0 -1 0 0\nEnd\n'
    control={'outputs':[dict(actuator='E1',residual="actuator('E1')+.2*actuator('E2')+200*error('RY[2]')-command('E1')"),
        dict(actuator='E2',residual="actuator('E2')-.3*actuator('E1')-command('E2')")]}
    out=solve_frequency_response(parse_asw(source),condition(),4,frequencies=[0,10],inputs=['power.1','power.2'],gravity=[0,0,0],controller=control)
    for point in out['samples']:
        s=1j*point['omega'];den=1.06*(2*s*s+10*s+500)+260
        for i,numerator in enumerate((1.3,.8)):
            assert z(point['responses'][i]['output']['sensors'][1]['displacement_body'])[1]==pytest.approx(numerator/den,abs=1e-8)


def test_scheduled_expression_parameter_derivative_enters_free_flight_modes():
    from test_time_integration import rigid_body
    source=rigid_body().dumps()+'\nEngine\n1 0 1 0 0 0 0 1 0 0 1 0 -1 0 0\nEnd\n'
    control={'commands':{'V':8},'parameters':{'k':{'speed':[5,15],'density':[0],'values':[[2.5,3.5]]}},
        'outputs':[dict(actuator='E1',expression="command('E1')+parameter('k')*error('V')")]}
    out=solve_modes(parse_asw(source),condition(),4,frame='free',count=16,controller=control,gravity=[0,0,0])
    assert min(abs(complex(*m['eigenvalue'])+3.2) for m in out['modes'])<2e-6


@pytest.mark.parametrize('expression',["abs(error('RY[2]'))","abs(measurement('Ay[2]'))"])
def test_state_and_rate_switching_tangents_are_rejected(expression):
    with pytest.raises(AnalysisError,match='one-sided tangents'):
        solve_modes(configuration(),condition(),4,count=2,gravity=[0,0,0],controller={'outputs':[dict(actuator='E1',expression=expression)]})


def test_command_only_switching_is_checked_in_the_harmonic_input_jacobian():
    with pytest.raises(AnalysisError,match='one-sided tangents'):
        solve_frequency_response(configuration(),condition(),4,frequencies=[10],inputs=['power.1'],gravity=[0,0,0],
            controller={'outputs':[dict(actuator='E1',expression="abs(command('E1'))")]})


def test_smooth_composite_of_nonsmooth_functions_keeps_its_valid_tangent():
    out=solve_modes(configuration(),condition(),4,count=2,gravity=[0,0,0],
        controller={'outputs':[dict(actuator='E1',expression="abs(error('RY[2]'))**2")]})
    roots_match(out,np.roots([2,10,500]))


def test_expression_is_lazy_in_conditional_branches_and_rejects_nonfinite_results():
    expression=Expression("where(state('x')>0,sqrt(state('x')),2)")
    assert expression({'state':{'x':-1}})==2
    assert expression({'state':{'x':4}})==2
    with pytest.raises(AnalysisError,match='nonfinite'):Expression('sqrt(-1)')({})
    with pytest.raises(AnalysisError,match='lower bound'):Expression('clip(0,1,-1)')({})


def test_inactive_conditional_schedule_does_not_evaluate_an_out_of_range_table():
    control={'parameters':{'high_speed_gain':{'speed':[20,30],'density':[0],'values':[[1,2]]}},
        'outputs':[dict(actuator='E1',expression="where(speed<15,command('E1'),parameter('high_speed_gain')*error('RY[2]'))")]}
    out=solve_modes(configuration(),condition(),4,count=2,gravity=[0,0,0],controller=control)
    roots_match(out,np.roots([2,10,500]))


@pytest.mark.parametrize('source',["__import__('os')",'x.attr','[x for x in [1]]','lambda x:x',
    "state('x')[0]","measurement(time)",'sum(1,2)','exp(x=1)','1e999','+'*5000,'True'])
def test_expression_rejects_code_and_unsupported_syntax(source):
    with pytest.raises(AnalysisError):Expression(source)


@pytest.mark.parametrize('mutate',[
    lambda c:c['states'][0].update(scale=0),lambda c:c['states'][0].update(unit=''),
    lambda c:c['states'][0].update(rate="state('missing')"),
    lambda c:c['outputs'][0].update(expression="parameter('missing')"),
    lambda c:c['outputs'][0].update(terms=[]),lambda c:c['outputs'][0].update(residual_scale=1),
])
def test_custom_controller_definition_errors_are_explicit(mutate):
    from openswing.network import StaticNetwork
    from openswing.feedback import FeedbackSystem
    control=lag_law();mutate(control)
    with pytest.raises(AnalysisError):FeedbackSystem(StaticNetwork(configuration(),4,condition(),[0,0,0],[]),control)
