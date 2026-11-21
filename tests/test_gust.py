from dataclasses import replace
import json
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid, evaluate_aerodynamics
from openswing.gust import gust_field
from openswing.ground import body_to_earth
from openswing.geometry import mesh_beam
from openswing.propulsion import engine_load
from openswing.time_integration import solve_time
from openswing.network import solve_static
from openswing.bridge import run_json
from test_volume import body_source
from test_propulsion import engine
from test_network import model as network_model, beam as network_beam
from test_time_integration import rigid_body


def test_cosine_is_compact_slanted_and_translates_at_prescribed_speed():
    n = np.array([-2., 1., 2.])/3
    origin = np.array([2., -4., 1.])
    f = gust_field(dict(type='cosine', amplitude=[1, 2, -3], origin=origin.tolist(),
                        normal=(-3*n).tolist(), length=2, speed=.7))
    # The supplied normal has the opposite sign and nonunit magnitude.
    for t in (0., .3):
        s = np.array([-1., 0., 1., 2., 3., 4., 5.])
        points = origin-(s+.7*t)[:, None]*n
        expected = np.array([0, 0, .5, 1, .5, 0, 0])[:, None]*[1, 2, -3]
        np.testing.assert_allclose(f.velocity(points, t), expected, atol=2e-15)


def test_expressions_fourier_superposition_and_body_earth_transform():
    c = FlightCondition(attitude=(31, -22, 17), position_earth=(3, -2, 4), time=.3)
    p = np.array([[.2, -.6, .9], [1, 2, -1]])
    R = body_to_earth(c.attitude)
    earth = p@R.T+c.position_earth
    f = gust_field(dict(type='expression', components=['x+2*y-t', 'sin(pi*z)', 'exp(-x*x)+cos(t)']))
    expected = np.column_stack([earth[:, 0]+2*earth[:, 1]-.3, np.sin(np.pi*earth[:, 2]),
                                np.exp(-earth[:, 0]**2)+np.cos(.3)])
    np.testing.assert_allclose(f.body_velocity(p, c), expected@R, atol=1e-14)
    spec = dict(type='sum', fields=[dict(type='uniform', velocity=[1, 2, 3]),
        dict(type='sinusoid', amplitude=[2, -1, 4], wavevector=[.3, -.2, .7], omega=.6, phase=.4)])
    expected = np.array([1, 2, 3])+np.sin(earth@[.3, -.2, .7]-.6*.3+.4)[:, None]*[2, -1, 4]
    np.testing.assert_allclose(gust_field(spec).velocity(earth, .3), expected)
    # Caller edits must neither change a cached field nor its saved specification.
    spec['fields'][0]['velocity'][0] = 100
    assert gust_field(spec).velocity(earth, .3)[0, 0] == pytest.approx(expected[0, 0]+99)


@pytest.mark.parametrize('spec', [
    {'type': 'cosine', 'amplitude': [0, 0, 1], 'length': 0},
    {'type': 'cosine', 'amplitude': [0, 0, 1], 'length': 1, 'normal': [0, 0, 0]},
    {'type': 'uniform', 'velocity': [1, 2]}, {'type': 'uniform', 'velocity': [1, 2, float('nan')]},
    {'type': 'uniform', 'velocity': [1, 2, 3], 'typo': 1}, {'type': 'aswing_type_5'},
    {'type': 'sum', 'fields': []}, {'type': 'expression', 'components': ['x', 'y']},
    *[{'type': 'expression', 'components': ['0', '0', s]} for s in
      ['__import__("os").getcwd()', 'x.__class__', '[x for x in (1,2)]', 'sin(x, y)', '1e999', 'lambda: 0']],
])
def test_invalid_unknown_and_executable_inputs_are_rejected(spec):
    with pytest.raises(ValueError):
        gust_field(spec)


def test_nonfinite_expression_evaluation_is_rejected_and_preview_uses_same_field():
    f = gust_field(dict(type='expression', components=['0', '0', 'sqrt(x)']))
    with pytest.raises(ValueError, match='nonfinite'):
        f.velocity([[-1, 0, 0]])
    request = dict(action='gust_sample', gust=dict(type='expression', components=['0', '0', 'where(x<0, 2*t, 0)']),
                   positions=[[-1, 0, 0], [1, 0, 0]], time=.7)
    assert json.loads(run_json(json.dumps(request)))['velocity'] == [[0, 0, 1.4], [0, 0, 0]]


def test_uniform_axial_gust_scales_profile_force_but_keeps_reference_dynamic_pressure():
    m = parse_asw(Path('examples/rectangular.asw').read_text())
    c = FlightCondition(speed=10, alpha=0, mach=0)
    zero = solve_rigid(m, c, 8)
    gust = solve_rigid(m, replace(c, gust=dict(type='uniform', velocity=[5, 0, 0])), 8)
    np.testing.assert_allclose(gust['force'], 2.25*np.array(zero['force']), atol=1e-12)
    assert gust['CDp'] == pytest.approx(2.25*zero['CDp'])
    assert gust['atmosphere']['dynamic_pressure'] == zero['atmosphere']['dynamic_pressure']
    assert gust['earth_state'] == zero['earth_state']
    np.testing.assert_array_equal(gust['apparent_force'], 0)


def test_body_drag_integrates_spatial_gust_and_point_drag_samples_current_pylon_location():
    from scipy.integrate import quad_vec
    c = FlightCondition(speed=10, alpha=0, mach=0,
                        gust=dict(type='expression', components=['0', '0', '.2*x']))
    m = parse_asw(body_source())
    result = solve_rigid(m, c, 4)
    def load(x):
        v = np.array([10., 0, .2*x]); normal = np.array([0., 0, .2*x])
        return 1.225*.2*(np.linalg.norm(v)*v*.01+np.linalg.norm(normal)*normal*1.2)
    expected = quad_vec(load, 0, 4, epsabs=1e-12)[0]
    np.testing.assert_allclose(result['force'], expected, atol=1e-11)
    m = parse_asw(body_source(radius=0, attachments='Weight\n1 0 0 0 0 0 .3 0\nEnd\n'))
    meshes = [mesh_beam(m.beams[0], 4)]
    r = np.array([2., 0, 1.])
    actual = evaluate_aerodynamics(m, c, meshes, point_positions=[r])
    v = np.array([10, 0, .4])
    np.testing.assert_allclose(actual['point_forces'][0], .5*1.225*.3*np.linalg.norm(v)*v, atol=1e-12)
    np.testing.assert_allclose(actual['moment'], np.cross(r, actual['force']), atol=1e-12)


def test_gust_is_evaluated_at_distinct_control_force_and_axis_locations():
    m = parse_asw(Path('examples/rectangular.asw').read_text())
    # Xax=.25: vortex/beam axis at x=0; control point at c/2=.5.
    # w=0 at the control points gives zero circulation even though w=1 at
    # the force points. This detects accidental use of a single strip sample.
    c = FlightCondition(speed=10, alpha=0, mach=0, stall=False,
                        gust=dict(type='expression', components=['0', '0', '1-2*x']))
    result = solve_rigid(m, c, 4)
    assert max(abs(s['circulation']) for s in result['strips']) < 1e-12
    # Only profile drag remains, directed along the local force-point velocity.
    expected = .5*1.225*12*.008*np.sqrt(101)*np.array([10, 0, 1])
    np.testing.assert_allclose(result['force'], expected, atol=1e-12)


def test_engine_disk_samples_gust_at_the_current_mount():
    m = parse_asw(body_source(radius=0))
    row = engine(typ=1, radius=-.8)
    m.records['engine'] = [row]
    position = np.array([-3., .2, .5])
    c = FlightCondition(speed=20, alpha=0, mach=0, powers={1: 1200},
                        gust=dict(type='expression', components=['x', '0', '0']))
    result = evaluate_aerodynamics(m, c, [mesh_beam(m.beams[0], 4)], engine_positions=[position])
    expected = engine_load(row, 1200, 1.225, position, np.array([17., 0, 0]))
    np.testing.assert_allclose(result['engine_force'], expected['force'], atol=1e-12)


def test_elastic_extension_feeds_back_into_spatial_gust_and_matches_exact_equilibrium():
    # Massless axial rod L=2, EA=1000; drag area 2 at its end. Gust cancels
    # the reference x flow and imposes vy=5y, so y=2+(.5*rho*2*25)*(2/1000)*y².
    m = network_model(network_beam(stiffness='0 0 0 1000 0 0'),
                      'Ground\n1 0 0\nEnd\nWeight\n1 2 0 2 0 0 2 0\nEnd\n')
    c = FlightCondition(speed=10, alpha=0, mach=0,
                        gust=dict(type='expression', components=['-10', '5*y', '0']))
    result = solve_static(m, c, 4, gravity=[0, 0, 0], tolerance=1e-10)
    k = .5*1.225*2*25*2/1000
    y = (1-np.sqrt(1-8*k))/(2*k)
    assert result['nodes'][-1]['position'][1] == pytest.approx(y, abs=2e-9)
    np.testing.assert_allclose(result['point_forces'][0], [0, 500*(y-2), 0], atol=1e-7)
    np.testing.assert_allclose(result['force_balance'], 0, atol=1e-8)
    assert any('Sears' in text for text in result['limitations'])


def test_rotated_translated_aircraft_loads_use_earth_gust_at_the_offset_point():
    m = parse_asw(body_source(radius=0, attachments='Weight\n1 0 .3 -.1 .8 0 .4 0\nEnd\n'))
    c = FlightCondition(speed=12, alpha=0, mach=0, attitude=(20, 35, -18), position_earth=(3, -2, 1),
                        gust=dict(type='expression', components=['.1*z', '.2*x', '.3*y']))
    result = solve_rigid(m, c, 4)
    R = body_to_earth(c.attitude)
    p = R@np.array([.3, -.1, .8])+c.position_earth
    v = np.array([12., 0, 0])+R.T@np.array([.1*p[2], .2*p[0], .3*p[1]])
    expected = .5*1.225*.4*np.linalg.norm(v)*v
    np.testing.assert_allclose(result['force'], expected, atol=1e-12)
    np.testing.assert_allclose(result['moment'], np.cross([.3, -.1, .8], expected), atol=1e-12)


def test_moving_aircraft_cannot_skip_a_narrow_frozen_cosine_gust():
    m = parse_asw(body_source(radius=0, attachments='Ground\n1 0 0\nEnd\nWeight\n1 0 0 0 0 0 .2 0\nEnd\n'))
    c = FlightCondition(speed=10, alpha=0, mach=0,
        gust=dict(type='cosine', amplitude=[0, 0, 2], origin=[-.4, 0, 0], length=.1))
    # A single requested step spans the entire pulse [t=.04, .06].
    result = solve_time(m, c, 4, duration=.08, dt=.08, gravity=[0, 0, 0])
    assert result['gust_resolution_retries'] > 0
    assert max(s['point_forces'][0][2] for s in result['snapshots']) > 2.4
    for s in result['snapshots']:
        x = -10*s['time']
        w = 1-np.cos(np.pi*np.clip((-x-.4)/.1, 0, 2))
        expected = .5*1.225*.2*np.hypot(10, w)*np.array([10, 0, w])
        np.testing.assert_allclose(s['point_forces'][0], expected, atol=1e-10)
        np.testing.assert_allclose(s['apparent_force'], 0, atol=1e-12)
        assert s['gust']['time'] == s['time']
    assert max(s['step'] for s in result['snapshots']) <= .1/10/8*(1+1e-9)


def test_temporal_gust_lift_converges_to_analytic_empirical_lag():
    source = Path('examples/rectangular.asw').read_text()
    source = source[:source.index('t dCLdF1')]+'End\n'
    source = (source.replace('6 0 6 0', '100000 0 100000 0').replace('6 .008', '100000 .008')
              .replace('.008', '0').replace('12 1 12', '200000 1 200000'))
    model = parse_asw(source)
    errors = []
    for dt in (.02, .01, .005):
        out = solve_time(model, FlightCondition(speed=10, alpha=0, mach=0, stall=False,
                         gust=dict(type='expression', components=['0', '0', '.002*t'])),
                         4, duration=.2, dt=dt, tolerance=1e-10, gravity=[0, 0, 0])
        t = np.array([s['time'] for s in out['snapshots']])
        # Infinite-AR limit: tau=2c/V=.2, CLcmd=2*pi*w/V;
        # total lift includes the circulation-rate contribution tau/2 * CLdot.
        exact = 2*np.pi*.002/10*(t-.1*(1-np.exp(-t/.2)))
        errors.append(np.max(abs(np.array([s['CL'] for s in out['snapshots']])-exact)))
    assert errors[1] < .3*errors[0]
    assert errors[2] < .3*errors[1]
    assert errors[-1] < 6e-8


def test_uniform_axial_gust_free_flight_converges_to_exact_drag_trajectory():
    m = rigid_body()
    m.records['weight'][0][6] = .2
    c = FlightCondition(speed=10, alpha=0, mach=0, gust=dict(type='uniform', velocity=[5, 0, 0]))
    # One kg, F=K(5-U)^2; U(0)=-10. This includes the feedback of changed
    # body velocity into relative wind while the Earth gust remains fixed.
    k = .5*1.225*.2
    errors = []
    for dt in (.02, .01):
        out = solve_time(m, c, 4, duration=.16, dt=dt, frame='free', gravity=[0, 0, 0], tolerance=1e-11)
        t = np.array([s['time'] for s in out['snapshots']])
        expected = 5-15/(1+15*k*t)
        actual = np.array([s['frame']['velocity_origin_body'][0] for s in out['snapshots']])
        errors.append(np.max(abs(actual-expected)))
        for s in out['snapshots']:
            u = s['frame']['velocity_origin_body'][0]
            assert s['frame']['acceleration_reference_body'][0] == pytest.approx(k*(5-u)**2, abs=1e-8)
            np.testing.assert_allclose(s['support_force'], 0, atol=1e-8)
    assert errors[1] < .3*errors[0]
