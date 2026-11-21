from pathlib import Path
import json
import numpy as np
import pytest
from scipy.optimize import brentq
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.inertia import Motion
from openswing.linear_dynamics import make_system, linearize, eigensystem, solve_modes, euler_matrix
from openswing.ground import body_to_earth
from test_network import model, beam
from test_time_integration import oscillator, rigid_body


def spectrum(configuration, condition=None, *, panels=4, frame='fixed', **kwargs):
    system, _ = make_system(configuration, condition, panels, frame=frame, gravity=[0, 0, 0], **kwargs)
    a, m = linearize(system)
    modes, meta = eigensystem(a, m, time_scale=system.W, count=100)
    return np.array([complex(*mode['eigenvalue']) for mode in modes]), modes, meta, system, a, m


def test_descriptor_reduction_enforces_hidden_constraints_and_left_right_equations():
    # Two constrained masses move together, so only their combined spring mode
    # is finite. The reaction is algebraic and x1=x2 differentiates twice.
    a = np.array([[0, 0, 1, 0, 0], [0, 0, 0, 1, 0],
                  [-18, 7, -.4, 0, 1], [7, -24, 0, -.8, -1], [1, -1, 0, 0, 0]], dtype=float)
    m = np.diag([1., 1., 2., 3., 0.])
    expected = np.roots([5., 1.2, 28.])
    for row, column in [(np.ones(5), np.ones(5)),
                        (np.array([1e-5, 3, 1e5, .003, 2]), np.array([.2, 3, .1, 4, .01]))]:
        aa, mm = row[:, None]*a*column, row[:, None]*m*column
        modes, report = eigensystem(aa, mm, time_scale=3.2, count=10)
        assert report['finite_dimension'] == 2
        assert len(report['right_reduction']) >= 3
        for mode in modes:
            value = complex(*mode['eigenvalue'])
            assert min(abs(value-expected)) < 1e-8
            v, w = mode['right'], mode['left']
            np.testing.assert_allclose(aa@v, value*mm@v, atol=2e-8)
            np.testing.assert_allclose(w.conj()@aa, value*(w.conj()@mm), atol=2e-8)
            assert np.vdot(w, mm@v) == pytest.approx(1, abs=1e-10)
            assert v[0]*column[0] == pytest.approx(v[1]*column[1], abs=1e-10)


def test_underdetermined_pencil_is_not_reported_as_physical_zero_modes():
    with pytest.raises(ValueError, match='underdetermined'):
        eigensystem(np.zeros((2, 2)), np.diag([1., 0.]))


def test_weak_inertia_near_rank_cutoff_requires_refinement_instead_of_losing_modes():
    with pytest.raises(ValueError, match='weak inertia'):
        eigensystem(np.eye(2), np.diag([1., 1e-10]), rank_tolerance=1e-9)
    modes, meta = eigensystem(np.eye(2), np.diag([1., 1e-10]), rank_tolerance=1e-12)
    assert meta['finite_dimension'] == 2
    np.testing.assert_allclose(sorted(complex(*m['eigenvalue']).real for m in modes), [1, 1e10], rtol=1e-10)


def test_shift_and_invert_selects_the_requested_nearby_poles():
    roots = -np.arange(1, 9, dtype=float)
    a = np.diag(roots); m = np.eye(8)
    modes, meta = eigensystem(a, m, count=2, shift=(-4.4, .1), method='shift_invert')
    assert meta['method'] == 'shift_invert'
    np.testing.assert_allclose(sorted(complex(*x['eigenvalue']).real for x in modes), [-5, -4], atol=1e-10)
    assert max(x['left_backward_error'] for x in modes) < 1e-12
    with pytest.raises(ValueError, match='shift is on'):
        eigensystem(a, m, count=2, shift=(-4, 0), method='shift_invert')


@pytest.mark.parametrize('damping', [0., .02, .16])
def test_axial_oscillator_modes_match_exact_under_over_and_undamped_roots(damping):
    values, modes, meta, *_ = spectrum(oscillator(damping))
    exact = np.roots([1., 250*damping, 250.])
    for value in exact:
        assert min(abs(values-value)) < 1e-7
    if damping == 0:
        assert meta['finite_dimension'] == 2
    else:
        # The printed massless/rigid-direction strain-rate equations retain
        # relaxation poles. They are not extra oscillatory spring/mass modes.
        for value in values:
            assert min([*abs(value-exact), abs(value+1/damping)]) < 1e-7
    assert max(m['right_backward_error'] for m in modes) < 1e-10


def test_mixed_time_units_preserve_physical_frequency_and_decay():
    si = oscillator(.02)
    ms = parse_asw(si.dumps().replace('T 1 s', 'T .001 s').replace('9.80665 1.225 340.294',
                    '.00000980665 1225000 .340294').replace('0 0.02', '0 20').replace('2 0.02', '2 20'))
    seconds = spectrum(si)[0]
    milliseconds = spectrum(ms)[0]*1000
    for value in seconds:
        assert min(abs(milliseconds-value)) < 1e-6


def test_uniform_cantilever_bending_frequency_converges_to_continuum_solution():
    source = beam(stiffness='100 0 0 0 0 0').replace('End', 't mg\n0 19.6133\n2 19.6133\nEnd')
    beta = brentq(lambda x: np.cos(x)*np.cosh(x)+1, 1, 2)
    exact = beta**2*np.sqrt(100/(2*2**4))
    errors = []
    for panels in (4, 8, 16):
        values = spectrum(model(source), panels=panels)[0]
        positive = sorted(v.imag for v in values if v.imag > 1e-6)
        errors.append(abs(positive[0]-exact))
        assert max(abs(v.real) for v in values) < 1e-6
    assert errors[1] < .3*errors[0]
    assert errors[2] < .3*errors[1]
    assert errors[-1]/exact < .002


def test_rigid_vacuum_has_twelve_neutral_states_and_no_spurious_finite_constraint_roots():
    values, _, meta, *_ = spectrum(rigid_body(), frame='free')
    assert meta['finite_dimension'] == 12
    assert max(abs(values)) < 1e-7


@pytest.mark.parametrize('axis,expected', [(2, 2j/np.sqrt(3)), (1, 2/np.sqrt(8))])
def test_free_body_modes_recover_gyroscopic_nutation_and_intermediate_axis_instability(axis, expected):
    omega = np.zeros(3); omega[axis] = 2
    values, *_ = spectrum(rigid_body(), frame='free', motion=Motion(rates=omega))
    assert min(abs(values-expected)) < 1e-7
    assert min(abs(values+expected)) < 1e-7


def test_rigid_high_aspect_ratio_wing_retains_unsteady_circulation_decay_modes():
    source = Path('examples/rectangular.asw').read_text()
    source = source[:source.index('t dCLdF1')]+'End\n'
    source = (source.replace('6 0 6 0', '100000 0 100000 0').replace('6 .008', '100000 .008')
              .replace('.008', '0').replace('12 1 12', '200000 1 200000'))
    values, _, meta, system, *_ = spectrum(parse_asw(source), FlightCondition(speed=10, alpha=0, mach=0, stall=False))
    assert meta['finite_dimension'] == system.network.ng
    np.testing.assert_allclose(values, -5, atol=.002)


def test_modal_output_has_correct_complex_constitutive_loads_and_serializes():
    result = solve_modes(oscillator(.02), panels=4, count=2, gravity=[0, 0, 0], matrices=True)
    assert result['vacuum']
    for mode in result['modes']:
        value = complex(*mode['eigenvalue'])
        for section in mode['output']['sections']:
            strain = np.array(section['strain']['real'])+1j*np.array(section['strain']['imag'])
            force = np.array(section['force_local']['real'])+1j*np.array(section['force_local']['imag'])
            # Strain recovery subtracts nearly equal positions at h=1e-5;
            # allow its ~1e-9 relative roundoff in the recovered force.
            assert force[1] == pytest.approx(1000*(1+.02*value)*strain[1], rel=2e-9, abs=1e-9)
        assert mode['output']['geometry'][0]['quads'] == dict(real=[], imag=[])
        assert mode['output']['frame'] is None
        assert mode['right_backward_error'] < 1e-10
    assert len(json.dumps(result, allow_nan=False)) > 100


def test_euler_rate_matrix_matches_independent_rotation_derivative():
    attitude = np.array([22., -31., 42.]); rates = np.array([.4, -.2, .6])
    h = 1e-5
    r = body_to_earth(attitude)
    rd = (body_to_earth(attitude+np.rad2deg(h*rates))-body_to_earth(attitude-np.rad2deg(h*rates)))/(2*h)
    skew = r.T@rd
    actual = np.array([skew[2, 1], skew[0, 2], skew[1, 0]])
    np.testing.assert_allclose(euler_matrix(attitude)@rates, actual, atol=1e-10)


def test_vacuum_bridge_keeps_file_mass_and_rotates_specified_earth_gravity():
    from openswing.bridge import dispatch
    result = dispatch(dict(action='modes', source=oscillator().dumps(), panels=4,
        condition=dict(speed=10, attitude=[25, 12, -5], gravity_magnitude=0),
        modes=dict(vacuum=True, count=2)))
    assert result['base']['mass_properties']['mass'] == pytest.approx(2)
    np.testing.assert_array_equal(result['base']['gravity_body'], [0, 0, 0])
    np.testing.assert_allclose([abs(complex(*m['eigenvalue'])) for m in result['modes']], np.sqrt(250), rtol=1e-9)


def test_coupled_heave_pitch_lag_model_keeps_eight_modes_and_has_growing_pair():
    configuration = parse_asw(Path('examples/heave-pitch.asw').read_text())
    values, modes, meta, *_ = spectrum(configuration, FlightCondition(speed=50, alpha=0, mach=0, stall=False))
    assert meta['finite_dimension'] == 8  # Four elastic states + four circulation states.
    unstable = values[values.real > 1e-5]
    assert len(unstable) == 2
    np.testing.assert_allclose(unstable.real, .77290818, atol=3e-5)
    np.testing.assert_allclose(abs(unstable.imag), 32.44995145, atol=3e-5)
    assert max(m['left_backward_error'] for m in modes) < 1e-9


def test_modal_tangent_rejects_wire_and_sprung_hinge_branch_boundaries():
    from test_joints import linked
    rod = model(beam(stiffness='0 0 0 1000 0 0'),
                'Ground\n1 0 0\nEnd\nStrut\n1 2 0 2 0 0 4 0 0 2000\nEnd\n')
    with pytest.raises(ValueError, match='wire slack/taut transition'):
        spectrum(rod, strut_mode='wire')
    with pytest.raises(ValueError, match='Jangle slope break'):
        spectrum(linked('-10 -20\n0 0\n0 0\n10 10'))
