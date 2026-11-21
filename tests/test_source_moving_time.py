"""Physical source-moving transients, BDF refinement, and portable history.

The two endpoint masses and massless axial spring give an independent ODE:
delta'' + tau*omega**2*delta' + omega**2*delta = 0,
omega**2 = (EA/L)*(1/m1+1/m2) = 250/3. The reference model is a
synthetic mechanics fixture, not an archived aircraft-frequency fit. Finite-step
COM positions are compared to BDF recurrence, not to exact continuous freefall.
"""
from copy import deepcopy
import json
import os
from pathlib import Path

import numpy as np
import pytest

from openswing.aero import AnalysisError, FlightCondition
from openswing.asw import parse_asw
from openswing.inertia import Motion
from openswing.linear_dynamics import make_system
from openswing.source_dynamics import MOVING_POLICY, SourceMovingNetwork
from openswing.time_initialization import launch_time
from openswing.time_integration import solve_time
from openswing.time_state import checkpoint, restore_checkpoint, resume_time


EXAMPLE = Path(__file__).resolve().parents[1]/'examples/source-moving-vacuum-check.asw'
PANELS = {'default': 4, 'beams': {'1': {'count': 4, 'spacing': 'uniform'}}}
PRELOAD = [dict(beam=1, t=1., force=[0., -1., 0.]),
           dict(beam=1, t=3., force=[0., 1., 0.])]
OMEGA2 = 250/3
EXTENSION = .01
DURATION = .08
TOLERANCE = 1e-10


def record(name, value):
    """Optional owned evidence, useful if a later independent assertion fails."""
    directory = os.environ.get('SOURCE_MOVING_TIME_ARTIFACTS')
    if directory:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        (path/(name+'.json')).write_text(json.dumps(value, allow_nan=False)+'\n')


def model(*, damping=0., rigid=False, interpolation='drela-segspl-v1'):
    text = EXAMPLE.read_text()
    if rigid:
        text = text.replace('1 200 0 0 0 0 0', '1 0 0 0 0 0 0')
        text = text.replace('3 200 0 0 0 0 0', '3 0 0 0 0 0 0')
    if damping:
        text = text.rstrip()[:-3]+f't tdeps\n1 {damping}\n3 {damping}\nEnd\n'
    return parse_asw(text, beam_interpolation=interpolation)


def oscillator(t, damping=0.):
    decay = damping*OMEGA2/2
    frequency = np.sqrt(OMEGA2-decay**2)
    t = np.asarray(t)
    extension = EXTENSION*np.exp(-decay*t)*(np.cos(frequency*t)+decay/frequency*np.sin(frequency*t))
    rate = -EXTENSION*OMEGA2/frequency*np.exp(-decay*t)*np.sin(frequency*t)
    return extension, rate


def bdf_coefficients(step, previous_step=None):
    # Independent interpolation-polynomial coefficients; no production helper.
    if previous_step is None:
        return np.array([1/step, -1/step, 0.])
    return np.array([(2*step+previous_step)/(step*(step+previous_step)),
                     -(step+previous_step)/(step*previous_step),
                     step/(previous_step*(step+previous_step))])


def spring_recurrence(snapshots, damping=0.):
    a = np.array([[0., 1.], [-OMEGA2, -damping*OMEGA2]])
    previous = np.array([EXTENSION, 0.])
    older = None
    values = [previous.copy()]
    hp = None
    for row in snapshots[1:]:
        k0, k1, k2 = bdf_coefficients(row['step'], hp)
        rhs = -k1*previous-(k2*older if older is not None else 0.)
        current = np.linalg.solve(k0*np.eye(2)-a, rhs)
        values.append(current.copy())
        older, previous, hp = previous, current, row['step']
    return np.asarray(values)


def com_recurrence(snapshots, position, velocity, acceleration):
    previous = np.r_[position, velocity]
    older = None
    values = [previous.copy()]
    a = np.zeros((6, 6)); a[:3, 3:] = np.eye(3)
    forcing = np.r_[np.zeros(3), acceleration]
    hp = None
    for row in snapshots[1:]:
        k0, k1, k2 = bdf_coefficients(row['step'], hp)
        rhs = forcing-k1*previous-(k2*older if older is not None else 0.)
        current = np.linalg.solve(k0*np.eye(6)-a, rhs)
        values.append(current.copy())
        older, previous, hp = previous, current, row['step']
    return np.asarray(values)


def spring_state(snapshot):
    a, b = snapshot['nodes'][0], snapshot['nodes'][-1]
    delta = np.asarray(b['position'])-np.asarray(a['position'])
    velocity = np.asarray(snapshot['local_velocity'])
    # This fixture remains axially translating with zero angular velocity.
    return np.array([delta[1]-2, velocity[-1, 1]-velocity[0, 1]])


def earth_com(snapshot):
    frame = snapshot['frame']
    rotation = np.asarray(frame['body_to_earth'])
    origin, u, omega = (np.asarray(frame[key]) for key in
                        ('position_earth', 'velocity_origin_body', 'rates_body'))
    positions, velocities = [], []
    for i in (0, -1):
        r = np.asarray(snapshot['nodes'][i]['position'])
        local = np.asarray(snapshot['local_velocity'][i])
        positions.append(origin+rotation@r)
        velocities.append(rotation@(u+np.cross(omega, r)+local))
    return (2*positions[0]+3*positions[1])/5, (2*velocities[0]+3*velocities[1])/5


def check_source_identity(result):
    assert result['temporal_policy'] == 'drela-euler-bdf-v1'
    identity = result['restart_context']['identity']
    assert identity['structural_operator'] == MOVING_POLICY
    assert identity['beam_interpolation'] == 'drela-segspl-v1'
    assert result['restart_context']['setup']['structural_operator'] == MOVING_POLICY
    for row in result['snapshots']:
        assert row['structural_operator'] == MOVING_POLICY
        assert row['restart']['accepted_method']['accepted_inputs']['identity'] == identity
        assert row['residual'] <= TOLERANCE
        accepted = row['restart']['accepted_method']
        if accepted['kind'] == 'bdf':
            assert accepted['scheme'] == 'drela-euler-bdf-v1'


@pytest.fixture(scope='module')
def released_series():
    aircraft = model()
    runs = []
    for dt in (.02, .01, .005):
        out = solve_time(aircraft, panels=PANELS, frame='free', duration=DURATION, dt=dt, order=2,
            gravity_magnitude=3., position=[.3, -.2, .7], attitude=[13., -17., 23.],
            velocity=[.2, -.1, .3], initial_loads=PRELOAD, loads=[],
            tolerance=TOLERANCE, structural_operator=MOVING_POLICY, max_steps=20)
        record('released-'+str(dt), out)
        runs.append(out)
    return aircraft, runs


def test_three_grid_bdf2_axial_transient_matches_independent_ode_and_discrete_recurrence(released_series):
    _, runs = released_series
    errors = []
    for out in runs:
        check_source_identity(out)
        rows = out['snapshots']
        assert out['rejected_steps'] == 0
        assert [s['order'] for s in rows[1:]] == [1]+[2]*(len(rows)-2)
        actual = np.array([spring_state(s) for s in rows])
        exact = np.array(oscillator([s['time'] for s in rows])).T
        # Original full time residuals and an independently assembled scalar
        # discrete equation both have to pass, not only the final curve.
        np.testing.assert_allclose(actual, spring_recurrence(rows), atol=2e-9, rtol=2e-8)
        errors.append(float(np.max(abs(actual[:, 0]-exact[:, 0]))))
    record('axial-refinement', dict(displacement_errors=errors,dt=[.02,.01,.005]))
    assert errors[1] < .4*errors[0]
    assert errors[2] < .4*errors[1]
    assert errors[2] < 2e-5


def test_free_frame_earth_com_obeys_momentum_and_independent_bdf_freefall(released_series):
    _, runs = released_series
    position_errors = []
    gravity = np.array([0., 0., -3.])
    for out in runs:
        rows = out['snapshots']
        initial_position, initial_velocity = earth_com(rows[0])
        actual = np.array([np.r_[*earth_com(row)] for row in rows])
        discrete = com_recurrence(rows, initial_position, initial_velocity, gravity)
        np.testing.assert_allclose(actual, discrete, atol=3e-9, rtol=3e-9)
        times = np.array([s['time'] for s in rows])
        # Total momentum changes only by total mass times Earth gravity.
        np.testing.assert_allclose(5*actual[:, 3:],
            5*(initial_velocity+times[:, None]*gravity), atol=2e-8, rtol=2e-9)
        continuous = initial_position+times[:, None]*initial_velocity+.5*times[:, None]**2*gravity
        position_errors.append(float(np.max(abs(actual[:, :3]-continuous))))
        assert max(np.linalg.norm(s['frame']['rates_body']) for s in rows) < 2e-9
    assert position_errors[1] < .3*position_errors[0]
    assert position_errors[2] < .3*position_errors[1]


def same_physical_snapshot(a, b):
    assert a['time'] == pytest.approx(b['time'], abs=1e-13)
    for key in ('local_velocity', 'local_rates', 'local_acceleration', 'local_rate_derivative'):
        np.testing.assert_allclose(a[key], b[key], atol=2e-9, rtol=2e-9)
    for key in a['frame']:
        np.testing.assert_allclose(a['frame'][key], b['frame'][key], atol=2e-9, rtol=2e-9)
    for x, y in zip(a['nodes'], b['nodes']):
        np.testing.assert_allclose(x['position'], y['position'], atol=2e-9, rtol=2e-9)
        np.testing.assert_allclose(x['rotation'], y['rotation'], atol=2e-9, rtol=2e-9)


def test_bdf2_checkpoint_preserves_source_network_history_and_original_step_equations(released_series):
    aircraft, runs = released_series
    out = runs[-1]
    index = 8
    saved = json.loads(json.dumps(checkpoint(out, index)))
    before = deepcopy(saved)
    n, _, _, older, _, _, error, restored = restore_checkpoint(aircraft, saved)
    assert type(n) is SourceMovingNetwork
    assert older is not None
    assert error <= 1e-8
    validation = restored['acceptance_validation']
    assert validation['discrete_replayed']
    assert validation['residual'] <= validation['tolerance']
    continued = resume_time(aircraft, saved, duration=DURATION-saved['state']['time'])
    record('checkpoint-resumed', continued)
    assert continued['continuation_steps'] == 0
    assert continued['snapshots'][1]['order'] == 2
    assert continued['checkpoint_validation']['discrete_replayed']
    check_source_identity(continued)
    assert len(continued['snapshots']) == len(out['snapshots'])-index
    for a, b in zip(continued['snapshots'], out['snapshots'][index:]):
        same_physical_snapshot(a, b)
    assert saved == before


@pytest.mark.parametrize('location', ['context_identity', 'setup', 'accepted_identity', 'accepted_setup', 'predecessor'])
def test_checkpoint_policy_or_hidden_predecessor_tampering_is_rejected(released_series, location):
    aircraft, runs = released_series
    saved = checkpoint(runs[-1], 8)
    if location == 'context_identity':
        saved['context']['identity']['structural_operator'] = 'midpoint-v1'
    elif location == 'setup':
        saved['context']['setup']['structural_operator'] = 'midpoint-v1'
    elif location == 'accepted_identity':
        saved['accepted_method']['accepted_inputs']['identity']['structural_operator'] = 'midpoint-v1'
    elif location == 'accepted_setup':
        saved['accepted_method']['accepted_inputs']['setup']['structural_operator'] = 'midpoint-v1'
    else:
        saved['older']['local_velocity'][-1][1] += .01
    with pytest.raises(AnalysisError):
        restore_checkpoint(aircraft, saved)


@pytest.mark.parametrize('location', ['context', 'accepted', 'both'])
@pytest.mark.parametrize('metric', [None, 'chord-ratio-v0'])
def test_checkpoint_old_or_changed_source_interval_measure_is_rejected(released_series, location, metric):
    aircraft, runs = released_series
    saved = checkpoint(runs[-1], 8)
    identities = [saved['context']['identity'], saved['accepted_method']['accepted_inputs']['identity']]
    selected = identities if location == 'both' else [identities[0 if location == 'context' else 1]]
    for identity in selected:
        if metric is None:
            identity.pop('deformed_interval_measure')
        else:
            identity['deformed_interval_measure'] = metric
    with pytest.raises(AnalysisError):
        restore_checkpoint(aircraft, saved)


@pytest.fixture(scope='module')
def damped_seed():
    aircraft = model(damping=.02)
    system, _ = make_system(aircraft, panels=PANELS, frame='free', gravity_magnitude=0.,
        loads=PRELOAD, structural_operator=MOVING_POLICY, tolerance=TOLERANCE)
    assert type(system.network) is SourceMovingNetwork
    seed = json.loads(json.dumps(system.equilibrium_state))
    record('damped-modal-equilibrium-no-eigensolve', seed)
    return aircraft, seed


def test_saved_source_modal_equilibrium_launches_damped_release_without_legacy_recovery(damped_seed):
    aircraft, seed = damped_seed
    original = deepcopy(seed)
    out = launch_time(aircraft, seed, frame='free', duration=.04, dt=.01, order=2,
                      loads=[], tolerance=TOLERANCE, max_steps=6)
    record('damped-modal-launch', out)
    check_source_identity(out)
    assert out['continuation_steps'] == 0
    assert not out['initialization']['equilibrium_recomputed']
    assert out['snapshots'][0]['initial_phase'] == 'saved_equilibrium_before_time_inputs'
    rows = out['snapshots']
    actual = np.array([spring_state(s) for s in rows])
    np.testing.assert_allclose(actual, spring_recurrence(rows, .02), atol=2e-9, rtol=2e-8)
    exact = np.array(oscillator([s['time'] for s in rows], .02)).T
    assert np.max(abs(actual[:, 0]-exact[:, 0])) < 1e-4
    assert np.max(abs(actual[1:, 1])) > .005
    for row in rows[1:]:
        for element in row['elements']:
            assert element['strain_source'] == 'source_discrete_damped_constitutive'
            assert all(trace['strain'] is None for trace in element['endpoint_traces'])
        # Uniform axial mechanical strain is the geometric extension/L;
        # total force includes the viscous term and is not its static inverse.
        np.testing.assert_allclose([e['strain'][1] for e in row['elements']],
                                   spring_state(row)[0]/2, atol=2e-9, rtol=2e-8)
    n, *_ = restore_checkpoint(aircraft, checkpoint(out, 2))
    assert type(n) is SourceMovingNetwork
    assert seed == original


@pytest.mark.parametrize('policy', ['midpoint-v1', 'drela-fixed-vacuum-v1', 'drela-fixed-still-air-v1', 'drela-steady-section-v1'])
def test_saved_launch_cannot_change_source_equation_identity(damped_seed, policy):
    aircraft, original = damped_seed
    seed = deepcopy(original)
    seed['identity']['structural_operator'] = policy
    with pytest.raises(AnalysisError):
        launch_time(aircraft, seed, frame='free', duration=.01, dt=.01)


@pytest.mark.parametrize('metric', [None, 'chord-ratio-v0'])
def test_saved_launch_rejects_old_or_changed_source_interval_measure(damped_seed, metric):
    aircraft, original = damped_seed
    seed = deepcopy(original)
    if metric is None:
        seed['identity'].pop('deformed_interval_measure')
    else:
        seed['identity']['deformed_interval_measure'] = metric
    with pytest.raises(AnalysisError, match='interval measure.*[Rr]ecompute'):
        launch_time(aircraft, seed, frame='free', duration=.01, dt=.01)


@pytest.mark.parametrize('frame,channel,target,acceleration', [
    ('prescribed', 'Ay', None, 2.),
    ('mixed', 'Fy', {'force.y': 1.}, -.2),
])
def test_canonical_frame_forcing_uses_source_physical_net_loads(frame, channel, target, acceleration):
    value = 2. if channel == 'Ay' else 1.
    out = solve_time(model(rigid=True), panels=PANELS, frame=frame, duration=.04, dt=.02,
        forcing=f'time {channel}\n0 {value}\n.1 {value}\n', load_targets=target,
        gravity_magnitude=0., structural_operator=MOVING_POLICY, tolerance=TOLERANCE, max_steps=3)
    record('forcing-'+channel, out)
    check_source_identity(out)
    rows = out['snapshots']
    expected = com_recurrence(rows, np.array([0., 1.2, 0.]), np.zeros(3), np.array([0., acceleration, 0.]))
    actual = np.array([np.r_[*earth_com(row)] for row in rows])
    np.testing.assert_allclose(actual, expected, atol=3e-9, rtol=3e-9)
    for row in rows:
        assert row['forcing_values'][channel] == pytest.approx(value)
        assert row['frame']['acceleration_reference_body'][1] == pytest.approx(acceleration, abs=2e-9)
        if frame == 'mixed':
            assert row['operating_constraints'][0]['actual'] == pytest.approx(1., abs=2e-9)


def earth_euler_rate(angles, omega):
    """Literal unsteady Eq.15, independently read from rendered page 6."""
    bank, elevation, _ = angles
    sb, cb = np.sin(bank), np.cos(bank)
    te, ce = np.tan(elevation), np.cos(elevation)
    ox, oy, oz = omega
    return np.array([-ox+sb*te*oy-cb*te*oz,
                     cb*oy+sb*oz,
                     (sb*oy-cb*oz)/ce])


def earth_euler_frame(angles):
    """Independent matrix product of unsteady Eq.6; input radians."""
    bank, elevation, heading = angles
    cb, ce, ch = np.cos([bank, elevation, heading])
    sb, se, sh = np.sin([bank, elevation, heading])
    return np.array([[ch, sh, 0], [-sh, ch, 0], [0, 0, 1]]) @ np.array([
        [ce, 0, se], [0, 1, 0], [-se, 0, ce]]) @ np.array([
        [1, 0, 0], [0, cb, sb], [0, -sb, cb]])


def material_euler_rate(angles, omega):
    """Literal surface-beam unsteady Eq.3, without production rate maps."""
    phi, _, psi = angles
    cp, sp, cpsi, tpsi = np.cos(phi), np.sin(phi), np.cos(psi), np.tan(psi)
    wx, wy, wz = omega
    return np.array([wx+cp*tpsi*wy+sp*tpsi*wz,
                     (cp*wy+sp*wz)/cpsi,
                     -sp*wy+cp*wz])


def test_prescribed_changing_rotation_axis_crosses_heading_cut_in_paper_euler_bdf_chart():
    aircraft = model(rigid=True)
    omega0 = np.array([.2, -.15, -.5])
    alpha = np.array([.4, .3, -.2])
    out = solve_time(aircraft, panels=PANELS, frame='prescribed', duration=.08, dt=.02,
        attitude=[11., -7., 179.], motion=Motion(rates=omega0, angular_acceleration=alpha),
        gravity_magnitude=0., structural_operator=MOVING_POLICY,
        tolerance=TOLERANCE, max_steps=5)
    record('rotating-heading-crossing', out)
    check_source_identity(out)
    rows = out['snapshots']
    assert len(rows) == 5 and out['rejected_steps'] == 0
    lifted = np.array([s['restart']['state']['source_attitude'] for s in rows])
    assert lifted[0, 2] < np.pi < lifted[-1, 2]
    assert np.max(abs(np.diff(lifted, axis=0))) < .05
    # Source snapshots expose the same owned lift in degrees, not principal
    # display angles; the physically equivalent matrices still cross the cut.
    np.testing.assert_allclose([s['frame']['attitude'] for s in rows],
                               np.rad2deg(lifted), atol=2e-11, rtol=2e-11)
    assert rows[0]['frame']['attitude'][2] < 180 < rows[-1]['frame']['attitude'][2]
    assert np.linalg.norm(np.cross(omega0, omega0+alpha*.08)) > .01
    for index, row in enumerate(rows):
        state = row['restart']['state']
        omega = np.array(row['frame']['rates_body'])
        np.testing.assert_allclose(omega, omega0+alpha*row['time'], atol=2e-9, rtol=2e-9)
        np.testing.assert_allclose(earth_euler_frame(lifted[index]),
                                   row['frame']['body_to_earth'], atol=2e-11, rtol=2e-11)
        np.testing.assert_allclose(row['local_rates'], 0., atol=2e-9)
        if index == 0:
            continue
        k0, _, k2 = bdf_coefficients(row['step'], None if index == 1 else rows[index-1]['step'])
        rate = k0*(lifted[index]-lifted[index-1])
        if index > 1:
            rate += k2*(lifted[index-2]-lifted[index-1])
        np.testing.assert_allclose(rate, earth_euler_rate(lifted[index], omega), atol=2e-9, rtol=2e-9)
        angles = np.asarray(state['source_angles'])
        previous = np.asarray(rows[index-1]['restart']['state']['source_angles'])
        local_rate = k0*(angles-previous)
        if index > 1:
            older = np.asarray(rows[index-2]['restart']['state']['source_angles'])
            local_rate += k2*(older-previous)
        expected = [material_euler_rate(q, w) for q, w in zip(angles, row['local_rates'])]
        np.testing.assert_allclose(local_rate, expected, atol=2e-9, rtol=2e-9)
    saved = checkpoint(out, 3)
    n, _, _, _, _, _, _, checked = restore_checkpoint(aircraft, saved)
    assert type(n) is SourceMovingNetwork
    assert checked['acceptance_validation']['scheme'] == 'drela-euler-bdf-v1'
    assert checked['acceptance_validation']['discrete_replayed']
    # The same physical matrix does not authorize changing the recorded chart.
    for field, component in [('source_attitude', 2), ('source_angles', 0)]:
        altered = deepcopy(saved)
        if field == 'source_attitude':
            altered['state'][field][component] += 2*np.pi
        else:
            altered['state'][field][0][component] += 2*np.pi
        with pytest.raises(AnalysisError):
            restore_checkpoint(aircraft, altered)


@pytest.mark.parametrize('policy', ['drela-fixed-vacuum-v1', 'drela-fixed-still-air-v1', 'drela-steady-section-v1'])
def test_old_source_policies_do_not_gain_time_support(policy):
    with pytest.raises((AnalysisError, ValueError), match='source|Source|policy|operator'):
        solve_time(model(), panels=PANELS, frame='free', duration=.01, dt=.01,
                   structural_operator=policy)


@pytest.mark.parametrize('option,value', [
    ('condition', FlightCondition(speed=1)),
    ('controller', {}),
    ('actuator_constraints', [dict(variable='control.1', quantity='force.y', target=0.)]),
])
def test_source_time_rejects_flow_controllers_and_arbitrary_actuator_constraints(option, value):
    with pytest.raises((AnalysisError, ValueError)):
        solve_time(model(), panels=PANELS, frame='free', duration=.01, dt=.01,
                   structural_operator=MOVING_POLICY, **{option: value})


def test_source_time_rejects_wrong_beam_interpolation():
    with pytest.raises((AnalysisError, ValueError), match='interpolation|drela'):
        solve_time(model(interpolation='natural-v1'), panels=PANELS, frame='free', duration=.01,
                   dt=.01, structural_operator=MOVING_POLICY)
