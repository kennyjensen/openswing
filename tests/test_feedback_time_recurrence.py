"""Independent short controller-time mechanics; no production integration helpers."""
import json
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.time_integration import solve_time
from openswing.aero import FlightCondition

CASES=[('implicit_pi',2,False),('implicit_pi',5,True),('coupled_p',2,True),('coupled_p',5,False)]

def setup_case(kind):
    source=Path('examples/instrumented-oscillator.asw').read_text()
    if kind=='implicit_pi':
        controller={'commands':{'RY[2]':2.,'UY[2]':0.},'initial_integrals':{'RY[2]':.003},
            'outputs':[{'actuator':'E1','residual':"actuator('E1')+200*error('RY[2]')+20*error('UY[2]')+100*integral('RY[2]')",'residual_scale':1.}]}
        matrix=np.array([[0.,1.,0.],[-350.,-15.,-50.],[1.,0.,0.]])
        initial=np.array([(1-100*.003)/700,0.,.003])
    else:
        source+='\nEngine\n2 0 1 2 0 2 0 0 1 0 1 0 -1 0 0\nEnd\n'
        controller={'commands':{'RY[2]':2.},'outputs':[
            {'actuator':'E1','residual':"actuator('E1')+.2*actuator('E2')+200*error('RY[2]')",'residual_scale':1.},
            {'actuator':'E2','residual':"actuator('E2')-.3*actuator('E1')",'residual_scale':1.}]}
        stiffness=500+260/1.06
        matrix=np.array([[0.,1.],[-stiffness/2,-5.]])
        initial=np.array([1/stiffness,0.])
    return parse_asw(source),controller,matrix,initial

def bdf(matrix,current,previous,h,hp):
    if previous is None:
        return np.linalg.solve(np.eye(len(current))-h*matrix,current)
    # Differentiate the degree-two interpolant through t-h-hp, t-h, t.
    c0=(2*h+hp)/(h*(h+hp));c1=-(h+hp)/(h*hp);c2=h/(hp*(h+hp))
    return np.linalg.solve(c0*np.eye(len(current))-matrix,-c1*current-c2*previous)

def radau(matrix,current,h):
    # Independent [2/3] Pade stability function of three-stage Radau IIA.
    z=h*matrix;eye=np.eye(len(current));z2=z@z;z3=z2@z
    return np.linalg.solve(eye-3*z/5+3*z2/20-z3/60,(eye+2*z/5+z2/20)@current)

@pytest.mark.parametrize('kind,order,checked',CASES,ids=['implicit-pi-bdf2-fixed','implicit-pi-radau-checked','coupled-p-bdf2-checked','coupled-p-radau-fixed'])
def test_short_controller_trajectory_matches_independent_discrete_mechanics(kind,order,checked,tmp_path):
    model,controller,matrix,expected=setup_case(kind)
    result=solve_time(model,FlightCondition(speed=10,alpha=0,mach=0),4,duration=.04,dt=.02,order=order,gravity=[0,0,0],
        controller=controller,initial_loads=[{'beam':1,'t':2,'force':[0,1,0]}],
        tolerance=1e-9,accuracy={'rtol':.1,'atol':.001} if checked else None)
    case=f'{kind}-{order}-{checked}'
    artifact=tmp_path
    (artifact/(case+'.json')).write_text(json.dumps(result,allow_nan=False)+'\n')
    assert result['converged'] and result['snapshots'][-1]['time']==.04
    assert result['rejected_steps']==0
    assert result['accepted_steps']==2
    assert result['actuator_constraints']==[]
    if checked:
        assert result['internal_steps']==4
        assert result['accuracy']['maximum_accepted_ratio']<=1
        assert result['accuracy']['rejected_nonlinear_steps']==0
    prior=None;prior_time=None;time=0.;rows=[]
    for index,row in enumerate(result['snapshots']):
        if index:
            h=row['time']-time
            if order==5:
                expected=radau(matrix,radau(matrix,expected,h/2),h/2) if checked else radau(matrix,expected,h)
            elif checked:
                # Startup uses two BDF1 halves; subsequent trials retain the
                # accepted midpoint predecessor for both variable-BDF2 halves.
                effective_first=prior is None
                half=bdf(matrix,expected,prior,h/2,None if prior is None else time-prior_time)
                end=bdf(matrix,half,None if effective_first else expected,h/2,h/2)
                prior,prior_time=half,time+h/2;expected=end
                assert row['restart']['older']['time']==pytest.approx(prior_time,abs=1e-14)
                np.testing.assert_allclose(row['restart']['older']['local_velocity'][-1][1],half[1],atol=2e-8,rtol=2e-7)
            else:
                end=bdf(matrix,expected,prior,h,None if prior is None else time-prior_time)
                prior,prior_time=expected,time;expected=end
            time=row['time']
        actual=[row['sensors'][1]['displacement_body'][1],row['sensors'][1]['anchor_velocity_body'][1]]
        if kind=='implicit_pi':actual.append(row['feedback']['integrals']['RY[2]'])
        np.testing.assert_allclose(actual,expected,atol=2e-8,rtol=2e-7)
        forces=row['feedback']['actuators']
        expected_forces=[-200*expected[0]-20*expected[1]-100*expected[2]] if kind=='implicit_pi' else [-200*expected[0]/1.06,-60*expected[0]/1.06]
        np.testing.assert_allclose(list(forces.values()),expected_forces,atol=2e-7,rtol=2e-7)
        assert row['residual']<=1e-8
        if index:
            np.testing.assert_allclose(row['local_acceleration'][-1][1],(matrix@expected)[1],atol=2e-7,rtol=2e-7)
            if order==5:
                assert row['collocation']['stages']==3
                assert row['collocation']['maximum_stage_residual']<=row['collocation']['stage_tolerance']
            if checked:assert 'controller' in row['accuracy']['group_ratios']
        rows.append({'time':row['time'],'actual':actual,'expected':expected.tolist(),'expected_forces':expected_forces,'residual':row['residual']})
    (artifact/(case+'-oracle.json')).write_text(json.dumps(rows,indent=2)+'\n')
