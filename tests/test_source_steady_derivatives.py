"""Source implicit derivatives against mechanics and fresh nonlinear states."""
from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path
import numpy as np
import pytest

from openswing.bridge import dispatch
from openswing.operating import free_flight_constraints
from test_source_airflow_trim import trim_request


def retain(name, request, result):
    if folder := os.environ.get('SOURCE_STEADY_DERIVATIVES_EVIDENCE'):
        p=Path(folder);p.mkdir(parents=True,exist_ok=True)
        (p/(name+'.json')).write_text(json.dumps(dict(request=request,result=result),allow_nan=False)+'\n')


def feedback_row(d, name):
    index=next(i for i,row in enumerate(d['feedback_rows']) if row['name']==name)
    return np.asarray(d['matrices']['feedback'][index])


def test_rotating_source_bar_releases_trim_and_preserves_centrifugal_stiffness():
    value=trim_request();value['condition']['rates']=[0.,0.,.7]
    value['derivatives']=dict(parameters=['power.1','rates.z'],axes='body')
    before=deepcopy(value);out=dispatch(value);d=out['derivatives'];matrix=d['matrices']
    # k*delta=P+m*Omega^2*(L+delta), k=500, m=2. The original net
    # force target fixes delta=.01. Its row is released for the derivatives.
    stiffness=500-2*.7**2
    expected=np.array([1.,2*2*.7*2.01])/stiffness
    assert out['operating_values']['power.1']==pytest.approx(5-2*.7**2*2.01,abs=2e-8)
    np.testing.assert_allclose(np.asarray(matrix['positions'])[-1,1],expected,rtol=2e-7,atol=2e-9)
    np.testing.assert_allclose(np.asarray(matrix['section_strain'])[:,1],
                               np.tile(expected/2,(4,1)),rtol=2e-7,atol=2e-9)
    np.testing.assert_allclose(np.asarray(matrix['net_wrench'])[1],500*expected,rtol=2e-7,atol=2e-7)
    assert max(d['linear_residuals'])<1e-9
    assert d['section_output_fields']['section_strain']['sample_location']=='element constitutive average'
    assert 'nonorthogonal' in d['section_output_fields']['section_strain']['axes']
    assert value==before
    retain('rotating-bar',value,out)


@pytest.mark.parametrize('ki',[0.,100.])
def test_source_controller_command_derivatives_match_independent_closed_loop_spring(ki):
    from test_feedback import law
    value=trim_request();value['operating_constraints']=[]
    value['controller']=law(kd=0,ki=ki);value['controller']['commands']={'RY[2]':2.01}
    value['derivatives']=dict(parameters=['command.E1','command.RY[2]'])
    out=dispatch(value);d=out['derivatives']
    expected=np.array([0.,1.]) if ki else np.array([1.,200.])/700
    np.testing.assert_allclose(np.asarray(d['matrices']['positions'])[-1,1],expected,atol=2e-9,rtol=0)
    np.testing.assert_allclose(feedback_row(d,'actuators.E1'),500*expected,atol=2e-6,rtol=0)
    np.testing.assert_allclose(feedback_row(d,'measurements.RY[2]'),expected,atol=2e-9,rtol=0)
    if ki:np.testing.assert_allclose(feedback_row(d,'integrals.RY[2]'),[.01,-5.],atol=2e-7,rtol=0)
    assert d['base_operating_values']==out['operating_values']
    assert out['equilibrium_state']['launch']['controller']==value['controller']
    retain('controller-'+str(ki),value,out)


def test_source_free_flight_derivatives_match_drag_thrust_and_euler_equations():
    from test_volume import body_source
    mass=3.;g=9.80665;inertia=np.diag([2.,3.,4.]);area=.2
    attachments=(f'Ground\n1 0 0\nEnd\nWeight\n1 0 0 0 0 {mass*g} {area} 0 0 0 0 {2*g} {3*g} {4*g}\nEnd\n'
                 'Engine\n1 0 1 0 0 0 0 -1 0 0 10 0 0 0\nEnd\n')
    value=trim_request();value['source']=body_source(radius=0,attachments=attachments)
    value['condition'].update(speed=10.,alpha=8.,beta=-4.,density=1.225,rates=[.3,-.2,.4],powers={1:2.})
    value['operating_constraints']=[asdict(c) for c in free_flight_constraints()]
    value['derivatives']=dict(response='free_flight',basis='body')
    out=dispatch(value);d=out['derivatives'];a=np.asarray(d['matrices']['accelerations'])
    from openswing.aero import FlightCondition
    c=FlightCondition(**value['condition']);velocity=-c.speed*c.vectors()[0];omega=np.array(c.rates)
    expected=-.5*c.density*area*(c.speed*np.eye(3)+np.outer(velocity,velocity)/c.speed)/mass
    np.testing.assert_allclose(a[:3,:3],expected,atol=2e-8,rtol=0)
    for j,axis in enumerate(np.eye(3)):
        expected=-np.linalg.solve(inertia,np.cross(axis,inertia@omega)+np.cross(omega,inertia@axis))
        np.testing.assert_allclose(a[3:,3+j],expected,atol=2e-8,rtol=0)
    np.testing.assert_allclose(a[:,6],[-10/mass,0,0,0,0,0],atol=2e-8,rtol=0)
    np.testing.assert_allclose(d['matrices']['net_wrench'],0,atol=2e-7,rtol=0)
    assert max(d['linear_residuals'])<1e-9
    retain('free-body',value,out)


def test_source_free_wing_acceleration_retains_real_and_apparent_mass():
    from dataclasses import replace
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition, solve_rigid
    value=trim_request()
    value['source']=Path('examples/inertial.asw').read_text().replace('.008 -.03 -.012','0 0 -.012')
    value['condition']=dict(speed=15.,alpha=0.,mach=0.,gravity_magnitude=0.)
    value['operating_constraints']=[asdict(c) for c in free_flight_constraints()]
    value['derivatives']=dict(response='free_flight',parameters=['alpha'])
    out=dispatch(value)
    # Literal 100 kg point at (.1,0,0), with point-centered principal
    # inertias (500,100,550). Source mass reports deliberately do not claim
    # a generic energy-derived spatial matrix for their endpoint operator.
    arm=np.array([[0.,0.,0.],[0.,0.,-.1],[0.,.1,0.]])
    real=np.block([[100*np.eye(3),-100*arm],
                   [100*arm,np.diag([500.,100.,550.])-100*arm@arm]])
    mass=real+out['apparent_mass']['spatial_matrix']
    model=parse_asw(value['source'],beam_interpolation='drela-segspl-v1');c=FlightCondition(**value['condition'])
    h=1e-4
    plus,minus=[solve_rigid(model,replace(c,alpha=sign*np.rad2deg(h)),panels=4) for sign in (1,-1)]
    load=(np.r_[plus['force'],plus['moment']]-np.r_[minus['force'],minus['moment']])/(2*h)
    expected=np.linalg.solve(mass,load)
    actual=np.asarray(out['derivatives']['matrices']['accelerations'])[:,0]
    np.testing.assert_allclose(actual,expected,rtol=2e-6,atol=1e-7)
    assert np.linalg.norm(np.asarray(out['apparent_mass']['spatial_matrix']))>1
    assert np.linalg.norm(actual-np.linalg.solve(real,load))>1e-3
    np.testing.assert_allclose(out['derivatives']['matrices']['net_wrench'],0,atol=1e-5)
    retain('free-wing',value,out)


def test_source_aeroelastic_derivatives_match_complete_resolved_equilibria():
    from test_source_coupled import source
    value=trim_request();value.update(source=source(),gravity=[0.,0.,0.],operating_constraints=[])
    value['condition']=dict(speed=8.,alpha=4.,beta=2.,density=1.2,mach=0.,controls={1:.15},
                            rates=[.1,-.2,.3])
    parameters=['alpha','rates.z','control.1'];value['derivatives']=dict(parameters=parameters,axes='body')
    out=dispatch(value);d=out['derivatives'];assert out['max_displacement']>1e-4
    for column,name in enumerate(parameters):
        samples=[];h=2e-4
        for sign in (1,-1):
            trial=deepcopy(value);trial.pop('derivatives')
            if name=='alpha':trial['condition']['alpha']+=sign*np.rad2deg(h)
            elif name=='rates.z':trial['condition']['rates'][2]+=sign*h
            else:trial['condition']['controls'][1]+=sign*h
            samples.append(dispatch(trial))
        def positions(o):return np.array([n['position'] for n in o['nodes']])
        def wrench(o):return np.r_[o['force'],o['moment']]
        def strain(o):return np.array([s['strain'] for s in o['elements']])
        for key,extract,absolute in [('positions',positions,2e-7),('fluid_wrench',wrench,5e-6),('section_strain',strain,2e-7)]:
            expected=(extract(samples[0])-extract(samples[1]))/(2*h)
            np.testing.assert_allclose(np.asarray(d['matrices'][key])[...,column],expected,rtol=5e-5,atol=absolute)
    assert d['input_derivative_methods']['control.1']=='analytic fixed-geometry control partial'
    assert max(d['linear_residuals'])<1e-9
    retain('elastic-wing',value,out)
