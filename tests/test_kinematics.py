from dataclasses import replace
from pathlib import Path
import json
import numpy as np
import pytest
from scipy.spatial.transform import Rotation
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.ground import body_to_earth
from openswing.inertia import Motion
from openswing.kinematics import flight_kinematics
from openswing.network import solve_static
from openswing.operating import OperatingConstraint, steady_turn_constraints
from openswing.bridge import dispatch, run_json
from test_volume import body_source
from test_network import balanced


def reference_model():
    m = parse_asw(body_source(radius=0))
    m.reference[2] = [.4, -.7, .2]
    m.reference[3] = [-.8, .3, -.5]
    return m


def test_reference_velocities_and_accelerations_match_differentiated_rigid_motion():
    m = reference_model()
    c = FlightCondition(speed=37, alpha=11, beta=-7, attitude=(23, -12, 64),
                        rates=(.3, -.2, .15), acceleration=(2, -3, 4), angular_acceleration=(-.2, .1, .4))
    k = flight_kinematics(c, m)
    q = body_to_earth(c.attitude)
    w, aa = np.array(c.rates), np.array(c.angular_acceleration)
    # A prescribed origin translation and a locally quadratic rotation provide
    # independent first/second derivatives of both offset material points.
    u0 = -c.speed*c.vectors()[0]-np.cross(w, m.reference[3])
    a0 = np.array(c.acceleration)-np.cross(aa, m.reference[2])-np.cross(w, np.cross(w, m.reference[2]))
    def point(t, r):
        return q@(u0*t+a0*t*t/2+Rotation.from_rotvec(w*t+aa*t*t/2).apply(r))
    h = 1e-4
    for r, v, a in [(m.reference[3], k['velocity_earth'], k['acceleration_velocity_reference_earth']),
                    (m.reference[2], q@(u0+np.cross(w,m.reference[2])), k['acceleration_earth'])]:
        np.testing.assert_allclose((point(h,r)-point(-h,r))/(2*h), v, atol=2e-8)
        np.testing.assert_allclose((point(h,r)-2*point(0,r)+point(-h,r))/h**2, a, atol=1e-7)
    np.testing.assert_allclose(k['velocity_origin_body'],u0,atol=1e-14)
    np.testing.assert_allclose(k['acceleration_origin_body'],a0,atol=1e-14)
    assert np.linalg.norm(np.array(k['acceleration_earth'])-k['acceleration_velocity_reference_earth']) > .1


def test_euler_rates_reproduce_independent_rotation_derivative_and_report_pole():
    angles = np.array([29., -32., 117.]); angle_rates = np.array([.17, -.09, .21])
    q = body_to_earth(angles); h = 1e-4
    derivative = (body_to_earth(angles+np.rad2deg(h*angle_rates))-body_to_earth(angles-np.rad2deg(h*angle_rates)))/(2*h)
    spin = q.T@derivative
    w = np.array([spin[2,1],spin[0,2],spin[1,0]])
    c = FlightCondition(attitude=angles,rates=w)
    np.testing.assert_allclose(c.earth_state()['attitude_rates'],angle_rates,atol=4e-11)
    pole = replace(c,attitude=[29,90,117]).earth_state()
    assert pole['attitude_rates'] is None
    assert np.all(np.isfinite(pole['rates_earth']))


@pytest.mark.parametrize('heading,rate,climb',[(0, .08, 0),(113, -.1, 0),(-71, .07, 9),(38, 0, -5)])
def test_steady_turn_kinematics_matches_an_independent_circular_or_helical_path(heading,rate,climb):
    model = reference_model()
    condition = FlightCondition(speed=40,alpha=7,beta=3,mach=0,attitude=(24,7+climb,heading))
    result = solve_static(model,condition,panels=4,operating_constraints=steady_turn_constraints(rate,climb))
    k = result['earth_state']; q = np.array(k['body_to_earth']); v = np.array(k['velocity_earth'])
    # Integrate a horizontal rotation of the initial velocity analytically.
    def position(t):
        if rate == 0: return v*t
        return np.array([(v[0]*np.sin(rate*t)+v[1]*(1-np.cos(rate*t)))/rate,
                         (v[1]*np.sin(rate*t)-v[0]*(1-np.cos(rate*t)))/rate,v[2]*t])
    h = 1e-3
    acceleration = (position(h)-2*position(0)+position(-h))/h**2
    np.testing.assert_allclose(k['acceleration_velocity_reference_earth'],acceleration,atol=1e-7)
    np.testing.assert_allclose(k['velocity_derivative_body'],0,atol=1e-10)
    np.testing.assert_allclose(k['rates_earth'],[0,0,-rate],atol=1e-12)
    np.testing.assert_allclose(k['attitude_rates'],[0,0,rate],atol=1e-12)
    assert k['flight_path'] == pytest.approx(climb,abs=1e-9)
    assert k['radial_acceleration'] == pytest.approx(0,abs=1e-10)
    assert k['speed_rate'] == pytest.approx(0,abs=1e-10)
    balanced(result)


def test_radial_acceleration_uses_velocity_reference_and_direct_body_target():
    model = reference_model()
    truth = FlightCondition(speed=27,alpha=8,beta=4,mach=0,attitude=(17,-9,38),rates=(.1,-.2,.3),
                            acceleration=(1,2,3),angular_acceleration=(.4,-.3,.2))
    q = body_to_earth(truth.attitude)
    velocity = -27*q@truth.vectors()[0]
    av = q@truth.motion().at(model.reference[3],model.reference[2])
    expected = av[1]-velocity[0]*(q@truth.rates)[2]
    constraints = [OperatingConstraint('acceleration.y','radial_acceleration',expected),
                   OperatingConstraint('angular_acceleration.z','angular_acceleration.z',.2)]
    result=solve_static(model,replace(truth,acceleration=(1,0,3),angular_acceleration=(.4,-.3,0)),panels=4,operating_constraints=constraints)
    assert result['operating_values']['acceleration.y'] == pytest.approx(2,abs=1e-10)
    assert result['operating_values']['angular_acceleration.z'] == pytest.approx(.2,abs=1e-12)


def test_direct_motion_target_also_works_without_aerodynamics():
    model = reference_model()
    result = solve_static(model,panels=4,motion=Motion(),operating_constraints=[OperatingConstraint('rates.x','rates.x',.7)])
    assert result['operating_values']['rates.x'] == pytest.approx(.7,abs=1e-12)


@pytest.mark.parametrize('rate,climb',[(0,0),(3,0),(-3,0),(2,5)])
def test_all_six_flight_loads_trim_with_elastic_geometry_and_distinct_reference_points(rate,climb):
    m = parse_asw(Path('examples/trim-aircraft.asw').read_text())
    r = solve_static(m,FlightCondition(alpha=4,mach=0,powers={1:120},attitude=(0,4,57)),panels=4,
                     operating_constraints=steady_turn_constraints(np.deg2rad(rate),climb,trim_controls=[2,1,3],engine_control=1))
    k, mass = r['earth_state'], r['mass_properties']
    assert len(r['operating_constraints']) == 16
    np.testing.assert_allclose(r['applied_force'],0,atol=2e-7)
    np.testing.assert_allclose(r['applied_moment'],0,atol=2e-7)
    np.testing.assert_allclose(k['attitude_rates'],[0,0,np.deg2rad(rate)],atol=1e-10)
    np.testing.assert_allclose(k['velocity_derivative_body'],0,atol=1e-9)
    assert k['flight_path'] == pytest.approx(climb,abs=1e-8)
    assert r['max_displacement'] > .1
    assert 2 < r['operating_values']['alpha'] < 7
    assert r['operating_values']['power.1'] > 80
    if rate: assert np.sign(r['operating_values']['attitude.bank']) == np.sign(rate)
    # Independently verify the assembled global Newton-Euler equations about
    # the deformed CG, including the steady gyroscopic moment of the real mass.
    w = np.array([r['operating_values'][f'rates.{a}'] for a in 'xyz'])
    cg_acc = np.array(k['acceleration_velocity_reference_body'])+np.cross(w,np.cross(w,np.array(mass['cg'])-m.reference[3]))
    np.testing.assert_allclose(r['force'],mass['mass']*(cg_acc-r['gravity_body']),atol=2e-7)
    aero_couple = np.array(r['moment'])-np.cross(np.array(mass['cg'])-m.reference[1],r['force'])
    np.testing.assert_allclose(aero_couple,np.cross(w,np.array(mass['inertia_cg'])@w+mass['spin_angular_momentum']),atol=2e-7)
    balanced(r)


@pytest.mark.parametrize('kwargs',[
    dict(heading_rate=np.nan),dict(flight_path=90),dict(flight_path=-91),
    dict(trim_controls=[1,1,3],engine_control=1),dict(trim_controls=[1,2,3]),dict(engine_control=1),
    dict(trim_controls=[1.,2,3],engine_control=1),dict(trim_controls=[1,2,3],engine_control=0)])
def test_invalid_turn_presets_fail_before_solving(kwargs):
    with pytest.raises(ValueError): steady_turn_constraints(**kwargs)


def test_bridge_preset_validates_model_controls_and_serializes_all_targets():
    source = Path('examples/trim-aircraft.asw').read_text()
    request = dict(action='steady_turn_constraints',source=source,preset=dict(heading_rate=.1,trim_controls=[2,1,3],engine_control=1))
    result=json.loads(run_json(json.dumps(request)))
    assert len(result) == 16
    assert result[2] == dict(variable='rates.z',quantity='rates_earth.z',target=-.1,
                            weight=1.,preferred=0.,expression=None,residual_scale=None,unit=None)
    request['preset']['trim_controls']=[2,9,3]
    with pytest.raises(ValueError,match='flap'): dispatch(request)
    request['preset'].update(trim_controls=[2,1,3],engine_control=2)
    with pytest.raises(ValueError,match='engine'): dispatch(request)
