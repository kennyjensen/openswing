"""Independent field integrals, coordinate kinematics and immutable saved-state probes."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import json
import numpy as np
import pytest
from scipy.integrate import quad_vec
from openswing.aero import FlightCondition,evaluate_aerodynamics
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
from openswing.ground import body_to_earth
from openswing.flow_survey import survey,plane_grid
from openswing.network import solve_static
from openswing.time_integration import solve_time
from openswing.time_state import checkpoint
from test_volume import body_source


def test_external_vortex_survey_matches_direct_line_integrals_and_does_not_change_loads():
    m=parse_asw(Path('examples/rectangular.asw').read_text());meshes=model_meshes(m,4);mesh=meshes[0]
    c=FlightCondition(speed=10,alpha=0,mach=0,stall=False)
    gamma=np.linspace(.2,.7,len(mesh.tm));points=np.array([[-2,.7,2.],[1,-1,1.3],[.5,2,-1.]])
    original=evaluate_aerodynamics(m,c,meshes,gamma)
    probed=evaluate_aerodynamics(m,c,meshes,gamma,survey_positions=points)
    assert {k:v for k,v in probed.items() if k!='flow_survey'}==original
    expected=[]
    for point in points:
        value=np.zeros(3)
        for g,a,b,length in zip(gamma,mesh.r0,mesh.r1,mesh.length):
            core=max(.25,length)
            def line(a,d,hi):
                def integrand(t):
                    r=point-a-t*d
                    return np.cross(d,r)/(r@r+core**2)**1.5/(4*np.pi)
                return quad_vec(integrand,0,hi,epsabs=1e-12)[0]
            value+=g*(line(a,b-a,1)+line(b,np.array([1.,0,0]),np.inf)-line(a,np.array([1.,0,0]),np.inf))
        expected.append(value)
    np.testing.assert_allclose(probed['flow_survey']['velocity_body']['lifting'],expected,atol=2e-12)


def test_oblique_earth_plane_and_frame_relative_velocity_follow_rigid_kinematics():
    m=parse_asw(body_source(radius=0));m.reference[3]=[.3,-.4,.2]
    c=FlightCondition(speed=11,alpha=13,beta=-7,mach=0,rates=[.2,-.3,.4],attitude=[23,17,-31],
        position_earth=[2,3,5],gust=dict(type='uniform',velocity=[1,2,3]))
    plane=dict(origin=[1,2,3],normal=[1,2,3],direction=[2,-1,1],u=[-2,3],v=[-1,2],counts=[17,19])
    out=survey(m,plane=plane,coordinates='earth',condition=c,panels=4)
    R=body_to_earth(c.attitude);points=np.array(out['position_body']);earth=np.array(out['position_earth'])
    U=-c.speed*c.vectors()[0]-np.cross(c.rates,m.reference[3])
    expected=np.array([1,2,3])-(U+np.cross(c.rates,points))@R.T
    np.testing.assert_allclose(out['velocity']['relative'],expected,atol=1e-13)
    np.testing.assert_allclose(out['velocity']['air'],np.broadcast_to([1,2,3],earth.shape),atol=2e-15)
    normal=np.array(plane['normal'])/np.linalg.norm(plane['normal'])
    np.testing.assert_allclose((earth-plane['origin'])@normal,0,atol=2e-15)
    axes=np.array([out['plane'][key] for key in ('direction','transverse','normal')])
    np.testing.assert_allclose(axes@axes.T,np.eye(3),atol=4e-16)
    np.testing.assert_allclose(out['plane_velocity']['relative'],expected@axes.T,atol=1e-13)
    json.dumps(out,allow_nan=False)


def test_body_and_ground_masks_identify_nonfluid_samples():
    m=parse_asw(body_source(radius=.2));c=FlightCondition(speed=10,alpha=0,mach=0,ground_effect=1,position_earth=[0,0,1])
    out=survey(m,positions=[[2,0,0],[2,.3,0],[2,0,-2],[2,.3,-1]],condition=c)
    assert out['inside_body']==[True,False,False,False]
    assert out['fluid_side']==[True,True,False,True]
    assert out['valid']==[False,True,False,True]


def test_saved_controller_equilibrium_preserves_actual_actuator_and_source_state():
    m=parse_asw(Path('examples/instrumented-oscillator.asw').read_text())
    controller=dict(commands={'RY[2]':2.02},outputs=[dict(actuator='E1',expression="100*error('RY[2]')")])
    base=solve_static(m,FlightCondition(speed=10,alpha=0,mach=0),4,gravity=[0,0,0],controller=controller)
    saved=base['equilibrium_state'];before=deepcopy(saved)
    out=survey(m,positions=[[0,1,.5],[1,2,.4]],equilibrium_state=saved)
    assert saved==before and out['state_kind']=='saved_equilibrium'
    assert out['condition']['powers'][1]==pytest.approx(base['feedback']['actuators']['E1'])
    assert out['saved_state_residual']<=1e-8


def test_time_checkpoint_survey_keeps_gust_phase_circulation_and_restart_unchanged():
    m=parse_asw(Path('examples/rectangular.asw').read_text());c=FlightCondition(speed=10,alpha=0,mach=0,
        gust=dict(type='expression',components=['0','0','.1*sin(3*t)']))
    trajectory=solve_time(m,c,4,duration=.04,dt=.02,gravity=[0,0,0]);saved=checkpoint(trajectory,1);before=deepcopy(saved)
    points=[[0,1,2],[1,-2,1]];out=survey(m,positions=points,checkpoint=saved)
    assert saved==before and out['time']==.02
    np.testing.assert_allclose(out['velocity']['gust'],[[0,0,.1*np.sin(.06)]]*2,atol=1e-15)
    frozen=survey(m,positions=points,condition=out['condition'],panels=4,circulation=saved['state']['network']['circulation'])
    np.testing.assert_allclose(out['velocity']['lifting'],frozen['velocity']['lifting'],atol=1e-12)
    damaged=deepcopy(saved);damaged['state']['network']['circulation'][0]+=.5
    with pytest.raises(ValueError,match='inconsistent'):survey(m,positions=points,checkpoint=damaged)


@pytest.mark.parametrize('spec',[dict(normal=[0,0,0]),dict(normal=[1,0,0],direction=[2,0,0]),dict(counts=[2,True]),dict(u=[1,1]),dict(normal=[0,0,float('nan')]),dict(unknown=1)])
def test_invalid_plane_definitions_are_rejected(spec):
    with pytest.raises(ValueError):plane_grid(spec)


@pytest.mark.parametrize('controller_trim',[False,True])
def test_solved_trim_values_are_preserved_without_a_new_trim_solve(controller_trim):
    from test_feedback import configuration,condition,law
    m=configuration();c=condition()
    kwargs=dict(controller=law(kd=0,ki=100),operating_constraints=[dict(variable='command.RY[2]',quantity='force.y',target=5)]) if controller_trim else dict(operating_constraints=[dict(variable='power.1',quantity='power.1',target=5)])
    base=solve_static(m,c,4,gravity=[0,0,0],**kwargs);saved=deepcopy(base['equilibrium_state'])
    out=survey(m,positions=[[0,1,2]],equilibrium_state=saved)
    assert out['condition']['powers'][1]==pytest.approx(5,abs=1e-8)
    assert out['saved_state_residual']<1e-8
    assert saved==base['equilibrium_state']


@pytest.mark.parametrize('frozen',[False,True])
def test_point_source_doublet_survey_matches_regularized_tensor_in_pg_space(frozen):
    m=parse_asw(body_source(radius=0,attachments='Weight\n1 0 .1 -.2 .3 0 .2 .5\nEnd\n'))
    c=FlightCondition(speed=13,alpha=17,beta=-11,mach=.4,freeze_influences=frozen)
    points=np.array([[1.2,.9,1.1],[3.,-.8,1.5]]);out=survey(m,positions=points,condition=c,panels=4)
    e=np.array([1.,0,0]) if frozen else c.vectors()[0];pg=np.eye(3)+(1/np.sqrt(1-c.mach**2)-1)*np.outer(e,e)
    core=max(np.sqrt(.2/np.pi),np.cbrt(.5/np.pi));r=(points-[.1,-.2,.3])@pg.T;nu=.5*pg@e;r2=np.sum(r*r,axis=1);den=r2+core**2
    expected=(.2*r/den[:,None]**1.5+(nu*r2[:,None]-3*(r@nu)[:,None]*r)/den[:,None]**2.5)@pg*c.speed/(4*np.pi)
    np.testing.assert_allclose(out['velocity']['volume'],expected,atol=3e-15)


def test_solid_ground_has_no_normal_induced_flow_from_volume_and_vortices():
    source=Path('examples/rectangular.asw').read_text()+'\nWeight\n1 0 .1 -.2 .3 0 .2 .5\nEnd\n'
    m=parse_asw(source);points=[[x,y,-2] for x in [-2,0,3] for y in [-4,1,5]]
    out=survey(m,positions=points,condition=FlightCondition(speed=13,alpha=0,mach=0,ground_effect=1,position_earth=[0,0,2]),circulation=np.arange(sum(len(mesh.tm) for mesh in model_meshes(m,4) if mesh.beam.lifting))*.2,panels=4)
    for key in ('lifting','volume'):np.testing.assert_allclose(np.array(out['velocity'][key])[:,2],0,atol=3e-16)


@pytest.mark.parametrize('frozen',[False,True])
def test_body_survey_matches_adaptive_integral_of_distributed_singularities(frozen):
    m=parse_asw(body_source(rows='0 -2 0 0 .1 0 0\n2 0 0 0 .35 0 0\n4 2 0 0 .1 0 0\n'));beam=m.beams[0]
    c=FlightCondition(speed=13,alpha=17,mach=0,freeze_influences=frozen)
    e=np.array([1.,0,0]) if frozen else c.vectors()[0];points=np.array([[.2,.8,.5],[1.,-1.,.7]])
    out=survey(m,positions=points,condition=c,panels=20);expected=[]
    for point in points:
        def integrand(t):
            radius=float(beam.value('radius',t));rd=float(beam.value('radius',t,derivative=1))
            r=point-beam.position(t);r2=r@r;den=r2+(radius/2)**2
            sigma=2*np.pi*radius*rd*e[0];nu=2*np.pi*radius**2*(e-[e[0],0,0])
            return c.speed/(4*np.pi)*(sigma*r/den**1.5+(nu*r2-3*(nu@r)*r)/den**2.5)
        expected.append(quad_vec(integrand,0,4,epsabs=1e-12)[0])
    np.testing.assert_allclose(out['velocity']['volume'],expected,rtol=3e-9,atol=1e-11)


def test_survey_jet_carries_prescribed_thrust_and_torque_across_wake_sections():
    from numpy.polynomial.legendre import leggauss
    source=body_source(radius=0,attachments='Engine\n1 0 1 0 0 0 0 -1 0 0 1 .03 .8 150 0\nEnd\n')
    m=parse_asw(source);c=FlightCondition(speed=25,alpha=0,mach=0,powers={1:100})
    # High-order polar integration of sampled velocity, independent of the
    # polynomial jet momentum coefficients and engine report.
    z,w=leggauss(96);rho=m.constants[1];dv=np.sqrt(25**2+2*100/(rho*np.pi*.8**2))-25
    contracted=.8*np.sqrt((25+dv/2)/(25+dv))
    for x in [1.,10.]:
        inner=max(0,contracted-.11*dv/(25+dv)*x);outer=contracted+.11*dv/(25+dv/2)*x
        r=np.r_[(z+1)*inner/2,inner+(z+1)*(outer-inner)/2];weights=np.r_[w*inner/2,w*(outer-inner)/2]
        out=survey(m,positions=np.column_stack([np.full_like(r,x),r,np.zeros_like(r)]),condition=c,panels=4)
        v=np.array(out['velocity']['jet']);rho=m.constants[1]
        linear=weights@(2*np.pi*r*rho*(25+v[:,0])*v[:,0]);angular=weights@(2*np.pi*r*r*rho*(25+v[:,0])*v[:,2])
        assert linear==pytest.approx(100,abs=2e-5)
        assert angular==pytest.approx(3,abs=1e-6)


@pytest.mark.parametrize('frozen',[False,True])
def test_deformed_engine_and_point_pylons_use_current_mounts_and_axes(frozen):
    from openswing.flow_survey import _steady
    from openswing.propulsion import jet_velocity
    source=Path('examples/flexible.asw').read_text()+'''\nEngine
1 0 1 4 .6 4 .8 -1 0 0 1 .02 .5 150 0
End
Weight
1 4 .6 4 .8 0 .1 .2
End
'''
    m=parse_asw(source);base=solve_static(m,FlightCondition(speed=20,alpha=5,mach=0,powers={1:40},freeze_influences=frozen),4,gravity=[0,0,0])
    saved=deepcopy(base['equilibrium_state']);n,state,options,data,_=_steady(m,saved)
    engines=base['engines'];engine=engines[0];point=np.array(engine['position']);axis=np.array(engine['axes'])[:,0]
    # Sample the downstream center and an off-axis point using the original
    # solved engine report, independently of the survey's mount reconstruction.
    e=data['condition'].vectors()[0];points=np.array([point+2*e,point+2*e+[0,.1,0]])
    out=survey(m,positions=points,equilibrium_state=saved)
    for field in ('position','axes'):engine[field]=np.asarray(engine[field])
    expected=jet_velocity(points,[engine],e,data['aero']['atmosphere']['density'])
    np.testing.assert_allclose(out['velocity']['jet'],expected,rtol=2e-10,atol=2e-10)
    assert np.linalg.norm(point-[.6,4,.8])>.001
    np.testing.assert_allclose(n.point_positions(data['r'],data['Q'])[0],point,atol=1e-12)
    # Physical mounts and jets stay current; frozen volume coefficients use jig sources.
    source_point=np.array([.6,4,.8]) if frozen else point
    influence_wind=np.array([1.,0,0]) if frozen else e
    pg=np.eye(3);r=points-source_point;r2=np.sum(r*r,axis=1);core=max(np.sqrt(.1/np.pi),np.cbrt(.2/np.pi));den=r2+core**2;nu=.2*influence_wind
    expected_volume=(.1*r/den[:,None]**1.5+(nu*r2[:,None]-3*(r@nu)[:,None]*r)/den[:,None]**2.5)*20/(4*np.pi)
    np.testing.assert_allclose(out['velocity']['volume'],expected_volume,atol=2e-12)
    assert saved==base['equilibrium_state']
