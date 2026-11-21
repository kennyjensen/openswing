"""Weak-limit field/load integrals and conservative concentrated-load transfer."""
from dataclasses import replace
from copy import deepcopy
import json
import numpy as np
import pytest
from scipy.integrate import quad_vec
from scipy.spatial.transform import Rotation
from openswing.asw import parse_asw
from openswing.aero import FlightCondition,solve_rigid
from openswing.geometry import model_meshes
from openswing.body_shoulders import shoulder_source,body_shoulders
from openswing.volume import VolumeField
from openswing.network import solve_static
from openswing.flow_survey import survey
from test_volume import body_source
from test_network import balanced


def step_source(left=.1,right=.3,width=0,closed=False):
    if closed:
        radii='0 0\n1 0\n1 .2\n3 .2\n3 0\n4 0'
    elif width:
        a,b=2-width/2,2+width/2
        radii=f'0 {left}\n{a} {left}\n{a} {left}\n{b} {right}\n{b} {right}\n4 {right}'
    else:radii=f'0 {left}\n2 {left}\n2 {right}\n4 {right}'
    return body_source(radius=0).replace('t x y z radius Cdf Cdp\n0 0 0 0 0 .01 1.2\n4 4 0 0 0 .01 1.2',f't x\n0 0\n4 4\nt radius\n{radii}\nt Cdf Cdp\n0 0 0\n4 0 0')


@pytest.mark.parametrize('radii',[(.1,.3),(.3,.1),(0.,.3),(.2,.2000000001)])
def test_collapsed_source_matches_area_integral_including_variable_core(radii):
    points=np.array([[.02,.001,0],[1.,-.4,.7],[-.5,.8,-1.1]])
    a,b=radii;coefficient=.87
    expected=quad_vec(lambda area:coefficient*points/(4*np.pi)/(np.sum(points*points,axis=1)[:,None]+area/(4*np.pi))**1.5,np.pi*a*a,np.pi*b*b,epsabs=1e-13)[0]
    np.testing.assert_allclose(shoulder_source(points,a,b,coefficient),expected,rtol=3e-7 if abs(a-b)<1e-8 else 2e-12,atol=2e-15)
    np.testing.assert_array_equal(shoulder_source(np.zeros((1,3)),a,b),0)


def test_smooth_transitions_converge_to_jump_field_and_force_without_core_choice():
    c=FlightCondition(speed=17,alpha=13,beta=-7,mach=.35);e=c.vectors()[0];pg=np.eye(3)+(1/np.sqrt(1-c.mach**2)-1)*np.outer(e,e)
    points=np.array([[2.1,.3,.2],[-1,.5,1],[5,-.7,.4]])
    jump=parse_asw(step_source());target=VolumeField(jump,model_meshes(jump,8),e,pg).velocity(points)
    errors=[];force=c.density if c.density else jump.constants[1]
    v=c.speed*e;s=np.array([1.,0,0]);expected=force*(v-(v@s)*s)*(v@s)*np.pi*(.3**2-.1**2)
    for width in [.2,.1,.05,.025]:
        m=parse_asw(step_source(width=width));meshes=model_meshes(m,8);field=VolumeField(m,meshes,e,pg)
        errors.append(np.linalg.norm(field.velocity(points)-target))
        assert not field.shoulders
        out=solve_rigid(m,c,8);np.testing.assert_allclose(out['body_force'],expected,atol=5e-12)
    assert all(b<a*.65 for a,b in zip(errors,errors[1:])),errors
    out=solve_rigid(jump,c,8);np.testing.assert_allclose(out['body_force'],expected,atol=3e-13)
    assert len(out['body_shoulders'])==1
    np.testing.assert_allclose(out['moment'],np.cross([2,0,0],expected),atol=5e-13)


def test_closed_stepped_body_has_zero_resultant_and_independent_munk_moment():
    m=parse_asw(step_source(closed=True));c=FlightCondition(speed=17,alpha=11,mach=0);v=c.speed*c.vectors()[0]
    out=solve_rigid(m,c,4)
    np.testing.assert_allclose(out['force'],0,atol=2e-13)
    np.testing.assert_allclose(out['moment'],[0,m.constants[1]*np.pi*.2**2*2*v[0]*v[2],0],atol=2e-13)
    assert [s['area_jump'] for s in out['body_shoulders']]==pytest.approx([np.pi*.2**2,-np.pi*.2**2])
    mounted=solve_static(m,c,4,gravity=[0,0,0]);balanced(mounted)
    np.testing.assert_allclose(mounted['force'],out['force'],atol=2e-9)
    np.testing.assert_allclose(mounted['moment'],out['moment'],atol=2e-9)
    # Internal force changes only at the two shoulders, with no artificial
    # distributed force density between them.
    assert all(np.linalg.norm(s['force'])<1e-14 for s in mounted['strips'])
    assert max(np.linalg.norm(s['force']) for s in mounted['body_shoulders'])>1
    survey(m,positions=[[2,.8,.3]],equilibrium_state=mounted['equilibrium_state'])


def test_pg_ground_image_includes_own_shoulder_and_preserves_impermeability():
    from openswing.ground import GroundPlane
    m=parse_asw(step_source());meshes=model_meshes(m,8);c=FlightCondition(alpha=0,mach=.3,position_earth=[0,0,2],ground_effect=1)
    e=c.vectors()[0];pg=np.diag([1/np.sqrt(1-.3**2),1,1]);field=VolumeField(m,meshes,e,pg,ground=GroundPlane.from_condition(c))
    points=np.array([[0,.4,-2],[2,.8,-2],[4,-1,-2]])
    np.testing.assert_allclose(field.velocity(points)[:,2],0,atol=2e-15)
    assert np.linalg.norm(field.velocity([2,0,0],exclude_body=m.beams[0].physical_index))>1e-5
    assert len(field.shoulders)==2


def test_radius_step_covariance_and_length_unit_scaling():
    m=parse_asw(step_source());meshes=model_meshes(m,8);q=Rotation.from_rotvec([.3,-.2,.4]).as_matrix();shift=np.array([1.,-2.,3.])
    e=np.array([.8,.6,0]);pg=np.eye(3)+.2*np.outer(e,e);points=np.array([[1,1,1],[3,-.8,.5]])
    base=VolumeField(m,meshes,e,pg).velocity(points)
    rotated=[]
    from openswing.geometry import surface_frame
    for mesh in meshes:
        rotated.append(replace(mesh,r0=mesh.r0@q.T+shift,r1=mesh.r1@q.T+shift,rm=mesh.rm@q.T+shift,frames=q@mesh.frames,
            frame0=q@surface_frame(mesh.beam,mesh.t0,'right'),frame1=q@surface_frame(mesh.beam,mesh.t1,'left')))
    np.testing.assert_allclose(VolumeField(m,rotated,q@e,q@pg@q.T).velocity(points@q.T+shift),base@q.T,atol=3e-15)
    for scale in [.001,1000.]:
        np.testing.assert_allclose(shoulder_source(points*scale,.1*scale,.3*scale),shoulder_source(points,.1,.3),rtol=8e-15,atol=1e-16)


@pytest.mark.parametrize('kind',['position','tangent'])
def test_undefined_coincident_geometry_breaks_require_a_resolved_transition(kind):
    m=parse_asw(step_source());mesh=model_meshes(m,8)[0];index=np.flatnonzero(mesh.t0==2)[0]
    if kind=='position':mesh.r0[index]+=[0,.1,0]
    else:
        from openswing.geometry import surface_frame
        mesh.frame0=surface_frame(mesh.beam,mesh.t0,'right');mesh.frame0[index]=Rotation.from_rotvec([0,0,.2]).as_matrix()@mesh.frame0[index]
    with pytest.raises(ValueError,match='explicit transition geometry'):body_shoulders(mesh)


def test_reversed_material_parameter_preserves_force_moment_and_volume_field():
    original=parse_asw(step_source());source=step_source().replace('0 0\n4 4\nt radius','0 4\n4 0\nt radius').replace('0 0.1\n2 0.1\n2 0.3\n4 0.3','0 0.3\n2 0.3\n2 0.1\n4 0.1');reverse=parse_asw(source)
    c=FlightCondition(speed=17,alpha=13,mach=.3)
    a,b=solve_rigid(original,c,8),solve_rigid(reverse,c,8)
    for key in ('force','moment'):np.testing.assert_allclose(a[key],b[key],atol=2e-12)
    for m in (original,reverse):assert len(solve_rigid(m,c,8)['body_shoulders'])==1
    points=[[1,.4,.5],[2.1,.3,0],[4,-1,1]]
    np.testing.assert_allclose(survey(original,positions=points,condition=c,panels=8)['velocity']['volume'],survey(reverse,positions=points,condition=c,panels=8)['velocity']['volume'],atol=2e-12)


def test_structural_reaction_and_flow_derivative_include_concentrated_body_lift():
    m=parse_asw(step_source(closed=True));c=FlightCondition(speed=17,alpha=11,mach=0)
    out=solve_static(m,c,4,gravity=[0,0,0],derivatives=dict(parameters=['alpha'],step=1e-5))
    derivative=np.asarray(out['derivatives']['matrices']['distributed_aero_wrench'])[:,0]
    expected=m.constants[1]*(2*np.pi*.2**2)*c.speed**2*np.cos(2*np.deg2rad(c.alpha))
    np.testing.assert_allclose(derivative,[0,0,0,0,expected,0],rtol=2e-8,atol=2e-8)


def test_unsteady_uniform_gust_preserves_exact_shoulder_reactions_and_checkpoint():
    from openswing.time_integration import solve_time
    from openswing.time_state import checkpoint,resume_time
    m=parse_asw(step_source(closed=True));c=FlightCondition(speed=10,alpha=0,mach=0,gust=dict(type='expression',components=['0','0','.2*sin(3*t)']))
    trajectory=solve_time(m,c,4,duration=.04,dt=.02,gravity=[0,0,0])
    for snap in trajectory['snapshots']:
        expected=m.constants[1]*(2*np.pi*.2**2)*10*.2*np.sin(3*snap['time'])
        np.testing.assert_allclose(snap['force'],0,atol=3e-8)
        np.testing.assert_allclose(snap['moment'],[0,expected,0],atol=3e-8)
        np.testing.assert_allclose(snap['support_moment'],[0,-expected,0],atol=3e-8)
        assert len(snap['body_shoulders'])==2
    saved=checkpoint(trajectory,1);before=deepcopy(saved);again=resume_time(m,saved,duration=.02)
    np.testing.assert_allclose(again['snapshots'][-1]['body_shoulders'][0]['force'],trajectory['snapshots'][-1]['body_shoulders'][0]['force'],atol=1e-9)
    assert before==saved
    field=survey(m,positions=[[2,.5,.3]],checkpoint=saved)
    assert field['saved_state_residual']<1e-8


def test_flexible_body_refinement_matches_independent_two_point_load_beam():
    source=step_source(closed=True).replace('t Cdf Cdp\n0 0 0\n4 0 0', 't Cdf Cdp\n0 0 0\n4 0 0\nt EIcc EInn GJ EA\n0 10000 10000 10000 10000000\n4 10000 10000 10000 10000000')
    m=parse_asw(source);c=FlightCondition(speed=5,alpha=1,mach=0);errors=[]
    for count in (4,8,16):
        out=solve_static(m,c,count,gravity=[0,0,0]);balanced(out)
        exact=sum(s['force'][2]*s['t']**2*(12-s['t'])/(6*10000) for s in out['body_shoulders'])
        tip=next(n for n in out['nodes'] if n['t']==4)['position'][2]
        errors.append(abs(tip-exact))
        grid=sorted(n['t'] for n in out['nodes'])
        # Midpoint rotation compatibility integrates quadratic slope by the
        # endpoint mean. Its exact linear-beam displacement error is -Σ(Fright h³)/(12 EI).
        predicted=-sum((b-a)**3*sum(s['force'][2] for s in out['body_shoulders'] if s['t']>(a+b)/2) for a,b in zip(grid,grid[1:]))/(12*10000)
        assert abs(tip-exact-predicted)<5e-10,(count,tip-exact,predicted)
        assert tip<0 and abs(tip)>1e-5
    assert errors[-1]<errors[1]*.3,errors
    assert errors[-1]<2e-7,errors


def test_shoulder_geometry_contains_annular_faces_at_both_discontinuities():
    from openswing.geometry import geometry_summary
    m=parse_asw(step_source(closed=True));mesh=model_meshes(m,4)[0];geometry=geometry_summary(m,meshes=[mesh])[0]
    caps=np.asarray(geometry['quads'])[12*len(mesh.tm):]
    assert caps.shape==(24,4,3)
    np.testing.assert_allclose(caps[:12][...,0],1,atol=1e-14)
    np.testing.assert_allclose(caps[12:][...,0],3,atol=1e-14)
    assert np.max(np.linalg.norm(caps[...,1:],axis=-1))==pytest.approx(.2)


def test_consistent_centimeter_units_preserve_physical_loads_and_flow():
    c=FlightCondition(speed=17,alpha=13,mach=.3);m=parse_asw(step_source())
    source=step_source(left=10,right=30).replace('t x\n0 0\n4 4','t x\n0 0\n4 400').replace('4 1 4','40000 100 400').replace('L 1 m','L 1 cm').replace('9.80665 1.225 340.294','980.665 1.225e-8 34029.4')
    cm=parse_asw(source);cc=replace(c,speed=c.speed*100)
    a,b=solve_rigid(m,c,8),solve_rigid(cm,cc,8)
    np.testing.assert_allclose(a['force'],b['force'],atol=3e-12)
    np.testing.assert_allclose(a['moment'],np.array(b['moment'])/100,atol=3e-12)
    points=np.array([[1,.4,.5],[2.1,.3,0],[4,-1,1]])
    first=survey(m,positions=points,condition=c,panels=8)['velocity']['volume'];second=survey(cm,positions=points*100,condition=cc,panels=8)['velocity']['volume']
    np.testing.assert_allclose(first,np.array(second)/100,atol=3e-12)


def test_shoulder_force_uses_local_elastic_velocity_at_its_actual_node():
    from openswing.network import StaticNetwork
    from openswing.local_motion import NetworkMotion
    from openswing.aero import evaluate_aerodynamics
    m=parse_asw(step_source(closed=True));c=FlightCondition(speed=17,alpha=11,mach=0,rates=[0,.02,0])
    n=StaticNetwork(m,4,c,[0,0,0],[]);r=n.rj.copy();Q=np.tile(np.eye(3),(n.nn,1,1));u=np.column_stack([.2*r[:,0],np.zeros(n.nn),.1*r[:,0]]);zero=np.zeros_like(r)
    local=NetworkMotion(n,r,Q,u,zero,zero,zero);meshes=n.deformed_meshes(r,Q,n.geometry(r,Q))
    out=evaluate_aerodynamics(m,c,meshes,local_motion=local)
    for s in out['body_shoulders']:
        i=n.node(s['beam'],s['t']);velocity=c.speed*c.vectors()[0]-np.cross(c.rates,s['position'])-u[i]
        normal=velocity.copy();normal[0]=0
        np.testing.assert_allclose(s['incident_velocity'],velocity,atol=2e-14)
        np.testing.assert_allclose(s['force'],m.constants[1]*normal*velocity[0]*s['area_jump'],atol=2e-14)
