from pathlib import Path
import numpy as np
import pytest
from scipy.integrate import quad, quad_vec
from scipy.spatial.transform import Rotation
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid, evaluate_aerodynamics
from openswing.network import solve_static, StaticNetwork
from openswing.geometry import mesh_beam
from openswing.volume import VolumeField, source_doublet
from test_network import balanced


def body_source(radius=.2, length=4, rows=None, attachments="Ground\n1 0 0\nEnd\n"):
    return """Name
Volume verification
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
9.80665 1.225 340.294
End
Reference
4 1 4
End
"""+attachments+"Beam 1\nBody\nt x y z radius Cdf Cdp\n"+(rows or f"0 0 0 0 {radius} .01 1.2\n{length} {length} 0 0 {radius} .01 1.2\n")+"End\n"


def test_unregularized_singularities_are_the_gradient_of_their_potential():
    point=np.array([1.3,-.7,.9]);sigma=.4;nu=np.array([.3,.5,-.2])
    def potential(p): return (-sigma/np.linalg.norm(p)+nu@p/np.linalg.norm(p)**3)/(4*np.pi)
    h=1e-5
    gradient=np.array([(potential(point+h*d)-potential(point-h*d))/(2*h) for d in np.eye(3)])
    np.testing.assert_allclose(source_doublet(point,sigma,nu),gradient,rtol=1e-9)
    jac=np.column_stack([(source_doublet(point+h*d,sigma,nu)-source_doublet(point-h*d,sigma,nu))/(2*h) for d in np.eye(3)])
    np.testing.assert_allclose(jac,jac.T,atol=2e-11)
    assert abs(np.trace(jac)) < 2e-11


def test_point_drag_and_volume_influence_pg_chain_rule_and_zero_self_field():
    model=parse_asw(body_source(radius=0,attachments="Weight\n1 0 .1 -.2 .3 0 .2 .5\nEnd\n"))
    e=np.array([.8,0,.6]); pg=np.eye(3)+.4*np.outer(e,e)
    field=VolumeField(model,[mesh_beam(model.beams[0],4)],e,pg)
    field.cores[:]=0  # isolate the exact potential/PG transform from core smoothing
    point=np.array([1.2,.9,1.1]);origin=np.array([.1,-.2,.3]);nu=.5*pg@e
    def phi(p):
        r=pg@(p-origin);return (-.2/np.linalg.norm(r)+nu@r/np.linalg.norm(r)**3)/(4*np.pi)
    h=1e-5
    expected=np.array([(phi(point+h*d)-phi(point-h*d))/(2*h) for d in np.eye(3)])
    np.testing.assert_allclose(field.velocity(point),expected,rtol=2e-9)
    np.testing.assert_array_equal(field.velocity(origin,exclude_point=0),0.)


def test_body_volume_quadrature_matches_adaptive_integration_and_is_parameter_invariant():
    rows="0 -2 0 0 .1 0 0\n2 0 0 0 .35 0 0\n4 2 0 0 .1 0 0\n"
    model=parse_asw(body_source(rows=rows));beam=model.beams[0]
    direction=np.array([.96,0,.28]);pg=np.eye(3)
    mesh=mesh_beam(beam,20);field=VolumeField(model,[mesh],direction,pg)
    target=np.array([.2,.8,.5])
    def integrand(t):
        radius=float(beam.value("radius",t));rd=float(beam.value("radius",t,derivative=1))
        sigma=2*np.pi*radius*rd*direction[0]
        nu=2*np.pi*radius**2*(direction-[direction[0],0,0])
        return source_doublet(target-beam.position(t),sigma,nu,radius/2)
    expected=quad_vec(integrand,0,4,epsabs=1e-12)[0]
    np.testing.assert_allclose(field.velocity(target),expected,rtol=2e-9,atol=1e-12)
    np.testing.assert_array_equal(field.velocity(target,exclude_body=beam.physical_index),0.)
    other=parse_asw(body_source(rows=rows.replace('2 0 0 0 .35','20 0 0 0 .35').replace('4 2 0 0 .1','40 2 0 0 .1')))
    field2=VolumeField(other,[mesh_beam(other.beams[0],20)],direction,pg)
    np.testing.assert_allclose(field2.velocity(target),expected,rtol=2e-9,atol=1e-12)


@pytest.mark.parametrize("alpha", [-6., 0., 12.])
def test_constant_radius_field_matches_closed_form_regularized_doublet_integral(alpha):
    # Independent integral of steady eqs.162–163 for the SA8 body geometry.
    # Unlike the adaptive-quadrature test, this oracle does not call the
    # production singularity kernel. Near-core points distinguish its printed
    # numerator |delta|^2 from a numerator augmented by the core radius.
    radius=.0645;core=radius/2
    model=parse_asw(body_source(rows=(
        "-.1 -.1 0 -.0645 .0645 0 0\n"
        ".95 .95 0 -.0645 .0645 0 0\n"),attachments=""))
    angle=np.deg2rad(alpha);direction=np.array([np.cos(angle),0.,np.sin(angle)])
    field=VolumeField(model,[mesh_beam(model.beams[0],64)],direction,np.eye(3))
    targets=np.array([[.03225,0.,0.],[.92225,0.,-.101],[.4,.2,.1],[-.2,0.,-.0645]])
    expected=[]
    for x,y,z in targets:
        z+=radius;a2=y*y+z*z+core*core
        def primitive(t):
            d=t*t+a2;u=t/np.sqrt(d)
            # Integrals needed for delta_x/D^(5/2), 1/D^(3/2), 1/D^(5/2).
            return np.array([d**-1.5,u/a2,(u-u**3/3)/a2**2])
        d0,i3,i5=primitive(x+.1)-primitive(x-.95)
        factor=.5*radius**2*np.sin(angle)
        expected.append(factor*np.array([z*d0,-3*y*z*i5,i3-(3*z*z+core*core)*i5]))
    np.testing.assert_allclose(field.velocity(targets),expected,rtol=2e-12,atol=2e-14)
    np.testing.assert_array_equal(field.velocity(targets,exclude_body=model.beams[0].physical_index),0.)


def test_volume_field_is_objective_under_rigid_rotation_and_translation():
    model=parse_asw(body_source())
    e=np.array([.8,.6,0]);q=Rotation.from_rotvec([.3,-.4,.7]).as_matrix();shift=np.array([3.,-2.,1.])
    rows="".join(f"{t} "+" ".join(map(str,q@np.array([t,0,0])+shift))+" .2 .01 1.2\n" for t in (0,4))
    other=parse_asw(body_source(rows=rows))
    target=np.array([[1.,1.,2.],[3.,-.8,.5]])
    pg=np.eye(3)+.3*np.outer(e,e)
    a=VolumeField(model,[mesh_beam(model.beams[0],12)],e,pg)
    b=VolumeField(other,[mesh_beam(other.beams[0],12)],q@e,q@pg@q.T)
    np.testing.assert_allclose(b.velocity(target@q.T+shift),a.velocity(target)@q.T,atol=1e-12)


def test_closed_slender_body_has_zero_net_potential_force_and_munk_moment():
    x=np.linspace(-2,2,17);radius=.3*(1-(x/2)**2)
    rows="".join(f"{i} {xx} 0 0 {r} 0 0\n" for i,(xx,r) in enumerate(zip(x,radius)))
    model=parse_asw(body_source(rows=rows,attachments=""));beam=model.beams[0]
    condition=FlightCondition(speed=30,alpha=5,mach=0)
    result=solve_rigid(model,condition,panels=24)
    volume=quad(lambda t: np.pi*beam.value('radius',t)**2/4,0,16,epsabs=1e-10)[0]
    v=condition.speed*condition.vectors()[0]
    np.testing.assert_allclose(result['force'],0,atol=1e-8)
    assert result['moment'][1] == pytest.approx(model.constants[1]*volume*v[0]*v[2],rel=2e-7)
    assert result['lifting_panels'] == 0 and all(s['cl'] is None for s in result['strips'])


def test_uniform_body_profile_drag_uses_full_and_transverse_velocities():
    model=parse_asw(body_source());condition=FlightCondition(speed=20,alpha=13,mach=0)
    result=solve_rigid(model,condition,panels=4)
    v=condition.speed*condition.vectors()[0];vp=v-[v[0],0,0]
    expected=1.225*.2*4*(np.linalg.norm(v)*v*.01+np.linalg.norm(vp)*vp*1.2)
    np.testing.assert_allclose(result['force'],expected,atol=1e-10)
    np.testing.assert_allclose(result['moment'],np.cross([2,0,0],expected),atol=1e-10)


@pytest.mark.parametrize("factor",[1.,2.])
def test_body_apparent_force_and_spatial_tensor_match_cylinder_pressure_integral(factor):
    model=parse_asw(body_source());c=FlightCondition(alpha=0,mach=0,acceleration=(.4,.7,1.2),angular_acceleration=(.1,.2,-.3),body_added_mass_factor=factor)
    result=solve_rigid(model,c,panels=4)
    # Direct unsteady Bernoulli pressure integral on the cylinder surface,
    # then integrate along its axis. No reliance on the spatial-matrix formula.
    mass_per_length=quad(lambda theta: 1.225*.2**2*np.cos(theta)**2,0,2*np.pi,epsabs=1e-13)[0]*factor
    def wrench(x):
        a=np.asarray(c.acceleration)+np.cross(c.angular_acceleration,[x,0,0])
        f=-mass_per_length*(a-[a[0],0,0])
        return np.r_[f,np.cross([x,0,0],f)]
    expected=quad_vec(wrench,0,4,epsabs=1e-12)[0]
    actual=np.r_[result['apparent_force'],result['apparent_moment']]
    np.testing.assert_allclose(actual,expected,atol=1e-12)
    matrix=np.array(result['apparent_mass']['spatial_matrix'])
    np.testing.assert_allclose(actual,-matrix@np.r_[c.acceleration,c.angular_acceleration],atol=1e-12)
    np.testing.assert_allclose(matrix,matrix.T,atol=1e-12)
    assert np.min(np.linalg.eigvalsh(matrix)) > -1e-12


def test_point_volume_changes_wing_circulation_and_recovers_the_coupled_rigid_limit():
    source=Path('examples/rectangular.asw').read_text()
    volume=parse_asw(source+'\nWeight\n1 0 -.6 0 -.5 0 0 .5\nEnd\n')
    c=FlightCondition(alpha=0,mach=0)
    baseline=solve_rigid(parse_asw(source),c,panels=16)
    result=solve_rigid(volume,c,panels=16)
    assert abs(result['CL']-baseline['CL'])>.001
    mirrored=parse_asw(source+'\nWeight\n1 0 -.6 0 .5 0 0 .5\nEnd\n')
    assert solve_rigid(mirrored,c,panels=16)['CL'] == pytest.approx(-result['CL'],rel=1e-9)
    coupled=solve_static(volume,c,panels=8,gravity=[0,0,0])
    rigid=solve_rigid(volume,c,panels=8)
    np.testing.assert_allclose(coupled['force'],rigid['force'],atol=1e-8)
    balanced(coupled)


def test_mixed_body_equilibrium_and_volume_follow_the_deformed_pylon():
    source=Path('examples/wing-body.asw').read_text().replace('2 0 -.5 0 -.75','2 1 -.5 0 -.75')
    model=parse_asw(source)
    # This check requires the volume field to follow the moving pod/body.
    # The ASWING frozen default intentionally retains the jig influence field.
    c=FlightCondition(alpha=5,mach=0,acceleration=(0,0,1),body_added_mass_factor=2,freeze_influences=False)
    result=solve_static(model,c,panels=8)
    balanced(result)
    assert result['max_displacement'] > .3
    assert np.linalg.norm(result['body_force']) > 1
    assert result['panels'] > result['lifting_panels'] > 0
    network=StaticNetwork(model,8,c,None,[])
    r=np.array([n['position'] for n in result['nodes']])
    Q=np.array([n['rotation'] for n in result['nodes']])
    meshes=network.deformed_meshes(r,Q,network.geometry(r,Q))
    row=model.records['weight'][0]
    node=next(n for n in result['nodes'] if n['beam']==2 and n['t']==1)
    expected=np.array(node['position'])+np.array(node['rotation'])@(row[2:5]-node['jig_position'])
    positions=network.point_positions(r,Q)
    np.testing.assert_allclose(positions[0],expected,atol=1e-12)
    assert np.linalg.norm(expected-row[2:5]) > 1e-4
    pylon=next(o for o in result['attachments'] if o['kind']=='weight')
    np.testing.assert_allclose(pylon['segments'][0][1],expected,atol=1e-12)
    gamma=np.array([s['circulation'] for s in result['strips'] if s['lifting']])
    actual=evaluate_aerodynamics(model,c,meshes,gamma,positions)
    np.testing.assert_allclose(actual['force'],result['force'],atol=1e-8)
    frozen=evaluate_aerodynamics(model,c,meshes,gamma,[row[2:5]])
    assert np.linalg.norm(np.array(frozen['circulation_residual'])-actual['circulation_residual']) > 1e-7
    body=next(g for g in result['geometry'] if not g['lifting'])
    # Ring centroids lie on the actual deformed axis; all vertices have the
    # prescribed radius in the node's rotated cross section.
    quads=np.array(body['quads']).reshape(-1,12,4,3)
    rings=quads[:,:,0]
    centers=np.array(body['axis'])[:,0]
    np.testing.assert_allclose(rings.mean(axis=1),centers,atol=1e-12)
    np.testing.assert_allclose(np.linalg.norm(rings-centers[:,None,:],axis=-1),
                               np.broadcast_to(meshes[1].beam.value('radius',meshes[1].t0)[:,None],rings.shape[:2]),atol=1e-12)


def test_body_only_network_balances_and_has_no_circulation_unknowns():
    model=parse_asw(body_source())
    c=FlightCondition(alpha=5,mach=0,acceleration=(0,0,1))
    rigid=solve_rigid(model,c,panels=4)
    mounted=solve_static(model,c,panels=4)
    assert mounted['lifting_panels']==0
    np.testing.assert_allclose(mounted['force'],rigid['force'],atol=1e-10)
    balanced(mounted)


def test_invalid_body_radius_and_discontinuities_are_explicit():
    with pytest.raises(ValueError,match='nonnegative'):
        solve_rigid(parse_asw(body_source(radius=-.2)),FlightCondition(),panels=4)
    rows='0 0 0 0 .2 0 0\n2 2 0 0 .2 0 0\n2 2 0 0 .3 0 0\n4 4 0 0 .3 0 0\n'
    result=solve_rigid(parse_asw(body_source(rows=rows)),FlightCondition(),panels=4)
    assert len(result['body_shoulders'])==1
