from pathlib import Path
from dataclasses import replace
import numpy as np
import pytest
from scipy.integrate import quad_vec
from scipy.spatial.transform import Rotation
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid, horseshoe_velocity
from openswing.ground import GroundPlane, body_to_earth, GroundIntersectionError
from openswing.geometry import mesh_beam
from openswing.volume import VolumeField
from openswing.network import solve_static
from openswing.operating import OperatingConstraint
from test_network import balanced
from test_volume import body_source


def test_earth_rotation_matches_passive_euler_sequence_and_gravity():
    angles=[23,-17,41]
    expected=Rotation.from_euler('xyz',[-23,-17,-41],degrees=True).as_matrix()
    q=body_to_earth(angles)
    np.testing.assert_allclose(q,expected,atol=1e-15)
    c=FlightCondition(alpha=5,beta=3,attitude=(0,5,41))
    assert c.earth_state()['flight_path']==pytest.approx(0,abs=1e-12)
    assert replace(c,attitude=(0,8,41),beta=0).earth_state()['flight_path']==pytest.approx(3,abs=1e-12)
    # A single known point mass checks the gravity wrench independently.
    model=parse_asw(body_source(radius=0)+ '\nWeight\n1 0 .4 .7 -.2 98.0665\nEnd\n')
    result=solve_static(model,FlightCondition(alpha=0,mach=0,attitude=angles),panels=4)
    expected_g=q.T@np.array([0,0,-9.80665])
    np.testing.assert_allclose(result['gravity_body'],expected_g,atol=1e-12)
    np.testing.assert_allclose(result['support_force'],-10*expected_g,atol=1e-9)
    np.testing.assert_allclose(result['support_moment'],-np.cross([.4,.7,-.2],10*expected_g),atol=1e-9)
    balanced(result)
    override=solve_static(model,FlightCondition(alpha=0,mach=0,attitude=angles),panels=4,gravity=[0,0,-2])
    np.testing.assert_allclose(override['support_force'],[0,0,20],atol=1e-10)


def test_earth_plane_reflection_is_an_involution_and_preserves_tangential_location():
    ground=GroundPlane(1,[2,-1,3],[20,12,-30],[.3,-.1,1])
    points=np.array([[1.,2.,3.],[-2.,.5,1.]])
    image=ground.reflect_points(points)
    earth=points@ground.rotation.T+ground.position
    expected=earth-2*(earth@ground.normal_earth)[:,None]*ground.normal_earth
    np.testing.assert_allclose(image@ground.rotation.T+ground.position,expected,atol=1e-14)
    np.testing.assert_allclose(ground.reflect_points(image),points,atol=1e-14)
    np.testing.assert_allclose(ground.distance(image),-ground.distance(points),atol=1e-14)


@pytest.mark.parametrize('flag',[1,-1])
@pytest.mark.parametrize('mach',[0.,.65])
def test_vortex_and_volume_images_satisfy_plane_boundary(flag,mach):
    ground=GroundPlane(flag,[0,0,2],[17,8,23],[0,0,1])
    n=ground.normal;offset=ground.offset
    e=np.cross(n,[0,1,0]);e/=np.linalg.norm(e)
    side=np.cross(n,e)
    points=-offset*n+np.array([[-1,.2],[.5,-.9],[2,1.]])@np.array([e,side])
    pg=np.eye(3)+(1/np.sqrt(1-mach**2)-1)*np.outer(e,e)
    a=np.array([-.2,-1.,.3]);b=np.array([.5,1.2,.6])
    vortex=horseshoe_velocity(points,a,b,e,pg,.17,ground)
    model=parse_asw(body_source(radius=.2,attachments='Weight\n1 0 -.3 .7 .1 0 .1 .4\nEnd\n'))
    volume=VolumeField(model,[mesh_beam(model.beams[0],8)],e,pg,ground=ground).velocity(points)
    for velocity in (vortex,volume):
        constrained=velocity@n if flag==1 else velocity-(velocity@n)[:,None]*n
        np.testing.assert_allclose(constrained,0,atol=3e-16)


def test_image_vortex_matches_independent_line_integrals():
    # Explicit physical mirror in the z=-1 plane; integrate each straight leg.
    a=np.array([-.1,-.7,.4]);b=np.array([.3,.8,.6]);p=np.array([.5,.2,.3]);e=np.array([.9,.1,.2]);e/=np.linalg.norm(e)
    ground=GroundPlane(1,[0,0,1]);core=.13
    def integral(a,b,direction):
        d=b-a
        bound=quad_vec(lambda t:np.cross(d,p-a-t*d)/(np.linalg.norm(p-a-t*d)**2+core**2)**1.5,0,1,epsabs=1e-12)[0]
        def leg(origin):
            return quad_vec(lambda t:np.cross(direction,p-origin-t*direction)/(np.linalg.norm(p-origin-t*direction)**2+core**2)**1.5,0,np.inf,epsabs=1e-12)[0]
        return (bound+leg(b)-leg(a))/(4*np.pi)
    ai=a*[1,1,-1]-[0,0,2];bi=b*[1,1,-1]-[0,0,2]
    expected=integral(a,b,e)-integral(ai,bi,e*[1,1,-1])
    np.testing.assert_allclose(horseshoe_velocity(p,a,b,e,np.eye(3),core,ground),expected,atol=2e-13)


def test_elliptic_circulation_center_downwash_matches_exact_height_factor():
    # Integrating an elliptic trailing sheet gives w(0)=-Gamma0/(4a)*
    # k/sqrt(1+k²), k=2h/a. This is independent of the discrete horseshoes.
    a=5.
    for h in (.2,1.,4.,30.):
        values=[]
        for count in (256,512):
            nodes=-a*np.cos(np.linspace(0,np.pi,count+1))
            midpoint=(nodes[1:]+nodes[:-1])/2
            gamma=np.sqrt(1-(midpoint/a)**2)
            va=np.c_[np.zeros(count),nodes[:-1],np.zeros(count)]
            vb=np.c_[np.zeros(count),nodes[1:],np.zeros(count)]
            field=horseshoe_velocity(np.zeros(3),va,vb,[1,0,0],np.eye(3),ground=GroundPlane(1,[0,0,h]))
            values.append(gamma@field[:,2])
        k=2*h/a;expected=-k/np.sqrt(1+k*k)/(4*a)
        assert abs(values[1]-expected)<.51*abs(values[0]-expected)
        # Constant-circulation panels converge linearly for the singular sheet;
        # eliminate that leading error with a two-grid Richardson estimate.
        assert 2*values[1]-values[0]==pytest.approx(expected,rel=3e-5)


def test_own_volume_image_is_retained_when_real_self_field_is_excluded():
    m=parse_asw(body_source(radius=0,attachments='Weight\n1 0 0 0 0 0 .1 .4\nEnd\n'))
    meshes=[mesh_beam(m.beams[0],4)]
    plain=VolumeField(m,meshes,np.array([1.,0,0]),np.eye(3))
    image=VolumeField(m,meshes,np.array([1.,0,0]),np.eye(3),ground=GroundPlane(1,[0,0,1]))
    np.testing.assert_array_equal(plain.velocity([0,0,0],exclude_point=0),0.)
    actual=image.velocity([0,0,0],exclude_point=0)
    assert np.linalg.norm(actual)>1e-3
    np.testing.assert_allclose(actual,plain.velocity([0,0,-2])*[1,1,-1],atol=1e-14)


def test_ground_height_sensitivity_far_limit_and_rigid_coupled_agreement():
    model=parse_asw(Path('examples/rectangular.asw').read_text())
    # This test compares Trefftz drag with wind parallel to the image plane.
    # The frozen default uses body-x wakes, which are oblique to this plane.
    c=FlightCondition(alpha=5,mach=0,attitude=(0,5,0),position_earth=(0,0,1),
                      freeze_influences=False)
    free=solve_rigid(model,c,panels=16)
    near=solve_rigid(model,replace(c,ground_effect=1),panels=16)
    anti=solve_rigid(model,replace(c,ground_effect=-1),panels=16)
    far=solve_rigid(model,replace(c,ground_effect=1,position_earth=(0,0,1e5)),panels=16)
    assert near['CL'] > free['CL'] > anti['CL']
    assert near['CDi']/near['CL']**2 < free['CDi']/free['CL']**2 < anti['CDi']/anti['CL']**2
    assert far['CL']==pytest.approx(free['CL'],rel=1e-9)
    coupled=solve_static(model,replace(c,ground_effect=1),panels=16)
    np.testing.assert_allclose(coupled['force'],near['force'],atol=1e-8)
    balanced(coupled)


def test_oblique_frozen_ground_wake_retains_loads_but_has_no_stationary_trefftz_plane():
    model=parse_asw(Path('examples/rectangular.asw').read_text())
    condition=FlightCondition(alpha=5,mach=0,ground_effect=1,
        attitude=(0,5,0),position_earth=(0,0,1),freeze_influences=True)
    frozen=solve_rigid(model,condition,panels=8)
    assert frozen['converged'] and np.all(np.isfinite(frozen['force']))
    assert frozen['CDi'] is None and not frozen['trefftz']['available']
    assert 'wind parallel' in frozen['trefftz']['reason']
    aligned=solve_rigid(model,replace(condition,freeze_influences=False),panels=8)
    assert aligned['trefftz']['available'] and aligned['CDi'] > 0


def test_ground_height_and_attitude_can_be_solved_from_operating_targets():
    model=parse_asw(Path('examples/rectangular.asw').read_text())
    c=FlightCondition(alpha=5,mach=0,attitude=(0,5,0),ground_effect=1,position_earth=(0,0,2))
    reference=solve_rigid(model,c,panels=8)
    result=solve_static(model,replace(c,position_earth=(0,0,3),attitude=(0,4,0)),panels=8,
        operating_constraints=[OperatingConstraint('position_earth.z','CL',reference['CL']),
                               OperatingConstraint('attitude.elevation','flight_path',0)])
    assert result['operating_values']['position_earth.z']==pytest.approx(2,abs=1e-7)
    assert result['operating_values']['attitude.elevation']==pytest.approx(5,abs=1e-8)
    balanced(result)


def test_earth_velocity_and_motion_component_targets_recover_body_inputs():
    model=parse_asw(body_source(radius=0))
    truth=FlightCondition(speed=35,alpha=4,mach=0,attitude=(23,-17,41),rates=(.1,.2,.3),
                          acceleration=(.4,.5,.6),angular_acceleration=(.03,.04,.05))
    q=Rotation.from_euler('xyz',[-23,-17,-41],degrees=True).as_matrix()
    targets=[OperatingConstraint('speed','velocity_earth.x',(-35*q@truth.vectors()[0])[0]),
             OperatingConstraint('rates.y','rates_earth.z',(q@truth.rates)[2]),
             OperatingConstraint('acceleration.x','acceleration_earth.x',(q@truth.acceleration)[0]),
             OperatingConstraint('angular_acceleration.y','angular_acceleration_earth.z',(q@truth.angular_acceleration)[2])]
    start=replace(truth,speed=30,rates=(.1,0,.3),acceleration=(0,.5,.6),angular_acceleration=(.03,0,.05))
    result=solve_static(model,start,panels=4,operating_constraints=targets)
    np.testing.assert_allclose([result['operating_values'][t.variable] for t in targets],[35,.2,.4,.04],atol=1e-9)
    balanced(result)


def test_ground_parameters_and_actual_geometry_clearance_are_checked():
    with pytest.raises(ValueError,match='nonzero'): GroundPlane(normal=[0,0,0])
    with pytest.raises(ValueError,match='flag'): GroundPlane(flag=2)
    with pytest.raises(ValueError,match='finite'): GroundPlane(position=[0,np.nan,1])
    model=parse_asw(Path('examples/wing-body.asw').read_text())
    with pytest.raises(GroundIntersectionError,match='touches or crosses'):
        solve_rigid(model,FlightCondition(ground_effect=1,position_earth=(0,0,.4)),panels=8)


def test_coupled_wing_body_ground_images_and_earth_targets_recover_the_same_state():
    model=parse_asw(Path('examples/wing-body.asw').read_text())
    c=FlightCondition(alpha=5,mach=0,ground_effect=1,position_earth=(0,0,2),attitude=(0,5,0))
    reference=solve_static(model,c,panels=8)
    balanced(reference)
    result=solve_static(model,replace(c,position_earth=(0,0,2.5),attitude=(0,4,0)),panels=8,
        operating_constraints=[OperatingConstraint('position_earth.z','CL',reference['CL']),
                               OperatingConstraint('attitude.elevation','flight_path',0)])
    assert result['earth_state']['position'][2]==pytest.approx(2,abs=1e-7)
    assert result['earth_state']['attitude'][1]==pytest.approx(5,abs=1e-8)
    assert result['ground_plane']['minimum_clearance']>1
    assert np.linalg.norm(result['body_force'])>1
    np.testing.assert_allclose(result['force'],reference['force'],atol=1e-6)
    np.testing.assert_allclose(result['body_force'],reference['body_force'],atol=1e-6)
    balanced(result)
