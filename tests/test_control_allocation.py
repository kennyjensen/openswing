from pathlib import Path
from copy import deepcopy
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import solve_static


def setup():
    m=parse_asw(Path('examples/redundant-thrust.asw').read_text())
    c=FlightCondition(speed=10,alpha=0,mach=0)
    constraints=[dict(variable='power.1',quantity='force.x',target=20,weight=1),
        dict(variable='power.2',quantity='minimum_control',weight=4),
        dict(variable='power.3',quantity='minimum_control',weight=2)]
    return m,c,constraints


def test_redundant_engines_match_weighted_projection_with_exact_load():
    m,c,targets=setup();before=deepcopy(targets)
    out=solve_static(m,c,4,gravity=[0,0,0],operating_constraints=targets)
    expected=np.array([40,5,10])/4.75
    actual=[out['operating_values'][f'power.{k}'] for k in (1,2,3)]
    np.testing.assert_allclose(actual,expected,atol=3e-6)
    assert out['applied_force'][0]==pytest.approx(20,abs=1e-8)
    report=out['control_allocation']
    assert report['objective']==pytest.approx(.5*np.sum(np.array([1,4,2])*expected**2),abs=1e-8)
    assert report['normalized_stationarity']<2e-6
    assert report['equality_residual']<1e-8
    assert min(report['reduced_curvatures'])>0
    assert targets==before


def test_two_hard_targets_and_preferred_settings_match_matrix_projection():
    m,c,targets=setup();preferred=np.array([1,-.5,2.]);weights=np.array([1,4,2.])
    targets[1].update(quantity='moment.z',target=0)
    for item,p in zip(targets,preferred):item['preferred']=p
    a=np.array([[2,1,1],[2,-1,0.]])
    expected=preferred+(a.T/weights[:,None])@np.linalg.solve((a/weights)@a.T,np.array([20,0])-a@preferred)
    out=solve_static(m,c,4,gravity=[0,0,0],operating_constraints=targets)
    np.testing.assert_allclose([out['operating_values'][f'power.{k}'] for k in (1,2,3)],expected,atol=2e-6)
    np.testing.assert_allclose([out['applied_force'][0],out['applied_moment'][2]],[20,0],atol=1e-8)
    assert out['control_allocation']['free_directions']==1
    # Reassign variable/target slots: no actuator is privileged as a pivot.
    targets[0]['variable']='power.3';targets[2]['variable']='power.1'
    targets[0].update(weight=2,preferred=2);targets[2].update(weight=1,preferred=1)
    again=solve_static(m,c,4,gravity=[0,0,0],operating_constraints=targets,initial_state=out['equilibrium_state'])
    np.testing.assert_allclose([again['operating_values'][f'power.{k}'] for k in (1,2,3)],expected,atol=2e-6)
    assert again['equilibrium_initialization']['initialization']=='saved physical equilibrium'
    saved=again['equilibrium_state']['launch']['released_constraints']
    assert [x['preferred'] for x in saved]==[2,-.5,1]


def test_nonlinear_actuator_disks_match_independent_thrust_parameter_optimization():
    from scipy.optimize import minimize_scalar
    source=Path('examples/redundant-thrust.asw').read_text()
    start=source.index('Engine\n');end=source.index('End\n',start)+4
    source=source[:start]+'Engine\n1 1 1 0 0 -1 0 -1 0 0 0 0 -.3 80 0\n2 1 1 0 0 1 0 -1 0 0 0 0 -.5 80 0\nEnd\n'+source[end:]
    m=parse_asw(source);c=FlightCondition(speed=10,alpha=0,mach=0,density=1.225)
    def power(thrust,radius):
        dv=np.sqrt(100+2*thrust/(1.225*np.pi*radius**2))-10
        return thrust*(10+(1+5*(10/(80*radius))**2)*dv/2)
    def objective(t):return .5*(power(t,.3)**2+3*power(20-t,.5)**2)
    optimum=minimize_scalar(objective,bounds=(0,20),method='bounded',options=dict(xatol=1e-11))
    expected=[power(optimum.x,.3),power(20-optimum.x,.5)]
    out=solve_static(m,c,4,gravity=[0,0,0],operating_constraints=[dict(variable='power.1',quantity='force.x',target=-20),dict(variable='power.2',quantity='minimum_control',weight=3)])
    np.testing.assert_allclose([out['operating_values'][f'power.{k}'] for k in (1,2)],expected,rtol=2e-6)
    assert out['applied_force'][0]==pytest.approx(-20,abs=1e-8)
    assert out['control_allocation']['objective']==pytest.approx(optimum.fun,rel=1e-10)
    assert min(out['control_allocation']['reduced_curvatures'])>1


def test_elastic_flap_allocation_preserves_the_loaded_wing_and_exact_lift_coefficient():
    source=Path('examples/flexible.asw').read_text().rsplit('End',1)[0]+'t dCLdF1 dCMdF1 dCLdF2 dCMdF2 dCLdF3 dCMdF3\n0 .03 -.004 .06 -.008 -.03 .004\n8 .03 -.004 .06 -.008 -.03 .004\nEnd\n'
    m=parse_asw(source);c=FlightCondition(speed=18,alpha=3,mach=0,controls={1:1.5})
    forward=solve_static(m,c,4,gravity=[0,0,0]);c.controls={}
    targets=[dict(variable='control.1',quantity='CL',target=forward['CL']),dict(variable='control.2',quantity='minimum_control',weight=4),dict(variable='control.3',quantity='minimum_control',weight=2)]
    out=solve_static(m,c,4,gravity=[0,0,0],operating_constraints=targets)
    np.testing.assert_allclose([out['operating_values'][f'control.{k}'] for k in (1,2,3)],[.6,.3,-.3],atol=4e-6)
    assert out['CL']==pytest.approx(forward['CL'],abs=1e-8)
    assert out['max_displacement']>1e-3
    np.testing.assert_allclose([n['position'] for n in out['nodes']],[n['position'] for n in forward['nodes']],atol=2e-7)


def test_saved_allocated_spring_base_releases_trim_in_frequency_response():
    from openswing.frequency_response import solve_frequency_response
    source=Path('examples/instrumented-oscillator.asw').read_text().replace('1 0 1 2 0 2 0 0 1 0 1 0 -1 0 0','1 0 1 2 0 2 0 0 1 0 1 0 -1 0 0\n2 0 1 2 0 2 0 0 1 0 2 0 -1 0 0')
    m=parse_asw(source);c=FlightCondition(speed=10,alpha=0,mach=0)
    targets=[dict(variable='power.1',quantity='force.y',target=5),dict(variable='power.2',quantity='minimum_control',weight=4)]
    out=solve_static(m,c,4,gravity=[0,0,0],operating_constraints=targets)
    np.testing.assert_allclose([out['operating_values'][f'power.{k}'] for k in (1,2)],[2.5,1.25],atol=2e-6)
    assert out['sensors'][1]['displacement_body'][1]==pytest.approx(.01,abs=1e-9)
    saved=deepcopy(out['equilibrium_state'])
    f=solve_frequency_response(m,c,4,gravity=[0,0,0],operating_constraints=targets,initial_state=saved,frequencies=[0,10],inputs=['power.2'])
    assert f['base']['control_allocation']['free_directions']==1
    for row in f['samples']:
        z=row['responses'][0]['output']['nodes'][-1]['displacement'];w=row['omega']
        assert z['real'][1]+1j*z['imag'][1]==pytest.approx(2/(500+10j*w-2*w*w),abs=1e-9)
    assert saved==out['equilibrium_state']


@pytest.mark.parametrize('edit,match',[
    (lambda x:x[1].update(variable='alpha'),'flap.*engine'),
    (lambda x:x[0].update(weight=0),'positive'),
    (lambda x:x[0].update(weight=True),'finite numbers'),
    (lambda x:x[0].update(preferred=np.inf),'finite numbers'),
    (lambda x:x[1].update(variable='power.1'),'more than once'),
    (lambda x:x[1].update(quantity='force.x'),'Duplicate'),
    (lambda x:x[1].update(target=3),'preferred settings'),
])
def test_invalid_allocation_definitions_fail_explicitly(edit,match):
    m,c,targets=setup();edit(targets)
    with pytest.raises(ValueError,match=match):solve_static(m,c,4,operating_constraints=targets)


def test_control_law_and_uncontrolled_redundant_actuators_share_hard_equations():
    m,c,targets=setup();targets=targets[:2]
    controller=dict(outputs=[dict(actuator='E3',expression='2')])
    out=solve_static(m,c,4,gravity=[0,0,0],operating_constraints=targets,controller=controller)
    # E3 is controller-owned and contributes 2 N. Remaining force: 2*E1+E2=18.
    expected=np.array([36,4.5])/4.25
    np.testing.assert_allclose([out['operating_values'][f'power.{k}'] for k in (1,2)],expected,atol=3e-6)
    assert out['feedback']['actuators']['E3']==pytest.approx(2,abs=1e-9)
    assert out['applied_force'][0]==pytest.approx(20,abs=1e-8)
    assert len(out['control_allocation']['controls'])==2


def test_unreachable_physical_target_is_not_replaced_by_a_soft_penalty():
    m,c,targets=setup();targets[0].update(quantity='force.z',target=1)
    with pytest.raises(ValueError,match='Weighted control trim failed'):
        solve_static(m,c,4,gravity=[0,0,0],operating_constraints=targets)


@pytest.mark.parametrize('base,preferred,match',[(1,-1,'not a local'),(1,0,'not numerically isolated'),(-1,-1,None)])
def test_optimality_checks_distinguish_stationary_maximum_flat_cost_and_minimum(base,preferred,match):
    from types import SimpleNamespace
    from openswing.operating import OperatingConstraint
    from openswing.control_allocation import allocate
    # On the unit circle, distance from (-1,0) is maximal at (1,0),
    # minimal at (-1,0), and distance from the origin is constant.
    # Each initial point is feasible and stationary, so an optimizer's success
    # flag alone is insufficient. This is an independent optimization reference.
    op=SimpleNamespace(minimum_indices=[1],constraints=[OperatingConstraint('control.1','circle',preferred=preferred),OperatingConstraint('control.2','minimum_control')],
        base={'control.1':base,'control.2':0},scale={'control.1':1,'control.2':1})
    residual=lambda x,factor:np.array([(base+x[0])**2+x[1]**2-1,0.])
    if match:
        with pytest.raises(ValueError,match=match):allocate(residual,np.zeros(2),op,0,tolerance=1e-9,continuation_steps=1)
    else:
        x,_,report=allocate(residual,np.zeros(2),op,0,tolerance=1e-9,continuation_steps=1)
        assert report['objective']==0
        assert report['reduced_curvatures'][0]==pytest.approx(1,abs=1e-10)
