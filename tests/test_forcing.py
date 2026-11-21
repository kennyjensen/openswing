from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.forcing import TimeForcing
from openswing.inertia import Motion
from openswing.time_integration import solve_time
from test_time_integration import rigid_body


def table(text, duration=2., condition=None, frame='prescribed'):
    m = parse_asw(Path('examples/inertial.asw').read_text())
    c = FlightCondition(controls={1: 3}) if condition is None else condition
    return TimeForcing(text, m, c, c.motion(), duration, frame)


def test_natural_cubic_interpolation_with_documented_scaling_comments_and_offsets():
    f = table('''# headings
time +F1 Gz
* 2 2 1
+ 0 1 0
0 0 0
.5 .5 90 ! midpoint
1 0 180
''')
    for t in np.linspace(0, 2, 19):
        x = min(t, 2-t)
        assert f.values(t)['F1'] == pytest.approx(4+1.5*x-.5*x**3)
        c, motion = f.apply(t, FlightCondition(controls={1: 3}), Motion())
        assert motion.angular_acceleration[2] == pytest.approx(np.pi*t/2)
        assert c.controls[1] == f.values(t)['F1']
    assert f.report()['channels'][0]['initial'] == 3


def test_doubled_times_have_independent_linear_segments_and_side_values():
    f = table('time F1\n0 1\n.7 2\n.7 5\n2 3\n')
    assert f.values(.7, 'left')['F1'] == 2
    assert f.values(.7, 'right')['F1'] == 5
    assert f.values(.35)['F1'] == pytest.approx(1.5)
    assert f.values(1.35)['F1'] == pytest.approx(4)
    np.testing.assert_array_equal(f.breaks, [.7,2])


@pytest.mark.parametrize('source,match', [
    ('F1\n0 1\n2 1', 'header'),
    ('time V\n0 1\n2 1', 'Unsupported'),
    ('time Ax[2]\n0 1\n2 1', 'Unsupported'),
    ('time F2\n0 1\n2 1', 'declared flap'),
    ('time E1\n0 1\n2 1', 'declared engine'),
    ('time F1 +f1\n0 1 1\n2 1 1', 'Duplicate'),
    ('time F1\n.1 1\n2 1', 'start at or before'),
    ('time F1\n2 1\n0 1', 'nondecreasing'),
    ('time F1\n0 1\n1 1\n1 2\n1 3\n2 3', 'each side'),
    ('time F1\n0 1\n2 1 2', 'exactly 2'),
    ('time F1\n0 nan\n2 1', 'finite'),
])
def test_bad_or_unimplemented_forcing_is_rejected_before_integration(source, match):
    with pytest.raises(ValueError, match=match):
        table(source)


def test_acceleration_history_cannot_override_free_flight_load_equations():
    with pytest.raises(ValueError, match='conflicts'):
        table('time Ax\n0 0\n2 0', frame='free')


def test_prescribed_acceleration_ramp_converges_to_exact_cubic_translation():
    errors = []
    for dt in (.04, .02, .01):
        out = solve_time(rigid_body(), panels=4, duration=.4, dt=dt, gravity=[0,0,0],
                         forcing='time Ax\n0 0\n.4 1.2')
        last = out['snapshots'][-1]
        # a=3t, v=3t²/2, x=t³/2, independently integrated.
        assert last['frame']['acceleration_reference_body'][0] == pytest.approx(1.2)
        error = max(abs(last['frame']['velocity_origin_body'][0]-.24),
                    abs(last['frame']['position_earth'][0]-.032))
        errors.append(error)
    assert errors[1] < .28*errors[0]
    assert errors[2] < .28*errors[1]


def test_step_impulse_is_not_applied_before_jump_and_bdf_restarts():
    # A non-grid-aligned jump must still get its own state, using its left value.
    out = solve_time(rigid_body(), panels=4, duration=.27, dt=.04, gravity=[0,0,0],
                     forcing='time Ax\n0 0\n.113 0\n.113 2\n.27 2')
    snapshots = out['snapshots']
    event = next(i for i, s in enumerate(snapshots) if s['time'] == .113)
    for s in snapshots[:event+1]:
        np.testing.assert_allclose(s['frame']['velocity_origin_body'], 0, atol=1e-10)
        assert s['forcing_values']['Ax'] == 0
    assert snapshots[event]['forcing_side'] == 'left'
    assert snapshots[event+1]['order'] == 1
    for s in snapshots[event+1:]:
        assert s['forcing_values']['Ax'] == 2
        assert s['frame']['velocity_origin_body'][0] == pytest.approx(2*(s['time']-.113), abs=1e-9)
    assert out['rejected_steps'] == 0


def test_flap_history_reaches_actual_section_pitching_loads():
    m = parse_asw(Path('examples/inertial.asw').read_text())
    out = solve_time(m, FlightCondition(alpha=0, mach=0), panels=4, duration=.11, dt=.01,
                     forcing='time F1\n0 0\n.11 3')
    for s in out['snapshots']:
        # Rigid horizontal wing, no flap lift derivative: pitch coefficient is
        # the prescribed section moment with the documented local compressibility
        # correction (separate from the fixed global PG Mach), without lag lift.
        flap = 3*s['time']/.11
        assert s['operating_values']['control.1'] == pytest.approx(flap)
        assert s['Cm'] == pytest.approx((-.03-.012*flap)/np.sqrt(1-(30/m.constants[2])**2), abs=1e-9)
    assert min(s['step'] for s in out['snapshots'][1:]) > .009


def test_time_varying_proportional_thrust_accelerates_free_rigid_mass():
    m = rigid_body()
    row = np.zeros(25)
    row[:15] = [1, 0, 1, 0, 0, 0, 0, -1, 0, 0, 1, 0, -1, 150, 0]
    m.records['engine'] = [row]
    # No lifting sections or finite body volume: force = -2t, mass = 1.
    errors = []
    for dt in (.04,.02):
        out = solve_time(m, FlightCondition(speed=3, alpha=0, mach=0), panels=4, frame='free',
                         duration=.2, dt=dt, gravity=[0,0,0], forcing='time E1\n0 0\n.2 .4')
        for s in out['snapshots']:
            np.testing.assert_allclose(s['frame']['acceleration_reference_body'], [-2*s['time'],0,0], atol=2e-9)
            np.testing.assert_allclose(s['support_force'], 0, atol=2e-9)
        errors.append(abs(out['snapshots'][-1]['frame']['velocity_origin_body'][0]+3.04))
    assert errors[1] < .28*errors[0]


def test_angular_acceleration_table_integrates_in_degrees_with_second_order_rotation():
    errors = []
    for dt in (.04,.02):
        out = solve_time(rigid_body(), panels=4, duration=.2, dt=dt, gravity=[0,0,0],
                         motion=Motion(rates=[0,0,.3]), forcing='time Gz\n0 0\n.2 45')
        final = out['snapshots'][-1]['frame']
        jerk = np.deg2rad(45)/.2
        angle = .3*.2+jerk*.2**3/6
        expected = np.array([[np.cos(angle),-np.sin(angle),0],
                             [np.sin(angle),np.cos(angle),0],[0,0,1]])
        errors.append(np.linalg.norm(np.array(final['body_to_earth'])-expected))
        assert final['angular_acceleration_body'][2] == pytest.approx(np.pi/4)
    assert errors[1] < .29*errors[0]


def test_flap_ramp_time_domain_lift_converges_to_the_analytic_empirical_lag():
    # At infinite aspect ratio, c=1, V=10: circulation relaxation tau=2c/V.
    # CLcmd=.01t gives CL=.01*(t-tau/2*(1-exp(-t/tau))). This checks the
    # integrated circulation state AND rate lift, rather than a static matrix.
    source = Path('examples/rectangular.asw').read_text()
    source = source[:source.index('t dCLdF1')]+'t dCLdF1\n0 .1\n100000 .1\nEnd\n'
    source = (source.replace('6 0 6 0', '100000 0 100000 0').replace('6 .008', '100000 .008')
              .replace('.008', '0').replace('12 1 12', '200000 1 200000'))
    model = parse_asw(source)
    errors = []
    for dt in (.02, .01, .005):
        result = solve_time(model, FlightCondition(speed=10, alpha=0, mach=0, stall=False), 4,
                            duration=.2, dt=dt, tolerance=1e-10, gravity=[0,0,0],
                            forcing='time F1\n0 0\n.2 .02')
        times = np.array([s['time'] for s in result['snapshots']])
        actual = np.array([s['CL'] for s in result['snapshots']])
        exact = .01*(times-.1*(1-np.exp(-times/.2)))
        errors.append(np.max(abs(actual-exact)))
    assert errors[1] < .3*errors[0]
    assert errors[2] < .3*errors[1]
    assert errors[-1] < 5e-7
