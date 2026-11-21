"""Independent small mechanics checks for source time UI extension paths.

Radau and optional step doubling are OpenSwing temporal extensions; these tests
do not claim that either is the discrete time algorithm of the ASWING paper.
"""
from copy import deepcopy
import json
import os
from pathlib import Path

import numpy as np

from openswing.linear_dynamics import make_system
from openswing.source_dynamics import MOVING_POLICY, SourceMovingNetwork
from openswing.time_initialization import launch_time
from openswing.time_integration import solve_time
from openswing.time_state import checkpoint, restore_checkpoint, resume_time
from test_source_moving_time import (model, PANELS, PRELOAD, OMEGA2, EXTENSION,
    TOLERANCE, oscillator, spring_state, spring_recurrence, earth_com,
    same_physical_snapshot)


def retain(name, value):
    directory = os.environ.get('SOURCE_MOVING_TIME_EXTENSION_ARTIFACTS')
    if directory:
        p = Path(directory); p.mkdir(parents=True, exist_ok=True)
        (p/(name+'.json')).write_text(json.dumps(value, allow_nan=False)+'\n')


def require_source(result, temporal_policy):
    assert result['temporal_policy'] == temporal_policy
    assert result['restart_context']['identity']['structural_operator'] == MOVING_POLICY
    assert result['restart_context']['setup']['structural_operator'] == MOVING_POLICY
    assert all(row['structural_operator'] == MOVING_POLICY for row in result['snapshots'])
    assert max(row['residual'] for row in result['snapshots']) <= TOLERANCE


def replay(aircraft, output, index=-1):
    saved = json.loads(json.dumps(checkpoint(output, index)))
    network, _, _, _, _, _, error, checked = restore_checkpoint(aircraft, saved)
    assert type(network) is SourceMovingNetwork
    assert error <= 1e-8
    verification = checked['acceptance_validation']
    assert verification['discrete_replayed']
    assert verification['residual'] <= verification['tolerance']
    return saved, verification


def scaled_oscillator_error(result):
    rows = result['snapshots']
    actual = np.array([spring_state(row) for row in rows])
    expected = np.array(oscillator([row['time'] for row in rows])).T
    return float(np.max(abs(actual-expected)/[EXTENSION, EXTENSION*np.sqrt(OMEGA2)]))


def test_source_radau_two_steps_match_exact_oscillator_and_replay_discrete_stages():
    aircraft = model()
    out = solve_time(aircraft, panels=PANELS, frame='free', gravity_magnitude=0.,
        initial_loads=PRELOAD, loads=[], duration=.02, dt=.01, order=5,
        structural_operator=MOVING_POLICY, tolerance=TOLERANCE, max_steps=3)
    retain('radau-release', out)
    require_source(out, 'openswing-so3-radau-iia-3-v1')
    assert out['accepted_steps'] == 2 and out['rejected_steps'] == 0
    rows = out['snapshots']
    actual = np.array([spring_state(row) for row in rows])
    exact = np.array(oscillator([row['time'] for row in rows])).T
    np.testing.assert_allclose(actual, exact, atol=2e-9, rtol=2e-9)
    # Independently derived [2/3] Pade/Radau rational transfer for y'=Ay.
    # No production Butcher coefficients or collocation helper is used.
    a = np.array([[0., 1.], [-OMEGA2, 0.]])
    expected = np.array([EXTENSION, 0.])
    for row, observed in zip(rows[1:], actual[1:]):
        z = row['step']*a; z2 = z@z; z3 = z2@z
        expected = np.linalg.solve(np.eye(2)-3*z/5+3*z2/20-z3/60,
                                   (np.eye(2)+2*z/5+z2/20)@expected)
        np.testing.assert_allclose(observed, expected, atol=2e-9, rtol=2e-9)
        assert row['order'] == 5
        assert row['collocation']['maximum_stage_residual'] <= row['collocation']['stage_tolerance']
    _, verification = replay(aircraft, out)
    assert verification['kind'] == 'radau_iia'
    assert verification['scheme'] == 'openswing-so3-radau-iia-3-v1'
    retain('radau-checks', dict(scaled_analytic_error=scaled_oscillator_error(out), replay=verification))


def test_source_bdf_accuracy_refines_analytic_trajectory_and_replays_hidden_midpoint():
    aircraft = model()
    outputs = []
    for label, atol in [('loose', 8e-6), ('tight', 2e-6)]:
        out = solve_time(aircraft, panels=PANELS, frame='free', gravity_magnitude=0.,
            initial_loads=PRELOAD, loads=[], duration=.04, dt=.04, order=2,
            accuracy=dict(atol=atol, rtol=1000*atol), structural_operator=MOVING_POLICY,
            tolerance=TOLERANCE, max_steps=60)
        retain('accuracy-'+label, out)
        require_source(out, 'drela-euler-bdf-v1')
        assert out['accuracy']['maximum_accepted_ratio'] <= 1
        assert out['internal_steps'] == 2*out['accepted_steps']
        assert out['snapshots'][-1]['time'] == .04
        for row in out['snapshots'][1:]:
            assert row['accuracy']['maximum_ratio'] <= 1
            assert row['restart']['older']['time'] == row['accuracy']['midpoint_time']
            assert row['restart']['accepted_method']['scheme'] == 'drela-euler-bdf-v1'
        outputs.append(out)
    errors = [scaled_oscillator_error(out) for out in outputs]
    retain('accuracy-checks', dict(scaled_analytic_errors=errors))
    assert errors[1] < .8*errors[0]
    assert errors[1] < .01
    assert outputs[1]['accuracy']['rejected_accuracy_steps'] > 0
    saved, verification = replay(aircraft, outputs[1])
    assert saved['older']['time'] == outputs[1]['snapshots'][-1]['accuracy']['midpoint_time']
    assert verification['selection']['mode'] == 'two_half_steps'
    assert verification['scheme'] == 'drela-euler-bdf-v1'


def test_saved_source_equilibrium_physical_velocity_disturbance_is_held_and_restartable():
    aircraft = model()
    system, _ = make_system(aircraft, panels=PANELS, frame='free', gravity_magnitude=0.,
        loads=PRELOAD, structural_operator=MOVING_POLICY, tolerance=TOLERANCE)
    seed = json.loads(json.dumps(system.equilibrium_state)); original = deepcopy(seed)
    retain('disturbance-modal-base-no-eigensolve', seed)
    disturbance = dict(frame=dict(velocity_origin_body=[0., .1, 0.]))
    out = launch_time(aircraft, seed, frame='free', duration=.02, dt=.01, order=2,
        loads=[], disturbance=disturbance, tolerance=TOLERANCE, max_steps=3)
    retain('disturbed-launch', out)
    require_source(out, 'drela-euler-bdf-v1')
    assert out['initialization']['disturbance'] == disturbance
    assert out['initialization']['consistency']['prescribed_coordinate_error'] == 0
    assert not out['initialization']['equilibrium_recomputed']
    assert out['continuation_steps'] == 0
    rows = out['snapshots']
    np.testing.assert_allclose(rows[0]['frame']['velocity_origin_body'], [0., .1, 0.], atol=1e-14, rtol=0)
    np.testing.assert_allclose(spring_state(rows[0]), [EXTENSION, 0.], atol=2e-10, rtol=0)
    np.testing.assert_allclose([spring_state(row) for row in rows], spring_recurrence(rows),
                               atol=2e-9, rtol=2e-8)
    r0, v0 = earth_com(rows[0])
    np.testing.assert_allclose(v0, [0., .1, 0.], atol=2e-12, rtol=0)
    for row in rows:
        position, velocity = earth_com(row)
        np.testing.assert_allclose(position, r0+v0*row['time'], atol=3e-9, rtol=3e-9)
        np.testing.assert_allclose(5*velocity, 5*v0, atol=2e-8, rtol=2e-9)
    assert scaled_oscillator_error(out) < .02
    saved, verification = replay(aircraft, out, 1)
    continued = resume_time(aircraft, saved, duration=.01)
    retain('disturbed-resume', continued)
    require_source(continued, 'drela-euler-bdf-v1')
    assert continued['continuation_steps'] == 0
    assert continued['snapshots'][1]['order'] == 2
    for a, b in zip(continued['snapshots'], rows[1:]):
        same_physical_snapshot(a, b)
    assert len(continued['snapshots']) == 2
    assert seed == original
    retain('disturbance-checks', dict(scaled_analytic_error=scaled_oscillator_error(out), replay=verification))
