"""Independent descriptor, mechanical and spatial-gust frequency checks."""
import json
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.frequency_response import harmonic_solve, HarmonicPole, HarmonicInput, solve_frequency_response
from openswing.linear_dynamics import make_system
from openswing.gust import gust_field
from openswing.ground import body_to_earth
from openswing.bridge import run_json
from test_time_integration import oscillator, rigid_body
from test_network import model, beam


def z(value):
    return np.array(value['real'])+1j*np.array(value['imag'])


def powered_oscillator(damping=.02):
    return parse_asw(oscillator(damping).dumps()+'\nEngine\n1 0 1 2 0 2 0 0 1 0 1 0 -1 0 0\nEnd\n')


def response(configuration, frequencies, inputs=None, **kwargs):
    return solve_frequency_response(configuration, FlightCondition(speed=10, alpha=0, mach=0, stall=False),
                                    4, frequencies=frequencies, inputs=inputs, gravity=[0, 0, 0], **kwargs)


def test_full_descriptor_retains_forced_constraint_and_dc_feedthrough_under_scaling():
    # xdot=-2x+3q+u; q=4u. The algebraic input survives at DC and infinity.
    a = np.array([[-2., 3.], [0., -1.]])
    m = np.diag([1., 0.]); b = np.array([[1., 2.], [4., -1.]])
    for w in (0., .01, 2., 1e6):
        exact = np.array([[13/(2+1j*w), -1/(2+1j*w)], [4., -1.]])
        for row, column, time in [(np.ones(2), np.ones(2), 1),
                                  (np.array([1e-7, 2e4]), np.array([.01, 7.]), 60)]:
            x, diagnostic = harmonic_solve(row[:, None]*a*column, row[:, None]*m*column/time,
                                           row[:, None]*b, w*time)
            np.testing.assert_allclose(column[:, None]*x, exact, rtol=3e-15)
            assert max(diagnostic['backward_errors']) < 1e-14


def test_poles_and_free_integrator_have_no_unique_forced_solution():
    for a, m, w in [(np.array([[0., 1.], [-4., 0.]]), np.eye(2), 2.),
                    (np.zeros((1, 1)), np.eye(1), 0.)]:
        with pytest.raises(HarmonicPole):
            harmonic_solve(a, m, np.ones((len(a), 1)), w)


def test_exact_damped_oscillator_displacement_load_strain_and_direct_input():
    progress = []
    frequencies = [0., 1., 10., np.sqrt(250), 50.]
    out = response(powered_oscillator(), frequencies, matrices=True, progress=lambda *x:progress.append(x))
    assert out['converged']
    assert {'base','linearizing','inertia','frequency','reporting'} <= {x[0] for x in progress}
    for sample in out['samples']:
        w = sample['omega']; value = sample['responses'][0]; output = value['output']
        exact = 1/(500*(1+1j*.02*w)-2*w*w)
        assert z(output['nodes'][-1]['displacement'])[1] == pytest.approx(exact, abs=2e-12)
        assert z(output['operating']['power.1']) == pytest.approx(1., abs=2e-12)
        assert z(output['global']['force'])[1] == pytest.approx(1., abs=2e-11)
        for section in output['sections']:
            strain = z(section['strain'])[1]; force = z(section['force_local'])[1]
            assert strain == pytest.approx(exact/2, abs=1e-10)
            assert force == pytest.approx(1000*(1+1j*.02*w)*strain, abs=2e-7)
        k = 1j*w*np.array(out['matrices']['M'])-np.array(out['matrices']['A'])
        np.testing.assert_allclose(k@z(value['state']), z(sample['B'])[:, 0], atol=1e-11)
    assert out['diagnostics']['state_layout']['nodes'] == len(out['base']['nodes'])
    assert len(json.dumps(out, allow_nan=False)) > 100


def test_free_rigid_thrust_recovers_velocity_position_acceleration_and_dc_gap():
    configuration = parse_asw(rigid_body().dumps()+'\nEngine\n1 0 1 0 0 0 0 1 0 0 1 0 -1 0 0\nEnd\n')
    out = response(configuration, [0., .3, 3.], frame='free')
    assert not out['converged']
    assert not out['samples'][0]['converged'] and not out['samples'][0]['responses']
    for sample in out['samples'][1:]:
        w = sample['omega']; output = sample['responses'][0]['output']
        np.testing.assert_allclose(z(output['frame']['velocity_origin_body']), [1/(1j*w), 0, 0], atol=2e-10)
        np.testing.assert_allclose(z(output['frame']['position_earth']), [-1/w**2, 0, 0], atol=2e-10)
        assert z(output['operating']['acceleration.x']) == pytest.approx(1., abs=1e-10)


def test_infinite_span_uniform_gust_matches_empirical_lag_with_rate_feedthrough():
    source = Path('examples/rectangular.asw').read_text().split('t dCLdF1')[0]+'End\n'
    source = (source.replace('6 0 6 0', '100000 0 100000 0').replace('6 .008', '100000 .008')
              .replace('.008', '0').replace('12 1 12', '200000 1 200000'))
    out = response(parse_asw(source), [0., 1., 5., 50.], [dict(kind='gust', wave='uniform')])
    for sample in out['samples']:
        w = sample['omega']; output = sample['responses'][0]['output']
        exact = 2*np.pi/10*(1+1j*w*.1)/(1+1j*w*.2)
        assert z(output['global']['CL']) == pytest.approx(exact, rel=4e-5)
        # Without direct rate-dependent loads this tends to zero at high w.
        assert abs(z(output['global']['CL'])) > .3


@pytest.mark.parametrize('symmetry', ['cosine', 'sine'])
def test_complex_convected_gust_samples_actual_offset_drag_points(symmetry):
    # Purely rigid beam with an offset drag object (no interaction with other source fields); no circulation dynamics.
    points = np.array([[1.2, .6, -.3]])
    attachments = 'Ground\n1 0 0\nEnd\nWeight\n'+''.join(f'1 0 {x} {y} {zz} 0 .4 0\n' for x, y, zz in points)+'End\n'
    configuration = model(beam(stiffness='0 0 0 0 0 0'), attachments)
    out = response(configuration, [.4, 12.], [dict(kind='gust', symmetry=symmetry, span_mode=1)])
    for sample in out['samples']:
        w = sample['omega']; phase = np.exp(-1j*w*points[:, 0]/10)
        parity = (np.cos if symmetry == 'cosine' else np.sin)(np.pi*points[:, 1])
        force = np.zeros((len(points), 3), complex); force[:, 2] = .5*1.225*.4*10*phase*parity
        output = sample['responses'][0]['output']
        np.testing.assert_allclose(z(output['global']['force']), force.sum(axis=0), atol=1e-8)
        np.testing.assert_allclose(z(output['global']['moment']), np.cross(points, force).sum(axis=0), atol=1e-8)


def test_gust_phase_is_covariant_with_earth_pose_and_retains_base_field():
    c = FlightCondition(speed=10, alpha=0, mach=0, attitude=[23, -17, 41], position_earth=[3, 7, -4],
                        gust=dict(type='uniform', velocity=[.1, .2, .3]))
    system, _ = make_system(model(beam(stiffness='0 0 0 0 0 0')), c, 4, gravity=[0, 0, 0])
    R = body_to_earth(c.attitude)
    channel = HarmonicInput(system, dict(kind='gust', direction=R[:, 2].tolist(), span_direction=R[:, 1].tolist(), span_mode=2), 0)
    forcing, profile = channel.at_frequency(12)
    assert profile['spatial_resolution_warning']
    points = np.array([[.3, .7, .1], [-.2, -.4, .8]])
    zero = np.zeros(system.size); fields = []
    for part in (0, 1):
        _, _, options = system.residual(zero, zero, forcing=forcing(part, 1), detail=True)
        cc = options['condition_override']
        value = gust_field(cc.gust).body_velocity(points, cc)-np.array([.1, .2, .3])@R
        fields.append(value)
    exact = np.exp(-1.2j*points[:, 0])*np.cos(2*np.pi*points[:, 1])
    np.testing.assert_allclose(fields[0]+1j*fields[1], exact[:, None]*[0, 0, 1], atol=5e-15)


@pytest.mark.parametrize('frequencies', [[], [1, 1], [2, 1], [-1], [float('nan')]])
def test_invalid_frequency_range_is_rejected(frequencies):
    with pytest.raises(ValueError, match='Frequencies'):
        response(powered_oscillator(), frequencies)


def test_bridge_returns_complex_response_and_rejects_undeclared_input():
    request = dict(action='frequency', source=powered_oscillator().dumps(), panels=4, gravity=[0, 0, 0],
                   condition=dict(speed=10, alpha=0, mach=0), frequency=dict(frequencies=[0., 10.], inputs=['power.1']))
    result = json.loads(run_json(json.dumps(request)))
    assert result['analysis'] == 'frequency_response' and result['converged']
    request['frequency']['inputs'] = ['power.2']
    with pytest.raises(ValueError, match='Undeclared'):
        run_json(json.dumps(request))


def test_transverse_gust_projection_does_not_mutate_aircraft_or_input_arrays():
    c = FlightCondition(speed=10, alpha=4, beta=19, mach=0, attitude=[23, -17, 41])
    system, _ = make_system(model(beam(stiffness='0 0 0 0 0 0')), c, 4, gravity=[0, 0, 0])
    before = system.R0.copy(); direction = np.array([0., 0., 3.])
    channel = HarmonicInput(system, dict(kind='gust', direction=direction, span_mode=1), 0)
    np.testing.assert_array_equal(system.R0, before)
    np.testing.assert_array_equal(direction, [0, 0, 3])
    assert np.dot(channel.ell, channel.velocity) == pytest.approx(0., abs=1e-14)


def test_zero_frequency_flap_response_matches_loaded_steady_difference():
    from dataclasses import replace
    from openswing.network import solve_static
    configuration = parse_asw(Path('examples/rectangular.asw').read_text())
    c = FlightCondition(speed=10, alpha=3, mach=0, stall=False)
    out = solve_frequency_response(configuration, c, 4, frequencies=[0.], inputs=['control.1'], gravity=[0, 0, 0])
    states = [solve_static(configuration, replace(c, controls={1:sign*.001}), 4, gravity=[0, 0, 0]) for sign in (1, -1)]
    for key in ('force', 'moment', 'CL', 'Cl', 'Cm'):
        expected = (np.asarray(states[0][key])-np.asarray(states[1][key]))/.002
        np.testing.assert_allclose(z(out['samples'][0]['responses'][0]['output']['global'][key]), expected, atol=2e-7)


def test_gust_schema_rejects_unresolved_and_zero_inputs():
    system, _ = make_system(model(beam(stiffness='0 0 0 0 0 0')), FlightCondition(speed=10), 4, gravity=[0, 0, 0])
    for spec in [dict(kind='gust', span_mode=-1), dict(kind='gust', span_mode=1.5),
                 dict(kind='gust', symmetry='sine'), dict(kind='gust', span_reference=0),
                 dict(kind='gust', direction=[0, 0, 0]), dict(kind='gust', wave='unknown'),
                 dict(kind='gust', unnoticed_parameter=3), 'control.bad']:
        with pytest.raises(ValueError):
            HarmonicInput(system, spec, 0)
