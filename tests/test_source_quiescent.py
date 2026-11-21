"""Independent stationary source-fluid inertia and scalar modal oracles.

The endpoint matrix follows rendered unsteady Eqs.41--44. Its local form is
an explicit sum of two rank-one matrices, independent of production load
helpers. No nonlinear-fluid or aircraft modal-reproduction claim is made.
"""
import json
import numpy as np
import pytest

from openswing.aero import AnalysisError
from openswing.asw import AswError, parse_asw
from openswing.inertia import Motion
from openswing.source_dynamics import SourceDynamicNetwork
from openswing.source_quiescent import FLUID_POLICY, SourceQuiescentNetwork, source_apparent_wrench


RHO = 1.3


def cross_matrix(v):
    x, y, z = v
    return np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])


def rotation(v):
    angle = np.linalg.norm(v)
    if angle == 0:
        return np.eye(3)
    k = cross_matrix(np.asarray(v)/angle)
    return np.eye(3)+np.sin(angle)*k+(1-np.cos(angle))*k@k


def endpoint_matrix(frame, chord, xax, density=RHO):
    """Independent local rank-two expression, then rigid body-axis rotation."""
    mu = np.pi*density*chord**2/4
    pitch = mu*chord**2/32
    arm = (.5-xax)*chord
    v = np.array([0., 0., 1., 0., -arm, 0.])
    p = np.array([0., 0., 0., 0., 1., 0.])
    local = mu*np.outer(v, v)+pitch*np.outer(p, p)
    transform = np.zeros((6, 6)); transform[:3, :3] = frame; transform[3:, 3:] = frame
    return transform@local@transform.T


@pytest.mark.parametrize('xax', [.2, .5, 1.1])
def test_complete_endpoint_matrix_has_correct_offset_sign_pitch_and_rank(xax):
    r = rotation([.35, -.2, .45]); chord = 1.2
    basis = np.eye(6)
    force, moment = source_apparent_wrench(np.repeat(r[None], 6, axis=0),
        np.full(6, chord), np.full(6, xax), RHO, basis[:, :3], basis[:, 3:])
    measured = -np.c_[force, moment].T
    expected = endpoint_matrix(r, chord, xax)
    np.testing.assert_allclose(measured, expected, rtol=3e-14, atol=3e-14)
    np.testing.assert_allclose(measured, measured.T, atol=3e-14)
    assert np.linalg.matrix_rank(measured, tol=1e-12) == 2
    assert np.min(np.linalg.eigvalsh(measured)) > -3e-14
    np.testing.assert_allclose(measured@np.r_[r[:, 0], [0., 0., 0.]], 0., atol=3e-14)
    np.testing.assert_allclose(measured@np.r_[r[:, 1], [0., 0., 0.]], 0., atol=3e-14)


def test_zero_chord_adds_exactly_no_fluid_inertia():
    r = rotation([.2, .1, -.3]); a = np.array([[.4, -.2, .3]])
    f, m = source_apparent_wrench(r[None], np.array([0.]), np.array([-.3]), RHO, a, -a)
    np.testing.assert_array_equal(f, np.zeros((1, 3)))
    np.testing.assert_array_equal(m, np.zeros((1, 3)))


def model_text(*, chord_left=.8, chord_right=1.2):
    return ('Name\nIndependent source still-air fixture\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\n'
            'Constant\n10 1.225 340\nEnd\nReference\n4 .2 4\n.2 -.3 .1\nEnd\nGround\n1 1 0\nEnd\n'
            'Weight\n1 3 .2 2 -.1 7 0 0 0 0 0 2 3 4 .1 -.2 .3\nEnd\n'
            'Beam 1\nTapered local airfoil chord\nt x y z chord Xax\n'
            f'1 0 0 0 {chord_left} .1\n5 0 4 0 {chord_right} .5\n'
            't EIcc GJ EInn EIcs EIcn EIsn EA GKc GKn Cea Nea Cta Nta\n'
            '1 100 75 150 8 -13 9 800 300 400 -.1 .07 .3 -.2\n'
            '5 140 100 160 6 2 5 1600 900 1000 .2 -.03 -.1 .4\n'
            't mg mgcc mgnn Ccg Ncg Dmg Dmgcc Dmgnn DCcg DNcg\n'
            '1 20 2 3 .1 -.1 4 .2 .3 -.05 .1\n5 24 3 4 -.05 .15 6 .4 .5 .1 -.1\nEnd\n')


def network(*, wet=True, density=RHO, gravity=(0., 0., 0.), text=None, **kwargs):
    model = parse_asw(model_text() if text is None else text, beam_interpolation='drela-segspl-v1')
    cls = SourceQuiescentNetwork if wet else SourceDynamicNetwork
    options = dict(quiescent_density=density) if wet else {}
    options.update(kwargs)
    return cls(model, {'default': 4, 'beams': {'1': {'nodes': [1., 2., 3., 4., 5.]}}}, None, gravity, [], **options)


def state(n, curved=True):
    x = np.zeros(n.size)
    q = np.zeros((5, 3))
    r = np.c_[np.zeros(5), np.arange(5), np.zeros(5)]
    if curved:
        q = np.array([[.1, -.2, .15], [-.2, .1, -.1], [.05, .2, -.15], [.15, -.1, .2], [-.1, .05, .1]])
        r += np.c_[.02*np.arange(5)**2, .01*np.arange(5)**2, -.015*np.arange(5)**2]
    x[:6*n.nn].reshape(-1, 6)[:, :3] = (r-n.rj)/n.L
    x[:6*n.nn].reshape(-1, 6)[:, 3:] = q
    return x, r, np.array([rotation(v) for v in q])


def evaluate(n, x, acceleration, angular):
    zero = np.zeros((n.nn, 3))
    return n.residual(x, detail=True, elastic_motion=(zero, zero, acceleration, angular))


def properties(t):
    return .8+.1*(t-1), .1+.1*(t-1)


def test_complete_interval_twelve_by_twelve_blocks_use_completed_endpoint_products():
    wet, dry = network(), network(wet=False)
    x, _, q = state(wet)
    wa = endpoint_matrix(q[0], *properties(1.))
    wb = endpoint_matrix(q[1], *properties(2.))
    expected = np.block([[wa, wb], [wa, wb]])/4
    measured = np.zeros((12, 12))
    for col in range(12):
        a, alpha = np.zeros((5, 3)), np.zeros((5, 3))
        node, direction = divmod(col, 6)
        (a if direction < 3 else alpha)[node, direction % 3] = 1.
        _, fluid = evaluate(wet, x, a, alpha); _, vacuum = evaluate(dry, x, a, alpha)
        force = fluid['element_forces'][0]-vacuum['element_forces'][0]
        moment = fluid['element_moments'][0]-vacuum['element_moments'][0]
        measured[:, col] = -np.r_[force[0], moment[0], force[1], moment[1]]
    np.testing.assert_allclose(measured, expected, rtol=2e-12, atol=3e-13)
    assert np.linalg.norm(measured-measured.T) > .05
    np.testing.assert_allclose(measured[:6], measured[6:], atol=2e-14)


def test_tapered_rotated_transfer_conserves_interval_and_global_wrenches():
    wet, dry = network(), network(wet=False)
    x, r, q = state(wet)
    acceleration = np.array([[.2, -.1, .3], [-.1, .3, .2], [.4, -.2, -.1], [.1, .2, -.3], [-.2, .1, .4]])
    angular = np.array([[.1, .3, -.2], [.2, -.1, .15], [-.1, .2, .3], [.3, -.2, .1], [-.2, -.1, .2]])
    rw, dw = evaluate(wet, x, acceleration, angular); rd, dd = evaluate(dry, x, acceleration, angular)
    expected_force, expected_moment = np.zeros((5, 3)), np.zeros((5, 3))
    intervals = []
    for j in range(4):
        interval = np.zeros(6)
        for i in (j, j+1):
            interval -= endpoint_matrix(q[i], *properties(i+1))@np.r_[acceleration[i], angular[i]]/2
        expected_force[j:j+2] += interval[:3]/2
        expected_moment[j:j+2] += interval[3:]/2
        intervals.append(interval)
        np.testing.assert_allclose(dw['element_forces'][j]-dd['element_forces'][j], np.tile(interval[:3]/2, (2, 1)), atol=3e-14)
        np.testing.assert_allclose(dw['element_moments'][j]-dd['element_moments'][j], np.tile(interval[3:]/2, (2, 1)), atol=3e-14)
    measured_force, measured_moment = dw['force']-dd['force'], dw['moment']-dd['moment']
    np.testing.assert_allclose(measured_force, expected_force, rtol=2e-13, atol=3e-14)
    np.testing.assert_allclose(measured_moment, expected_moment, rtol=2e-13, atol=3e-14)
    np.testing.assert_array_equal(rw[:6*wet.ne], rd[:6*dry.ne])
    np.testing.assert_array_equal(dw['distributed_mass_force'], dd['distributed_mass_force'])
    for a, b in zip(wet.mass_cached[:2]+wet.mass_cached[3:], dry.mass_cached[:2]+dry.mass_cached[3:]):
        np.testing.assert_array_equal(a, b)
    intervals = np.array(intervals)
    for origin in (np.zeros(3), np.array([.5, -.4, .2])):
        actual = (np.cross(r-origin, measured_force)+measured_moment).sum(axis=0)
        expected = (np.cross((r[:-1]+r[1:])/2-origin, intervals[:, :3])+intervals[:, 3:]).sum(axis=0)
        np.testing.assert_allclose(actual, expected, rtol=2e-13, atol=5e-14)
    # Apparent inertia must not enter ordinary real-mass/CG bookkeeping.
    assert len(dw['masses']) == len(dd['masses'])
    for a, b in zip(dw['masses'], dd['masses']):
        for field in ('mass', 'position', 'inertia', 'spin'):
            np.testing.assert_array_equal(a[field], b[field])


def test_no_fluid_eq80_rotary_correction_is_added():
    wet, dry = network(), network(wet=False)
    x, _, _ = state(wet, curved=False)
    zero, angular = np.zeros((5, 3)), np.tile([.3, 0., -.2], (5, 1))
    rw, dw = evaluate(wet, x, zero, angular); rd, dd = evaluate(dry, x, zero, angular)
    # Only c and n angular accelerations: no local normal acceleration or pitch.
    np.testing.assert_array_equal(rw, rd)
    for key in ('force', 'moment', 'element_forces', 'element_moments'):
        np.testing.assert_array_equal(dw[key], dd[key])


def test_stationary_fluid_does_not_change_gravity_or_static_equilibrium():
    wet, dry = network(gravity=(.2, -.4, -9.81)), network(wet=False, gravity=(.2, -.4, -9.81))
    x, *_ = state(wet)
    rw, dw = wet.residual(x, detail=True); rd, dd = dry.residual(x, detail=True)
    np.testing.assert_array_equal(rw, rd)
    for key in ('force', 'moment', 'element_forces', 'element_moments'):
        np.testing.assert_array_equal(dw[key], dd[key])
    assert wet.ng == dry.ng == 0 and dw['aero'] is None


@pytest.mark.parametrize('curved', [False, True])
@pytest.mark.parametrize('reference', [[0., 0., 0.], [.7, -.3, .2]])
def test_rigid_acceleration_report_matches_actual_six_nodal_impulses(curved, reference):
    """A reported matrix must be the rigid projection of the physical loads.

    Varying chord/Xax and curved endpoint frames deliberately expose the
    nonsymmetric source-box rule. Do not replace it by a symmetric mass tensor.
    """
    wet, dry = network(), network(wet=False)
    x, r, q = state(wet, curved=curved)
    meshes = wet.deformed_meshes(r, q, wet.geometry(r, q))
    reference = np.array(reference)
    report = wet.rigid_acceleration_report(meshes, reference)
    matrix = np.asarray(report['matrix'])
    assert report['geometry'] == 'provided endpoint geometry'
    assert report['maximum_antisymmetric_entry'] > 1e-3
    for column, impulse in enumerate(np.eye(6)):
        angular = np.broadcast_to(impulse[3:], r.shape)
        acceleration = impulse[:3]+np.cross(angular, r-reference)
        _, fluid = evaluate(wet, x, acceleration, angular)
        _, vacuum = evaluate(dry, x, acceleration, angular)
        f = fluid['force']-vacuum['force']
        m = fluid['moment']-vacuum['moment']
        reaction = np.r_[f.sum(axis=0), (m+np.cross(r-reference, f)).sum(axis=0)]
        np.testing.assert_allclose(reaction, -matrix[:, column], rtol=2e-12, atol=3e-12)


def test_fluid_report_uses_supplied_deformed_endpoints_without_claiming_symmetric_tensor():
    from openswing.quiescent import report
    wet = network()
    _, r, q = state(wet)
    meshes = wet.deformed_meshes(r, q, wet.geometry(r, q))
    actual = report(wet, meshes)
    expected = wet.rigid_acceleration_report(meshes)
    assert actual['rigid_acceleration_response'] == expected
    assert actual['apparent_properties']['spatial_matrix'] is None
    assert actual['apparent_properties']['mass_tensor'] is None
    assert actual['apparent_properties']['inertia_reference'] is None
    assert not np.allclose(expected['matrix'], wet.rigid_acceleration_report()['matrix'])


@pytest.mark.parametrize('density', [0., -1., np.nan, np.inf, True])
def test_source_fluid_density_must_be_positive_finite(density):
    with pytest.raises(AnalysisError, match='positive finite'):
        network(density=density)


@pytest.mark.parametrize('chord', [-.1, np.nan, np.inf])
def test_invalid_chord_table_is_rejected(chord):
    with pytest.raises((AnalysisError, AswError, ValueError), match='finite|nonnegative|non-finite|Non-finite'):
        network(text=model_text(chord_left=chord))


def test_positive_chord_knots_with_negative_inward_sample_are_rejected():
    lines = model_text().splitlines()
    at = lines.index('t x y z chord Xax')
    lines[at] = 't x y z Xax'
    for j in (at+1, at+2):
        parts = lines[j].split(); del parts[4]; lines[j] = ' '.join(parts)
    # The three-point endpoint rule gives (t-2)^2-.5, negative at t=2.
    lines[-1:-1] = ['t chord', '1 .5', '3 .5', '5 8.5']
    with pytest.raises(AnalysisError, match='nonnegative.*endpoint chord'):
        network(text='\n'.join(lines)+'\n')


def test_nonfinite_axis_fraction_is_rejected():
    text = model_text().replace('1 0 0 0 0.8 .1', '1 0 0 0 0.8 nan')
    with pytest.raises((AnalysisError, AswError, ValueError), match='finite|non-finite|Non-finite'):
        network(text=text)


def test_chord_and_axis_jumps_preserve_inward_endpoint_samples():
    lines = model_text().splitlines(); at = lines.index('t x y z chord Xax')
    lines[at] = 't x y z'
    for j in (at+1, at+2):
        lines[j] = ' '.join(lines[j].split()[:4])
    lines[-1:-1] = ['t chord Xax', '1 .8 .1', '3 1.0 .3', '3 .5 .7', '5 .7 .9']
    n = network(text='\n'.join(lines)+'\n')
    report = n.fluid_report()['apparent_properties']
    assert report['spatial_matrix'] is None
    expected = {0: (np.array([.8, .9, .5, .6]), np.array([.1, .2, .7, .8])),
                1: (np.array([.9, 1., .6, .7]), np.array([.2, .3, .8, .9]))}
    for sample in report['endpoint_coefficients']:
        c, x = expected[sample['end']]
        mu = RHO*np.pi*c*c/4
        np.testing.assert_allclose(sample['normal_mass_per_length'], mu, atol=3e-15)
        np.testing.assert_allclose(sample['midchord_arm'], (.5-x)*c, atol=3e-15)
        np.testing.assert_allclose(sample['span_pitch_inertia_per_length'], mu*c*c/32, atol=3e-15)


def test_vacuum_density_and_operator_saved_identities_cannot_be_mixed():
    from openswing.equilibrium_state import capture, identity, validate
    wet, dry, other = network(), network(wet=False), network(density=RHO+.1)
    saved = capture(wet, np.zeros(wet.size))
    assert identity(wet)['structural_operator'] == FLUID_POLICY
    assert saved['identity']['quiescent_density'] == saved['launch']['quiescent_density'] == RHO
    assert 'quiescent_density' not in identity(dry)
    validate(wet, saved)
    for wrong in (dry, other):
        with pytest.raises(AnalysisError, match='does not match'):
            validate(wrong, saved)


def test_nonzero_prescribed_frame_motion_remains_rejected():
    with pytest.raises(AnalysisError, match='stationary|fixed|zero prescribed'):
        network(motion=Motion(rates=[0., .01, 0.]))


def scalar_text(kind):
    # Midchord axis isolates shear and torsion for exact scalar eigenvalues.
    gj, gkn = (5., 0.) if kind == 'torsion' else (0., 20.)
    mu, icc, inn = (0., .02, .03) if kind == 'torsion' else (.4, 0., 0.)
    return ('Name\nIndependent still-air scalar oracle\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\n'
            'Constant\n10 1.225 340\nEnd\nReference\n4 1.2 4\nEnd\nGround\n1 1 0\nEnd\n'
            'Beam 1\nScalar shear or torsion\nt x y z chord Xax\n1 0 0 0 1.2 .5\n5 0 4 0 1.2 .5\n'
            't EIcc GJ EInn EA GKc GKn mg mgcc mgnn\n'
            +''.join(f'{t} 0 {gj} 0 0 0 {gkn} {10*mu} {10*icc} {10*inn}\n' for t in (1, 5))+'End\n')


@pytest.mark.parametrize('kind', ['torsion', 'shear'])
def test_scalar_still_air_complete_spectrum_and_refinement(kind):
    from scipy.optimize import linear_sum_assignment
    from openswing.linear_dynamics import make_system, linearize, eigensystem
    mu_a = np.pi*RHO*1.2**2/4; pitch_a = mu_a*1.2**2/32
    stiffness, real_density, added_density = (5., .05, pitch_a) if kind == 'torsion' else (20., .4, mu_a)
    errors = []
    for count in (4, 8):
        h = 4/count
        omega = 2*np.sqrt(stiffness/(real_density+added_density))/h*np.tan((2*np.arange(1, count+1)-1)*np.pi/(4*count))
        expected = np.r_[1j*omega, -1j*omega]
        model = parse_asw(scalar_text(kind), beam_interpolation='drela-segspl-v1')
        panels = {'default': count, 'beams': {'1': {'nodes': np.linspace(1., 5., count+1).tolist()}}}
        print('SOURCE_FLUID_START '+json.dumps(dict(kind=kind, intervals=count)), flush=True)
        system, _ = make_system(model, panels=panels, frame='fixed', gravity=[0., 0., 0.],
                                quiescent_density=RHO, structural_operator=FLUID_POLICY)
        assert type(system.network) is SourceQuiescentNetwork and system.network.ng == 0
        a, m = linearize(system, sparse=True)
        modes, meta = eigensystem(a.toarray(), m.toarray(), time_scale=system.W, count=2*count, method='dense')
        actual = np.array([complex(*v['eigenvalue']) for v in modes])
        assert meta['finite_dimension'] == len(actual) == 2*count
        rows, cols = linear_sum_assignment(abs(actual[:, None]-expected[None, :]))
        error = abs(actual[rows]-expected[cols])/abs(expected[cols])
        backward = max(max(v['right_backward_error'], v['left_backward_error']) for v in modes)
        assert max(error) < 2e-8 and backward < 1e-10
        positive = np.sort(actual.imag[actual.imag > 0.])
        vacuum_omega = 2*np.sqrt(stiffness/real_density)/h*np.tan((2*np.arange(1, count+1)-1)*np.pi/(4*count))
        np.testing.assert_allclose(positive/vacuum_omega, np.sqrt(real_density/(real_density+added_density)), rtol=2e-8)
        continuum = np.pi/8*np.sqrt(stiffness/(real_density+added_density))
        errors.append(positive[0]/continuum-1)
        print('SOURCE_FLUID_SPECTRUM '+json.dumps(dict(kind=kind, intervals=count, finite_dimension=2*count,
            maximum_relative_pole_error=float(max(error)), maximum_backward_error=float(backward),
            first_frequency_continuum_relative_error=float(errors[-1]))), flush=True)
    assert 0 < errors[1] < errors[0] and .20 < errors[1]/errors[0] < .26
    assert errors[1] < .0033
