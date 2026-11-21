"""Independent mechanical, algebraic-feedback and control-command checks."""
from copy import deepcopy
from pathlib import Path
import json
import numpy as np
import pytest
from scipy.linalg import expm
from scipy.optimize import linear_sum_assignment
from openswing.asw import parse_asw
from openswing.aero import FlightCondition,AnalysisError
from openswing.feedback import Gain
from openswing.control_tables import parse_control_tables,bind_control_tables
from openswing.time_integration import solve_time
from openswing.linear_dynamics import solve_modes
from openswing.frequency_response import solve_frequency_response


def configuration():
    return parse_asw(Path('examples/instrumented-oscillator.asw').read_text())

def condition():
    return FlightCondition(speed=10,alpha=0,mach=0)

def law(kp=200.,kd=20.,ki=0.,ka=0.):
    terms=[dict(input='RY[2]',gain=-kp),dict(input='UY[2]',gain=-kd)]
    if ki:terms.append(dict(input='RY[2]',gain=-ki,mode='integral'))
    if ka:terms.append(dict(input='Ay[2]',gain=-ka))
    return dict(outputs=[dict(actuator='E1',terms=terms)])

def z(value):
    return np.asarray(value['real'])+1j*np.asarray(value['imag'])

def roots_match(result,expected,tolerance=1e-7):
    actual=np.array([complex(*m['eigenvalue']) for m in result['modes']])
    cost=abs(actual[:,None]-expected)
    i,j=linear_sum_assignment(cost)
    assert max(cost[i,j])<tolerance


@pytest.mark.parametrize('ki,ka',[(0.,0.),(100.,0.),(0.,3.)])
def test_closed_loop_poles_and_transfers_match_independent_oscillator(ki,ka):
    control=law(ki=ki,ka=ka);before=deepcopy(control)
    m=2+ka;d=30.;k=700.
    out=solve_modes(configuration(),condition(),4,count=3 if ki else 2,gravity=[0,0,0],controller=control,matrices=True)
    roots_match(out,np.roots([m,d,k,ki] if ki else [m,d,k]))
    layout=out['diagnostics']['state_layout']['feedback']
    assert layout['actuators']==['E1']
    assert layout['integrals']==(['RY[2]'] if ki else [])
    response=solve_frequency_response(configuration(),condition(),4,frequencies=[0,3,10,30],
        inputs=['power.1','command.RY[2]'],gravity=[0,0,0],controller=control)
    for point in response['samples']:
        s=1j*point['omega'];den=m*s*s+d*s+k
        force=(s/(s*den+ki)) if ki else 1/den
        command=((200*s+ki)/(s*den+ki)) if ki else 200/den
        for column,expected in enumerate((force,command)):
            output=point['responses'][column]['output']
            assert z(output['sensors'][1]['displacement_body'])[1]==pytest.approx(expected,rel=2e-6,abs=3e-9)
            assert z(output['sensors'][1]['acceleration_sensor'])[1]==pytest.approx(s*s*expected,rel=2e-6,abs=3e-8)
            assert z(output['feedback']['actuators_E1'])==pytest.approx((2*s*s+10*s+500)*expected,rel=2e-6,abs=3e-7)
        if ki and s==0:
            assert z(point['responses'][0]['output']['feedback']['integrals_RY[2]'])==pytest.approx(1/ki,rel=1e-7)
    assert control==before
    json.dumps(response,allow_nan=False)


def test_gust_vane_feedback_retains_direct_input_feedthrough():
    control=dict(outputs=[dict(actuator='E1',terms=[dict(input='A[2]',gain=-2)])])
    out=solve_frequency_response(configuration(),condition(),4,frequencies=[3,10],
        inputs=[dict(kind='gust',wave='uniform')],controller=control,gravity=[0,0,0])
    for point in out['samples']:
        s=1j*point['omega'];output=point['responses'][0]['output']
        exact=-2*180/np.pi/10/(2*s*s+10*s+500)
        assert z(output['sensors'][1]['displacement_body'])[1]==pytest.approx(exact,abs=1e-8)


def test_pi_time_solution_refines_to_independent_matrix_exponential():
    control=law(ki=100);control['commands']={'RY[2]':2.}
    errors=[]
    matrix=np.array([[0,1,0],[-350,-15,-50],[1,0,0.]])
    initial=np.array([1/700,0,0])
    for dt in (.02,.01,.005):
        out=solve_time(configuration(),condition(),4,duration=.12,dt=dt,controller=control,gravity=[0,0,0],
            initial_loads=[dict(beam=1,t=2,force=[0,1,0])])
        actual=[]
        for snapshot in out['snapshots']:
            sensor=snapshot['sensors'][1]
            vector=np.array([sensor['displacement_body'][1],sensor['anchor_velocity_body'][1],snapshot['feedback']['integrals']['RY[2]']])
            reference=expm(matrix*snapshot['time'])@initial
            actual.append(np.linalg.norm((vector-reference)*[1,.05,20]))
            assert snapshot['residual']<1e-8
        errors.append(max(actual))
    assert errors[1]<.4*errors[0] and errors[2]<.4*errors[1],errors


def test_sensor_command_doubled_time_uses_left_then_right_and_relative_trim():
    out=solve_time(configuration(),condition(),4,duration=.08,dt=.02,controller=law(),gravity=[0,0,0],
        forcing='time +RY[2]\n0 0\n.03 0\n.03 .01\n.08 .01')
    at=next(s for s in out['snapshots'] if s['time']==.03)
    assert at['feedback']['commands']['RY[2]']==2.
    assert at['feedback']['actuators']['E1']==pytest.approx(0,abs=1e-10)
    later=next(s for s in out['snapshots'] if s['time']>.03)
    assert later['order']==1 and later['feedback']['commands']['RY[2]']==2.01
    assert later['feedback']['actuators']['E1']>0


def test_constant_nonzero_command_solves_closed_loop_integral_base():
    control=law(ki=100);control['commands']={'RY[2]':2.002}
    out=solve_modes(configuration(),condition(),4,count=3,controller=control,gravity=[0,0,0])
    base=out['base']
    assert base['sensors'][1]['position_earth'][1]==pytest.approx(2.002,abs=1e-9)
    assert base['feedback']['actuators']['E1']==pytest.approx(1,abs=1e-7)
    assert base['feedback']['integrals']['RY[2]']==pytest.approx(-.01,abs=1e-8)


def test_free_flight_scheduled_velocity_feedback_retains_gain_derivative():
    from test_time_integration import rigid_body
    source=rigid_body().dumps()+'\nEngine\n1 0 1 0 0 0 0 1 0 0 1 0 -1 0 0\nEnd\n'
    control={'commands':{'V':8},'outputs':[{'actuator':'E1','terms':[{'input':'V',
        'gain':{'speed':[5,15],'density':[0],'values':[[2.5,3.5]]}}]}]}
    out=solve_modes(parse_asw(source),condition(),4,frame='free',count=16,controller=control,gravity=[0,0,0])
    # One kg, F=(2+.1 V)(V-8); Vdot=-F. At V=10, dVdot/dV=-3.2.
    assert min(abs(complex(*m['eigenvalue'])+3.2) for m in out['modes'])<2e-6
    assert out['base']['feedback']['actuators']['E1']==pytest.approx(6,abs=1e-8)


def test_con_controller_runs_through_the_shared_dynamic_residual():
    source='1 7 2 -1\n1 1\n0\n0\n200\n1 8 2 -1\n1 1\n0\n0\n20\n'
    control={'con':source,'bindings':{'outputs':{'1':{'actuator':'E1'}},
        'inputs':{'2:7':{'input':'RY[2]'},'2:8':{'input':'UY[2]'}}}}
    out=solve_modes(configuration(),condition(),4,count=2,controller=control,gravity=[0,0,0])
    roots_match(out,np.roots([2,30,700]))
    assert out['controller']['definition']['con']==source


def test_schedule_kink_is_rejected_only_when_it_makes_the_dynamic_tangent_nonunique():
    from test_time_integration import rigid_body
    source=rigid_body().dumps()+'\nEngine\n1 0 1 0 0 0 0 1 0 0 1 0 -1 0 0\nEnd\n'
    control={'commands':{'V':8},'outputs':[{'actuator':'E1','terms':[{'input':'V',
        'gain':{'speed':[5,10,15],'density':[0],'values':[[2.5,3,4]]}}]}]}
    with pytest.raises(AnalysisError,match='slope break'):
        solve_modes(parse_asw(source),condition(),4,frame='free',count=12,controller=control,gravity=[0,0,0])
    # When error is zero, g(V)*(V-Vc) is differentiable even at the gain kink.
    control['commands']['V']=10
    out=solve_modes(parse_asw(source),condition(),4,frame='free',count=12,controller=control,gravity=[0,0,0])
    assert min(abs(complex(*m['eigenvalue'])+3) for m in out['modes'])<2e-5


def test_wrapped_controller_measurement_outputs_and_error_branch_guard():
    from dataclasses import replace
    from openswing.linear_dynamics import make_system,output_perturbation
    control={'outputs':[{'actuator':'E1','terms':[{'input':'Ez[2]','gain':.1}]}]}
    system,_=make_system(configuration(),replace(condition(),attitude=[0,0,180]),4,controller=control,gravity=[0,0,0])
    vector=np.zeros(system.size,dtype=complex)
    vector[:6*system.network.nn].reshape(-1,6)[:,5]=.1+.2j
    output=output_perturbation(system,vector,np.zeros_like(vector))
    expected=-(.1+.2j)*180/np.pi
    assert z(output['feedback']['measurements_Ez[2]'])==pytest.approx(expected,abs=2e-8)
    assert z(output['feedback']['errors_Ez[2]'])==pytest.approx(expected,abs=2e-8)
    control['commands']={'Ez[2]':0.}
    with pytest.raises(AnalysisError,match='branch cut'):
        solve_modes(configuration(),replace(condition(),attitude=[0,0,179.9999]),4,count=2,controller=control,gravity=[0,0,0])


def test_feedback_tolerances_and_modes_are_invariant_to_a_large_gps_origin():
    from dataclasses import replace
    model=configuration();control=law(ki=100)
    reference=np.roots([2,30,700,100])
    results=[]
    for origin in ([0,0,0],[2e5,1e6,-1e5]):
        result=solve_modes(model,replace(condition(),position_earth=origin),4,count=3,
            controller=control,gravity=[0,0,0])
        roots_match(result,reference,tolerance=3e-5)
        results.append(result)
    np.testing.assert_array_equal(results[0]['controller']['scales'],results[1]['controller']['scales'])


def test_gain_bilinear_scaling_and_explicit_extrapolation():
    # Independent affine-plus-cross polynomial, exact under bilinear interpolation.
    f=lambda x,y:2+3*x-4*y+.2*x*y
    x=[10,20,50];y=[1,2]
    table=dict(speed=x,density=y,values=[[f(a,b) for a in x] for b in y])
    assert Gain(table)(13,1.7)==pytest.approx(f(13,1.7))
    with pytest.raises(AnalysisError,match='outside'):Gain(table)(60,1.5)
    assert Gain({**table,'outside':'linear'})(60,.5)==pytest.approx(f(60,.5))
    assert Gain({**table,'outside':'hold'})(60,.5)==pytest.approx(f(50,1))
    assert Gain(dict(speed=[0],density=[0],values=[[3]]))(100,7)==3


@pytest.mark.parametrize('definition',[
    {},{'outputs':[]},{'outputs':[{'actuator':'E99','terms':[{'input':'V','gain':1}]}]},
    {'outputs':[{'actuator':'E1','terms':[{'input':'V[99]','gain':1}]}]},
    {'outputs':[{'actuator':'E1','terms':[{'input':'V','gain':float('nan')}]}]},
    {'outputs':[{'actuator':'E1','terms':[{'input':'V','gain':1,'mode':'derivative'}]}]},
])
def test_invalid_controllers_are_explicitly_rejected(definition):
    with pytest.raises((ValueError,AnalysisError)):
        solve_modes(configuration(),condition(),4,count=2,controller=definition,gravity=[0,0,0])


CON='''! Original example with explicit application bindings
1 7 2 -2
2 2
10 20
1 2
50 100
75 150
C- - - another table
1 8 2 -1
1 1
0
0
20
'''
def test_con_parser_preserves_indices_and_binds_gain_and_unit_factors():
    tables=parse_control_tables(CON)
    assert len(tables)==2 and tables[0]['sensor']==2
    bindings={'outputs':{'1':{'actuator':'E1','factor':2}},
        'inputs':{'2:7':{'input':'RY[2]','factor':.5},'2:8':{'input':'UY[2]'}},'outside':'linear'}
    control=bind_control_tables(CON,bindings)
    assert Gain(control['outputs'][0]['terms'][0]['gain'])(15,1.5)==pytest.approx(-187.5)
    assert Gain(control['outputs'][0]['terms'][1]['gain'])(10,1)==-40
    with pytest.raises(ValueError,match='bindings'):bind_control_tables(CON,{})
    with pytest.raises(ValueError,match='Incomplete'):parse_control_tables(CON.rsplit('\n20',1)[0])
    with pytest.raises(ValueError,match='Duplicate'):parse_control_tables(CON+CON)
