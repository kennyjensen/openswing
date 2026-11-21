"""Independent outputs do not require a complete sensor orientation (unsteady §10)."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from openswing.aero import AnalysisError, FlightCondition
from openswing.asw import parse_asw
from openswing.bridge import run_json
from openswing.geometry import attachment_geometry, model_meshes
from openswing.ground import body_to_earth
from openswing.inertia import Motion
from openswing.linear_dynamics import make_system, output_perturbation
from openswing.local_motion import LocalMotion, rotation_matrix
from openswing.network import solve_static
from openswing.rom_outputs import MeasurementOutputs
from openswing.sensors import measure_sensor, sensor_axes, sensor_orientation, validate_sensors
from test_network import model
from test_sensors import with_sensor, z
from test_time_integration import oscillator


ST1 = Path('.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/'
           '3 - Structure/CASE - ST1 High aspect ratio/Static_deflection/[45_0]_3a.asw')
PROJECTED = ('axes_body', 'axes_earth', 'air_velocity_sensor', 'rates_sensor',
             'acceleration_sensor', 'angular_acceleration_sensor', 'alpha', 'beta', 'bank')


def row(v=(1, 1, 1), a=(1, 1, 1)):
    return np.array([1, 1, 1, .4, 1.2, -.3, *v, *a], dtype=float)


@pytest.mark.parametrize('v,a,reason', [
    ((1, 1, 1), (2, 2, 2), 'parallel'),
    ((1, 0, 0), (1, 1e-12, 0), 'nearly parallel'),
    ((1, 0, 0), (0, 0, 0), 'nonzero'),
    ((0, 0, 0), (0, 0, 1), 'nonzero'),
])
def test_partial_axes_preserve_literal_records_and_reject_only_full_triad_request(v, a, reason):
    raw = row(v, a)
    configuration = with_sensor(model(), ' '.join(map(str, raw)))
    np.testing.assert_array_equal(configuration.records['sensor'][0], raw)
    axes, longitudinal, diagnostic = sensor_orientation(raw)
    assert axes is None and reason in diagnostic
    assert (longitudinal is None) == (not any(v))
    assert any(reason in d for d in validate_sensors(configuration))
    assert not configuration.diagnostics  # Unrecognized-input errors still block solves.
    with pytest.raises(ValueError, match=reason):
        sensor_axes(raw)


@pytest.mark.parametrize('magnitude', [1e-300, 1e-160, 1e-100, 1., 1e100, 1e300])
def test_arbitrary_axis_magnitudes_leave_rotation_unchanged(magnitude):
    raw = row((3, 0, 4), (-4, 0, 3)); before = raw.copy()
    raw[6:9] *= magnitude
    raw[9:12] /= magnitude
    expected = np.array([[.6, 0, -.8], [0, 1, 0], [.8, 0, .6]])
    np.testing.assert_allclose(sensor_axes(raw), expected, atol=4e-16)
    np.testing.assert_allclose(sensor_axes(before), expected, atol=4e-16)


def test_both_omitted_vectors_keep_documented_default():
    raw = row((0, 0, 0), (0, 0, 0))
    axes, longitudinal, reason = sensor_orientation(raw)
    np.testing.assert_array_equal(axes, np.eye(3))
    np.testing.assert_array_equal(longitudinal, [1, 0, 0])
    assert reason is None


@pytest.mark.parametrize('field', range(12))
def test_complete_postscaled_row_must_be_finite(field):
    raw = row(); raw[field] = np.inf
    with pytest.raises(ValueError, match='finite fields'):
        sensor_orientation(raw)


def test_finite_source_numbers_that_overflow_pylon_scaling_reject():
    text = model().dumps() + '\nSensor\n* 1 1e308\n1 1 1 1e308 1 0\nEnd\n'
    with np.errstate(over='ignore'), pytest.raises(ValueError, match='finite fields'):
        parse_asw(text)


@pytest.mark.parametrize('v,a', [((1, 1, 1), (1, 1, 1)), ((0, 0, 0), (0, 0, 1))])
def test_partial_sensor_motion_matches_independent_pylon_trajectory(v, a):
    raw = row(v, a); configuration = model()
    earth = body_to_earth([27, -18, 39]); q = rotation_matrix(np.array([.2, -.4, .3]))
    anchor = np.array([.1, 1.1, -.2]); u = np.array([.2, -.1, .3]); w = np.array([.6, -.2, .1])
    omega = np.array([.3, .4, -.5]); origin = np.array([2., 4., -1]); velocity = np.array([-12., 3., 2.])
    motion = Motion(omega, np.zeros(3)); local = LocalMotion(anchor, u, w, np.zeros(3), np.zeros(3))
    condition = FlightCondition(speed=12, sensor_flow='kinematic')
    result = measure_sensor(raw, anchor, q, local, motion, model=configuration, condition=condition,
        gravity=[0, 0, -9.81], frame=dict(body_to_earth=earth, position_earth=origin, velocity_origin_body=earth.T@velocity))
    arm = raw[3:6]-[0, 1, 0]
    def position(t):
        return origin+t*velocity+earth@rotation_matrix(t*omega)@(anchor+t*u+rotation_matrix(t*w)@q@arm)
    h = 1e-5
    measured_velocity = (position(h)-position(-h))/(2*h)
    np.testing.assert_allclose(result['position_earth'], position(0), atol=1e-14)
    np.testing.assert_allclose(result['velocity_earth'], measured_velocity, atol=1e-9)
    assert result['speed'] == pytest.approx(np.linalg.norm(measured_velocity), abs=1e-9)
    assert result['flow_singular'] is False and result['axes_available'] is False
    assert all(result[key] is None for key in PROJECTED)
    if any(v):
        direction = earth@q@(np.array(v)/np.linalg.norm(v))
        assert result['heading'] == pytest.approx(np.rad2deg(np.arctan2(-direction[1], direction[0])))
        assert result['elevation'] == pytest.approx(np.rad2deg(np.arctan2(-direction[2], np.hypot(*direction[:2]))))
    else:
        assert result['heading'] is None and result['elevation'] is None
    json.dumps(result, allow_nan=False)


@pytest.mark.skipif(not ST1.is_file(), reason='Optional pinned ISAE archive is not installed.')
def test_original_st1_model_is_lossless_and_inspection_retains_anchor_and_pylon():
    source = ST1.read_text(); configuration = parse_asw(source, beam_interpolation='drela-segspl-v1')
    assert configuration.dumps() == source
    raw = configuration.records['sensor'][0]
    np.testing.assert_array_equal(raw[6:9], raw[9:12])
    result = json.loads(run_json(json.dumps(dict(action='inspect', source=source, panels=10))))
    assert len(result['sensors']) == len(configuration.records['sensor']) == 1
    sensor = result['sensors'][0]
    assert sensor['axes_available'] is False and sensor['v_axis_available'] is True
    assert 'parallel' in sensor['axes_unavailable_reason']
    mesh = model_meshes(configuration, 10)[0]
    assert raw[2] in np.r_[mesh.t0, mesh.t1]
    attachment = next(v for v in attachment_geometry(configuration) if v['kind'] == 'sensor')
    assert len(attachment['segments']) == 1
    np.testing.assert_array_equal(attachment['segments'][0][1], raw[3:6])
    json.dumps(result, allow_nan=False)


def test_axes_do_not_change_mechanics_or_beam_frame_section_outputs():
    configurations = [with_sensor(model(), '1 1 1 .4 1.2 -.3 '+directions)
                      for directions in ('1 0 0 0 0 1', '1 1 1 1 1 1')]
    results = [solve_static(m, panels=4, gravity=[0, 0, 0], loads=[dict(beam=1, t=2, force=[1, 2, 3])])
               for m in configurations]
    for field in ('force_balance', 'moment_balance', 'support_force', 'support_moment'):
        np.testing.assert_array_equal(results[0][field], results[1][field])
    for field in ('force_local', 'moment_local', 'strain', 'curvature_change',
                  'position_body', 'anchor_position_body', 'position_earth', 'velocity_earth'):
        np.testing.assert_array_equal(results[0]['sensors'][0][field], results[1]['sensors'][0][field])
    assert all(r['residual'] < 1e-8 for r in results)


def test_complex_speed_and_v_axis_angles_survive_missing_transverse_axes():
    configuration = with_sensor(oscillator(.02), '1 1 2 0 2 0 1 0 0 1 0 0')
    condition = FlightCondition(speed=10, alpha=0, mach=0, sensor_flow='kinematic')
    system, _ = make_system(configuration, condition, 4, gravity=[0, 0, 0])
    direction = np.zeros(system.size, dtype=complex)
    direction[system.velocity_start:system.frame_start].reshape(2, -1, 3)[0, :, 0] = .4+.7j
    direction[:6*system.network.nn].reshape(-1, 6)[:, 5] = .2+.3j
    output = output_perturbation(system, direction, np.zeros_like(direction))['sensors'][0]
    assert z(output['speed']) == pytest.approx(-system.V*(.4+.7j), abs=1e-8)
    assert z(output['heading']) == pytest.approx(-180/np.pi*(.2+.3j), abs=1e-8)
    assert output['elevation'] is not None
    assert all(output[key] is None for key in PROJECTED if key not in ('axes_body', 'axes_earth'))
    json.dumps(output, allow_nan=False)
    selection = MeasurementOutputs(system, ['V[1]', 'RY[1]', 'Ey[1]', 'Ez[1]'])
    np.testing.assert_allclose(selection.base, [10, 2, 0, 0], atol=1e-10)
    for field in ('A', 'B', 'Ex', 'Ax', 'Gx', 'Wx'):
        with pytest.raises(AnalysisError, match='undefined'):
            MeasurementOutputs(system, [field+'[1]'])


def test_feedback_and_custom_trim_accept_position_but_reject_undefined_axes():
    from test_custom_constraints import setup, target, solve
    configuration, condition = setup()
    original = deepcopy(configuration.records['sensor'])
    for sensor in configuration.records['sensor']:
        sensor[6:] = [1, 0, 0, 1, 0, 0]
    result = solve(configuration, condition, [target(value=.01)])
    assert result['operating_values']['power.1'] == pytest.approx(5, abs=2e-7)
    assert result['sensors'][1]['displacement_body'][1] == pytest.approx(.01, abs=1e-9)
    for name in ('alpha', 'acceleration_sensor.y'):
        with pytest.raises(AnalysisError, match='undefined'):
            solve(configuration, condition, [target(f'sensor("2.{name}")')])
    control = dict(commands={'RY[2]': 2.}, outputs=[dict(actuator='E1', terms=[dict(input='RY[2]', gain=-200)])])
    system, _ = make_system(configuration, condition, 4, gravity=[0, 0, 0], controller=control)
    assert system.base_report()['feedback']['measurements']['RY[2]'] == pytest.approx(2)
    for selected in ('A[2]', 'Ay[2]', 'Ex[2]'):
        bad = deepcopy(control); bad['commands'] = {}
        bad['outputs'][0]['terms'][0]['input'] = selected
        with pytest.raises(AnalysisError, match='undefined'):
            make_system(configuration, condition, 4, gravity=[0, 0, 0], controller=bad)
    assert all(np.array_equal(a[:6], b[:6]) for a, b in zip(original, configuration.records['sensor']))
