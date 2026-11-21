import json
from pathlib import Path
import numpy as np
import pytest
from openswing.ground import body_to_earth
from openswing.inertia import Motion
from openswing.local_motion import rotation_matrix as exp
from openswing.time_integration import bdf_coefficients, attitude_angles, rotation_rate, solve_time
from openswing.bridge import run_json
from openswing.aero import FlightCondition
from test_network import model, beam


def oscillator(damping=0.):
    b = beam(stiffness='0 0 0 1000 0 0').replace('End', f't tdeps\n0 {damping}\n2 {damping}\nEnd')
    return model(b, 'Ground\n1 0 0\nEnd\nWeight\n1 2 0 2 0 19.6133\nEnd\n')


def rigid_body():
    # One kilogram at the origin, principal inertias 2, 3, 4 kg m².
    return model(beam(stiffness='0 0 0 0 0 0'),
                 'Ground\n1 0 0\nEnd\nWeight\n1 0 0 0 0 9.80665 0 0 0 0 0 19.6133 29.41995 39.2266\nEnd\n')


@pytest.mark.parametrize('h,hp', [(.1,.1), (.02,.1), (.15,.1)])
def test_variable_step_bdf2_differentiates_quadratics(h, hp):
    t = np.array([.7, .7-h, .7-h-hp])
    k = bdf_coefficients(h, hp)
    np.testing.assert_allclose(k@np.stack([np.ones(3), t, t*t], axis=1), [0,1,1.4], atol=1e-14)


@pytest.mark.parametrize('angles', [(23,-54,172), (50,90,135), (-42,-90,-175), (12,134,255)])
def test_display_euler_angles_preserve_orientation_including_poles(angles):
    rotation = body_to_earth(angles)
    np.testing.assert_allclose(body_to_earth(attitude_angles(rotation)), rotation, atol=1e-14)


def test_lie_bdf2_has_second_order_rate_for_changing_axes_across_rotvec_branch():
    def rotation(t): return exp(np.array([2.9+t, 0, 0]))@exp(np.array([0, .4*t*t, 0]))
    t = 1.
    r = rotation(t)
    hfd = 1e-5
    rd = (rotation(t+hfd)-rotation(t-hfd))/(2*hfd)
    skew = rd@r.T
    exact = np.array([skew[2,1], skew[0,2], skew[1,0]])
    errors = []
    for h in (.04,.02,.01):
        rate = rotation_rate(r, rotation(t-h), rotation(t-2*h), bdf_coefficients(h,h))
        errors.append(np.linalg.norm(rate-exact))
    assert errors[1] < .26*errors[0]
    assert errors[2] < .26*errors[1]
    body = rotation_rate(r, rotation(t-.01), rotation(t-.02), bdf_coefficients(.01,.01), body=True)
    np.testing.assert_allclose(body, r.T@rate, atol=1e-13)


@pytest.mark.parametrize('order,damping', [(1,0.), (2,0.), (2,.02)])
def test_released_axial_point_mass_matches_exact_oscillator_with_temporal_order(order, damping):
    # Axial bar k=EA/L=500, tip m=2, initial extension F/k=.002.
    errors = []
    for dt in (.01,.005,.0025):
        out = solve_time(oscillator(damping), panels=4, duration=.2, dt=dt, order=order,
                         gravity=[0,0,0], initial_loads=[dict(beam=1,t=2,force=[0,1,0])])
        t = np.array([s['time'] for s in out['snapshots']])
        displacement = np.array([s['nodes'][-1]['position'][1]-2 for s in out['snapshots']])
        decay = 250*damping/2
        omega = np.sqrt(250-decay**2)
        exact = .002*np.exp(-decay*t)*(np.cos(omega*t)+decay/omega*np.sin(omega*t))
        errors.append(np.max(abs(displacement-exact)))
        assert out['rejected_steps'] == 0
        assert max(s['residual'] for s in out['snapshots']) <= 1e-8
        assert out['snapshots'][0]['initial_phase'] == 'before_load_switch'
        assert out['jacobian_builds'] <= 3
        assert len(json.dumps(out, allow_nan=False)) > 100
    ratio = .6 if order == 1 else .3
    assert errors[1] < ratio*errors[0]
    assert errors[2] < ratio*errors[1]


def test_rigid_free_fall_has_second_order_position_and_exact_velocity():
    errors = []
    for dt in (.05,.025,.0125):
        out = solve_time(rigid_body(), panels=4, frame='free', duration=.2, dt=dt,
                         position=[1,2,3], velocity=[.2,-.3,.4], attitude=[17,28,-41])
        initial = out['snapshots'][0]['frame']
        v0 = np.array(initial['body_to_earth'])@initial['velocity_origin_body']
        end = out['snapshots'][-1]
        frame = end['frame']
        expected = np.array([1,2,3])+.2*v0+np.array([0,0,-.5*9.80665*.2**2])
        errors.append(np.linalg.norm(np.array(frame['position_earth'])-expected))
        np.testing.assert_allclose(np.array(frame['body_to_earth'])@frame['velocity_origin_body'],
                                   v0+np.array([0,0,-9.80665*.2]), atol=2e-9)
        assert end['max_displacement'] < 1e-9
        np.testing.assert_allclose(end['support_force'],0,atol=1e-8)
        np.testing.assert_allclose(end['support_moment'],0,atol=1e-8)
    assert errors[1] < .27*errors[0]
    assert errors[2] < .27*errors[1]


def test_torque_free_asymmetric_rigid_body_conserves_momentum_and_energy_under_refinement():
    errors = []
    inertia = np.diag([2.,3.,4.])
    omega0 = np.array([.8,1.2,.6])
    energy0 = .5*omega0@inertia@omega0
    for dt in (.04,.02):
        out = solve_time(rigid_body(), panels=4, frame='free', duration=.4, dt=dt,
                         gravity=[0,0,0], motion=Motion(omega0))
        frames = [s['frame'] for s in out['snapshots']]
        momentum = np.array([np.array(f['body_to_earth'])@inertia@f['rates_body'] for f in frames])
        energy = np.array([.5*np.array(f['rates_body'])@inertia@f['rates_body'] for f in frames])
        errors.append(max(np.max(np.linalg.norm(momentum-inertia@omega0,axis=1))/np.linalg.norm(inertia@omega0),
                          np.max(abs(energy-energy0))/energy0))
    assert errors[1] < .3*errors[0]
    assert errors[1] < 3e-4


def test_prescribed_frame_constant_spin_crosses_global_rotation_branch():
    out = solve_time(rigid_body(), panels=4, duration=1., dt=.1, gravity=[0,0,0],
                     motion=Motion(rates=[0,0,4]))
    for s in out['snapshots']:
        np.testing.assert_allclose(s['frame']['body_to_earth'], exp(np.array([0,0,4*s['time']])), atol=1e-8)
        np.testing.assert_allclose(s['frame']['rates_body'], [0,0,4], atol=1e-9)
    assert out['rejected_steps'] == 0


def test_large_time_rotation_is_substepped_instead_of_aliasing_a_full_turn():
    out = solve_time(rigid_body(), panels=4, duration=1., dt=1., gravity=[0,0,0],
                     motion=Motion(rates=[0,0,2*np.pi]))
    assert out['rejected_steps'] > 0
    np.testing.assert_allclose(out['snapshots'][-1]['frame']['body_to_earth'], np.eye(3), atol=1e-8)


def test_browser_json_boundary_holds_loaded_aeroelastic_equilibrium():
    out = json.loads(run_json(json.dumps(dict(action='time', source=Path('examples/stress-wing.asw').read_text(),
                    panels=4, condition=dict(alpha=3, mach=0), time=dict(duration=.03, dt=.01)))))
    initial = out['snapshots'][0]
    for s in out['snapshots'][1:]:
        assert s['CL'] == pytest.approx(initial['CL'], abs=1e-10)
        np.testing.assert_allclose([n['position'] for n in s['nodes']], [n['position'] for n in initial['nodes']], atol=1e-9)
        np.testing.assert_allclose(s['local_velocity'], 0, atol=1e-10)
        np.testing.assert_allclose(s['circulation_rate'], 0, atol=1e-9)
        assert s['residual'] <= 1e-8
    # Frame translation must still advance through stationary air.
    assert out['snapshots'][-1]['frame']['position_earth'][0] < -.89
    assert initial['frame']['position_earth'] == [0,0,0]


def test_free_aerodynamic_trajectory_satisfies_independent_rigid_newton_euler_balance():
    out = json.loads(run_json(json.dumps(dict(action='time', source=Path('examples/inertial.asw').read_text(),
                    panels=4, condition=dict(alpha=5, mach=0), time=dict(duration=.03, dt=.01, frame='free')))))
    for s in out['snapshots']:
        f, moment = np.array(s['force']), np.array(s['moment'])
        frame = s['frame']
        omega, acceleration, angular = [np.array(frame[key]) for key in
                                        ['rates_body','acceleration_reference_body','angular_acceleration_body']]
        cg = np.array([.1,0,0])
        gravity = np.array(frame['body_to_earth']).T@np.array([0,0,-9.80665])
        acg = acceleration+np.cross(angular,cg)+np.cross(omega,np.cross(omega,cg))
        inertia = np.diag([500,100,550])
        np.testing.assert_allclose(f+100*gravity, 100*acg, atol=2e-5)
        np.testing.assert_allclose(moment-np.cross(cg,f), inertia@angular+np.cross(omega,inertia@omega), atol=2e-5)
        np.testing.assert_allclose(s['support_force'],0,atol=2e-5)
        assert s['max_displacement'] < 1e-9
    assert np.max(abs(np.array(out['snapshots'][-1]['circulation_rate']))) > 1
    assert abs(out['snapshots'][-1]['CL']-out['snapshots'][0]['CL']) > .01


def test_separate_velocity_and_acceleration_references_follow_straight_earth_path():
    m = rigid_body()
    m.reference[2] = [.3,-.2,.1]
    m.reference[3] = [-.1,.4,.2]
    c = FlightCondition(speed=3, alpha=7, beta=-3, mach=0, rates=[.2,.3,.4], attitude=[21,-16,33])
    rotation = body_to_earth(c.attitude)
    v_ref = -c.speed*c.vectors()[0]+np.cross(c.rates,m.reference[2]-m.reference[3])
    expected = rotation@(m.reference[2]+.2*v_ref)
    errors = []
    for dt in (.02,.01):
        out = solve_time(m, c, panels=4, duration=.2, dt=dt, gravity=[0,0,0])
        f = out['snapshots'][-1]['frame']
        at_ref = np.array(f['position_earth'])+np.array(f['body_to_earth'])@m.reference[2]
        errors.append(np.linalg.norm(at_ref-expected))
    assert errors[1] < .28*errors[0]
    assert errors[1] < 1e-4
