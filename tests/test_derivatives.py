from dataclasses import replace
from pathlib import Path
import json
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid, AnalysisError
from openswing.network import solve_static
from openswing.operating import free_flight_constraints, steady_turn_constraints
from openswing.derivatives import stability_rotation
from openswing.propulsion import actuator_disk
from openswing.bridge import run_json
from test_volume import body_source


def aircraft(name):
    return parse_asw(Path(f'examples/{name}.asw').read_text())


def test_rigid_limit_velocity_scaling_and_independent_lifting_line_derivatives():
    m = aircraft('rectangular'); c = FlightCondition(alpha=5,mach=0,stall=False)
    r = solve_static(m,c,panels=8,derivatives={})
    d = r['derivatives']; a = np.asarray(d['matrices']['coefficients'])
    assert a[2,0] == pytest.approx(2*r['CL'],rel=2e-8)  # fixed BASE dynamic pressure
    assert a[3,3] < 0  # roll damping in conventional forward/down stability axes
    np.testing.assert_allclose(d['matrices']['positions'],0,atol=2e-8)
    np.testing.assert_allclose(d['matrices']['rotations'],0,atol=2e-8)
    rotation = stability_rotation(c.alpha); qs = .5*1.225*30**2*12
    h = 1e-4
    for j in (1,3,6):
        if j==1: cp,cm = replace(c,alpha=5+np.rad2deg(h)),replace(c,alpha=5-np.rad2deg(h))
        elif j==3:
            delta=rotation.T[:,0]*2*30/12*h
            cp,cm=replace(c,rates=delta),replace(c,rates=-delta)
        else: cp,cm=replace(c,controls={1:h}),replace(c,controls={1:-h})
        plus,minus = [solve_rigid(m,t,panels=8) for t in (cp,cm)]
        df=(np.array(plus['distributed_aero_force'])-minus['distributed_aero_force'])/(2*h)
        dm=(np.array(plus['distributed_aero_moment'])-minus['distributed_aero_moment'])/(2*h)
        expected=np.r_[(rotation@df)*[1,1,-1]/qs,(rotation@dm)/(qs*np.array([12,1,12]))]
        np.testing.assert_allclose(a[:,j],expected,rtol=3e-6,atol=1e-7)
    assert max(d['linear_residuals']) < 1e-10


def test_flexible_position_rotation_circulation_and_load_response_matches_resolved_states():
    m=aircraft('flexible');c=FlightCondition(alpha=5,mach=0)
    r=solve_static(m,c,panels=4,derivatives=dict(parameters=['alpha']))
    assert r['max_displacement']>1
    d=r['derivatives']['matrices'];h=2e-4
    plus,minus=[solve_static(m,replace(c,alpha=5+np.rad2deg(s*h)),panels=4) for s in (1,-1)]
    for field,result_key in [('fluid_wrench',None),('circulation',None),('positions',None),('internal_forces','force'),('internal_moments','moment')]:
        def values(result):
            if field=='fluid_wrench': return np.r_[result['force'],result['moment']]
            if field=='circulation': return np.array([v['circulation'] for v in result['strips'] if v['lifting']])
            if field=='positions': return np.array([n['position'] for n in result['nodes']])
            return np.array([e[result_key] for e in result['elements']])
        expected=(values(plus)-values(minus))/(2*h)
        np.testing.assert_allclose(np.asarray(d[field])[...,0],expected,rtol=2e-5,atol=2e-5)
    q0=np.array([n['rotation'] for n in r['nodes']])
    dq=(np.array([n['rotation'] for n in plus['nodes']])-np.array([n['rotation'] for n in minus['nodes']]))/(2*h)
    skew=dq@q0.transpose(0,2,1)
    expected=np.stack([skew[:,2,1],skew[:,0,2],skew[:,1,0]],axis=1)
    np.testing.assert_allclose(np.asarray(d['rotations'])[...,0],expected,rtol=2e-5,atol=3e-7)


def test_free_flight_body_response_matches_analytic_drag_thrust_and_gyroscopic_derivatives():
    g=9.80665;mass=3.; tensor=np.diag([2.,3.,4.]);cda=.2
    attachments=f'''Ground
1 0 0
End
Weight
1 0 0 0 0 {mass*g} {cda} 0 0 0 0 {2*g} {3*g} {4*g}
End
Engine
1 0 1 0 0 0 0 -1 0 0 10 0 0 0
End
'''
    m=parse_asw(body_source(radius=0,attachments=attachments))
    c=FlightCondition(alpha=8,beta=-4,mach=0,rates=(.3,-.2,.4),powers={1:2})
    r=solve_static(m,c,panels=4,operating_constraints=free_flight_constraints(),derivatives=dict(response='free_flight',basis='body'))
    d=r['derivatives']['matrices'];a=np.array(d['accelerations']);u=-c.speed*c.vectors()[0];w=np.array(c.rates)
    expected=-.5*1.225*cda*(c.speed*np.eye(3)+np.outer(u,u)/c.speed)/mass
    np.testing.assert_allclose(a[:3,:3],expected,atol=1e-8)
    for j,e in enumerate(np.eye(3)):
        expected=-np.linalg.solve(tensor,np.cross(e,tensor@w)+np.cross(w,tensor@e))
        np.testing.assert_allclose(a[3:,3+j],expected,atol=1e-8)
    np.testing.assert_allclose(a[:,6],[-10/mass,0,0,0,0,0],atol=1e-8)
    np.testing.assert_allclose(d['distributed_aero_wrench'],0,atol=1e-9)
    np.testing.assert_allclose(d['net_wrench'],0,atol=2e-7)
    assert np.linalg.norm(d['fluid_wrench'])>10


def test_free_flight_wing_acceleration_response_uses_real_plus_apparent_mass():
    m=aircraft('inertial');c=FlightCondition(alpha=5,mach=0)
    r=solve_static(m,c,panels=4,operating_constraints=free_flight_constraints(),
                   derivatives=dict(response='free_flight',parameters=['alpha']))
    mass=np.array(r['mass_properties']['spatial_matrix'])+r['apparent_mass']['spatial_matrix']
    h=1e-4
    p,n=[solve_rigid(m,replace(c,alpha=5+np.rad2deg(s*h)),panels=4) for s in (1,-1)]
    force=(np.r_[p['force'],p['moment']]-np.r_[n['force'],n['moment']])/(2*h)
    np.testing.assert_allclose(np.array(r['derivatives']['matrices']['accelerations'])[:,0],np.linalg.solve(mass,force),rtol=2e-6,atol=1e-7)
    np.testing.assert_allclose(r['derivatives']['matrices']['net_wrench'],0,atol=1e-5)


def test_body_origin_state_basis_preserves_origin_velocity_with_separate_references():
    mass=3.;g=9.80665;tensor=np.diag([2.,3.,4.])
    m=parse_asw(body_source(radius=0,attachments=f'Ground\n1 0 0\nEnd\nWeight\n1 0 0 0 0 {mass*g} .2 0 0 0 0 {2*g} {3*g} {4*g}\nEnd\n'))
    m.reference[2]=[.4,-.3,.2];m.reference[3]=[-.5,.7,.1]
    c=FlightCondition(alpha=7,beta=-3,mach=0,rates=(.3,-.2,.4));w=np.array(c.rates)
    r=solve_static(m,c,panels=4,operating_constraints=free_flight_constraints(),derivatives=dict(response='free_flight',basis='body_origin'))
    d=r['derivatives'];a=np.array(d['matrices']['origin_accelerations'])
    u=-c.speed*c.vectors()[0]-np.cross(w,m.reference[3]);v=np.linalg.norm(u)
    np.testing.assert_allclose(a[:3,:3],-.5*1.225*.2*(v*np.eye(3)+np.outer(u,u)/v)/mass,atol=1e-8)
    np.testing.assert_allclose(a[:3,3:],0,atol=1e-8)
    for j,e in enumerate(np.eye(3)):
        expected=-np.linalg.solve(tensor,np.cross(e,tensor@w)+np.cross(w,tensor@e))
        np.testing.assert_allclose(a[3:,3+j],expected,atol=1e-8)
    assert d['parameters'][3]['name']=='origin_rates.x'
    assert np.linalg.norm(np.array(d['matrices']['accelerations'])[:3,3:])>.1


def test_full_flight_trim_releases_controls_and_state_for_free_flight_derivatives():
    m=aircraft('trim-aircraft');c=FlightCondition(alpha=4,mach=0,powers={1:120})
    r=solve_static(m,c,panels=4,operating_constraints=steady_turn_constraints(.04,trim_controls=[2,1,3],engine_control=1),
                   derivatives=dict(response='free_flight',parameters=['control.1']))
    v=r['operating_values'];d=r['derivatives']
    assert d['base_operating_values']==v
    current=replace(c,alpha=v['alpha'],beta=v['beta'],attitude=[v[f'attitude.{k}'] for k in ('bank','elevation','heading')],
                    rates=[v[f'rates.{a}'] for a in 'xyz'],acceleration=[v[f'acceleration.{a}'] for a in 'xyz'],
                    angular_acceleration=[v[f'angular_acceleration.{a}'] for a in 'xyz'],
                    controls={k:v[f'control.{k}'] for k in m.controls},powers={1:v['power.1']})
    h=.002
    perturbed=[solve_static(m,replace(current,controls={**current.controls,1:current.controls[1]+s*h}),panels=4,
                           operating_constraints=free_flight_constraints()) for s in (1,-1)]
    accel=[np.array([r['operating_values'][f'{group}.{a}'] for group in ('acceleration','angular_acceleration') for a in 'xyz']) for r in perturbed]
    np.testing.assert_allclose(np.array(d['matrices']['accelerations'])[:,0],(accel[0]-accel[1])/(2*h),rtol=1e-4,atol=2e-6)
    assert abs(d['matrices']['accelerations'][4][0]) > .01


@pytest.mark.parametrize('axes',['body','reverse_stability'])
def test_output_axes_and_step_refinement(axes):
    m=aircraft('rectangular');c=FlightCondition(alpha=12,mach=0)
    base=solve_static(m,c,panels=4,derivatives=dict(parameters=['alpha'],axes='stability'))['derivatives']
    other=solve_static(m,c,panels=4,derivatives=dict(parameters=['alpha'],axes=axes,step=3e-6))['derivatives']
    # Dimensional body-axis outputs do not change with output presentation.
    np.testing.assert_allclose(base['matrices']['fluid_wrench'],other['matrices']['fluid_wrench'],rtol=1e-7,atol=2e-6)
    w=np.array(other['matrices']['distributed_aero_wrench'])[:,0]
    q=other['normalization']['dynamic_pressure_area'];r=np.array(other['output_rotation'])
    expected=np.r_[r@w[:3]/q,r@w[3:]/(q*np.array([12,1,12]))]
    np.testing.assert_allclose(np.array(other['matrices']['coefficients'])[:,0],expected,atol=1e-8)


@pytest.mark.parametrize('options,match',[(dict(step=0),'step'),(dict(parameters=['missing']),'parameters'),
    (dict(parameters=['alpha','alpha']),'parameters'),(dict(parameters=[]),'parameters'),
    (dict(axes='unknown'),'axes'),(dict(response='unknown'),'response'),(dict(response='free_flight'),'zero-net')])
def test_invalid_derivative_requests_fail_explicitly(options,match):
    with pytest.raises(AnalysisError,match=match):
        solve_static(aircraft('inertial'),FlightCondition(mach=0),panels=4,derivatives=options)


def test_wire_transition_is_not_reported_as_a_unique_derivative():
    m=parse_asw(body_source(radius=0,attachments='Ground\n1 0 0\nEnd\nStrut\n1 4 4 0 0 4 0 1 0 1000\nEnd\n'))
    with pytest.raises(AnalysisError,match='wire slack'):
        solve_static(m,FlightCondition(alpha=0,mach=0),panels=4,strut_mode='wire',derivatives=dict(parameters=['alpha']))


def test_engine_clipping_transition_is_detected():
    state=actuator_disk(0,1.225,30,.5,200,.001)
    power=state['minimum_power']+state['viscous_power']
    m=parse_asw(body_source(radius=0,attachments='Ground\n1 0 0\nEnd\nEngine\n1 1 1 0 0 0 0 -1 0 0 0 0 -.5 200 .001\nEnd\n'))
    with pytest.raises(AnalysisError,match='power-clipping'):
        solve_static(m,FlightCondition(alpha=0,mach=0,powers={1:power}),panels=4,derivatives=dict(parameters=['power.1']))


def test_bridge_derivatives_are_finite_and_reject_rigid_mode():
    request=dict(action='solve',source=Path('examples/rectangular.asw').read_text(),panels=4,mode='mounted',
                 condition=dict(mach=0),derivatives=dict(parameters=['alpha']))
    result=json.loads(run_json(json.dumps(request)))
    assert len(result['derivatives']['matrices']['positions'])==result['structural_nodes']
    request['mode']='rigid'
    with pytest.raises(ValueError,match='mounted'):run_json(json.dumps(request))
