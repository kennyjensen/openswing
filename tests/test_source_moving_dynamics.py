"""Independent moving-frame, real-mass source-discretization checks.

The fixture is shared with the fixed-source tests, but the expected wrench
below is derived directly from inertial transport. It does not call production
LocalMotion, inertial_wrench, or source endpoint helpers. Angular acceleration
includes Omega cross omega: the Earth derivative of the absolute angular
velocity, explicitly qualifying the omitted term in printed unsteady Eq.40.
"""
import numpy as np
import pytest

from openswing.aero import AnalysisError, FlightCondition
from openswing.asw import parse_asw
from openswing.inertia import Motion
from openswing.source_dynamics import (
    DYNAMIC_POLICY, MOVING_POLICY, SourceDynamicNetwork, SourceMovingNetwork,
)
from test_source_dynamic_inertia import (
    T, POINT_ARM, POINT_J, POINT_MASS, properties, rotation, source, state,
)


FRAME_OMEGA = np.array([.41, -.28, .33])
FRAME_ALPHA = np.array([-.17, .23, .12])
FRAME_ACCEL = np.array([.32, -.19, .27])
ACCEL_REFERENCE = np.array([-.3, .25, .15])
POINT_SPIN = np.array([.06, -.04, .02])


def fixture_text(*, varying=True, kind='dual', point=True, damping=False,
                 reference=ACCEL_REFERENCE):
    text = source(varying=varying, kind=kind, point=point)
    text = text.replace('4 .2 4\n.4 -.3 .2\nEnd',
        '4 .2 4\n.4 -.3 .2\n'+' '.join(map(str, reference))+'\nEnd')
    if point:
        text = text.replace('7 0 0 0 0 0 2 3 4 .1 -.2 .3',
                            '7 0 0 .6 -.4 .2 2 3 4 .1 -.2 .3')
    if damping:
        text = text[:-4]+'t tdeps tdgam\n1 .013 .021\n5 .037 .029\nEnd\n'
    return text


def network(*, cls=SourceMovingNetwork, text=None, motion=None,
            gravity=(.2, -.4, -9.), **kwargs):
    model = parse_asw(fixture_text() if text is None else text,
                      beam_interpolation='drela-segspl-v1')
    return cls(model, {'default': 4, 'beams': {'1': {'nodes': T.tolist()}}},
               None, gravity, [], motion=motion, **kwargs)


def fields():
    # Fixed nonsymmetric values, with nonparallel frame and local rotation.
    return tuple(np.array(v) for v in (
        [[.2, -.3, .1], [-.1, .4, .2], [.3, .2, -.4], [.1, -.2, .3], [-.3, .1, .2]],
        [[-.2, .1, .3], [.3, -.1, .2], [.1, .4, -.2], [-.3, .2, .1], [.2, -.4, .3]],
        [[.1, .2, -.3], [.2, -.4, .1], [-.3, .1, .2], [.4, .2, -.1], [.2, -.3, .4]],
        [[.3, -.2, .1], [-.2, .1, .4], [.2, .3, -.1], [.1, -.4, .2], [-.1, .2, .3]],
    ))


def evaluate(n, x, values, motion=None):
    return n.residual(x, detail=True, elastic_motion=values,
                      circulation_rate=np.empty(0), motion_override=motion)


def material_wrench(mu, position, offset, inertia, velocity, omega, accel, alpha,
                    frame, gravity, reference, spin=None, *, omit_transport=False):
    """Completed endpoint density, before any interval averaging.

    frame.acceleration is absolute acceleration at Reference row 3. Relative
    velocity/acceleration and omega derivatives use moving body components.
    """
    delta = position+offset-reference
    acg = (frame.acceleration+np.cross(frame.angular_acceleration, delta)
           +np.cross(frame.rates, np.cross(frame.rates, delta))
           +accel+np.cross(alpha, offset)+np.cross(omega, np.cross(omega, offset))
           +2*np.cross(frame.rates, velocity+np.cross(omega, offset)))
    absolute_omega = frame.rates+omega
    absolute_alpha = frame.angular_acceleration+alpha
    if not omit_transport:
        absolute_alpha = absolute_alpha+np.cross(frame.rates, omega)
    f = mu*(gravity-acg)
    momentum = inertia@absolute_omega+(np.zeros(3) if spin is None else spin)
    m = np.cross(offset, f)-inertia@absolute_alpha-np.cross(absolute_omega, momentum)
    return f, m


def endpoint_oracle(r, q, values, frame, gravity, *, varying=True, kind='dual',
                    point=True, reference=ACCEL_REFERENCE, omit_transport=False):
    velocity, omega, accel, alpha = values
    force, moment = np.zeros_like(r), np.zeros_like(r)
    ef, em = np.zeros((4, 2, 3)), np.zeros((4, 2, 3))
    for j in range(4):
        h = T[j+1]-T[j]
        for i in (j, j+1):
            for mu, arm, icc, inn in properties(T[i], varying, kind):
                offset = q[i]@arm
                # Eq.80 real-mass finite-segment term appears exactly once.
                tensor = q[i]@np.diag([icc+mu*h*h/12, icc+inn, inn+mu*h*h/12])@q[i].T
                f, m = material_wrench(mu, r[i], offset, tensor, velocity[i], omega[i],
                    accel[i], alpha[i], frame, gravity, reference, omit_transport=omit_transport)
                ef[j] += h*f/4
                em[j] += h*m/4
        force[j:j+2] += ef[j]
        moment[j:j+2] += em[j]
    if point:
        i = 2
        f, m = material_wrench(POINT_MASS, r[i], q[i]@POINT_ARM, q[i]@POINT_J@q[i].T,
            velocity[i], omega[i], accel[i], alpha[i], frame, gravity, reference,
            q[i]@POINT_SPIN, omit_transport=omit_transport)
        force[i] += f
        moment[i] += m
    return force, moment, ef, em


@pytest.mark.parametrize('varying', [False, True])
def test_nonparallel_moving_frame_matches_independent_completed_endpoint_wrenches(varying):
    frame = Motion(FRAME_OMEGA, FRAME_ACCEL, FRAME_ALPHA)
    gravity = np.array([.2, -.4, -9.])
    n = network(text=fixture_text(varying=varying), motion=frame, gravity=gravity)
    x, r, q = state(n, curved=True)
    values = fields()
    residual, data = evaluate(n, x, values)
    expected = endpoint_oracle(r, q, values, frame, gravity, varying=varying)
    for key, want in zip(('force', 'moment', 'element_forces', 'element_moments'), expected):
        np.testing.assert_allclose(data[key], want, rtol=4e-14, atol=1e-13)
    np.testing.assert_array_equal(data['element_forces'][:, 0], data['element_forces'][:, 1])
    np.testing.assert_array_equal(data['element_moments'][:, 0], data['element_moments'][:, 1])
    # At this synthetic state all internal resultants/reactions are zero, so
    # these are direct physical force/moment rows, not only report channels.
    start = 6*n.ne
    np.testing.assert_allclose(residual[start:start+3*n.nn].reshape(-1, 3)*n.F,
                               expected[0], rtol=4e-14, atol=1e-13)
    np.testing.assert_allclose(residual[start+3*n.nn:start+6*n.nn].reshape(-1, 3)*n.F*n.L,
                               expected[1], rtol=4e-14, atol=1e-13)
    for origin in (np.zeros(3), np.array([.4, -.3, .2]), np.array([-1., .6, .8])):
        got = np.sum(data['moment']+np.cross(r-origin, data['force']), axis=0)
        want = np.sum(expected[1]+np.cross(r-origin, expected[0]), axis=0)
        np.testing.assert_allclose(got, want, rtol=4e-14, atol=2e-13)


def test_zero_linear_mass_still_requires_omega_cross_local_omega_in_angular_acceleration():
    frame = Motion(FRAME_OMEGA)
    n = network(text=fixture_text(kind='torsion', point=False), motion=frame, gravity=(0., 0., 0.))
    x, r, q = state(n, curved=True)
    zero = np.zeros_like(r)
    values = (zero, fields()[1], zero, zero)
    _, data = evaluate(n, x, values)
    expected = endpoint_oracle(r, q, values, frame, zero[0], kind='torsion', point=False)
    omitted = endpoint_oracle(r, q, values, frame, zero[0], kind='torsion', point=False,
                              omit_transport=True)
    np.testing.assert_array_equal(data['force'], zero)
    np.testing.assert_allclose(data['moment'], expected[1], rtol=4e-14, atol=2e-14)
    assert np.linalg.norm(expected[1]-omitted[1]) > .01


def test_uniform_rotating_rigid_segment_matches_whole_body_wrench_and_single_eq80_term():
    frame = Motion(FRAME_OMEGA, FRAME_ACCEL, FRAME_ALPHA)
    gravity = np.array([.2, -.4, -9.])
    n = network(text=fixture_text(varying=False), motion=frame, gravity=gravity)
    x, r, rotations = state(n, rigid=True)
    q = rotations[0]
    omega, alpha, a0, u0 = map(np.array, ([.3, -.4, .2], [-.2, .3, .1], [.1, .4, -.3], [.7, -.2, .3]))
    values = (u0+np.cross(omega, r), np.broadcast_to(omega, r.shape),
              a0+np.cross(alpha, r)+np.cross(omega, np.cross(omega, r)), np.broadcast_to(alpha, r.shape))
    _, data = evaluate(n, x, values)
    entries = []
    for mu, arm, icc, inn in properties(1., False):
        center = (r[0]+r[-1])/2+q@arm
        tensor = q@np.diag([4*icc+mu*4**3/12, 4*(icc+inn), 4*inn+mu*4**3/12])@q.T
        entries.append((4*mu, center, tensor, np.zeros(3)))
    entries.append((POINT_MASS, r[2]+q@POINT_ARM, q@POINT_J@q.T, q@POINT_SPIN))
    force, moment = np.zeros(3), np.zeros(3)
    for mass, center, tensor, spin in entries:
        # Independent whole-object mass/inertia, not a repeat of nodal sums.
        f, m = material_wrench(mass, center, np.zeros(3), tensor,
            u0+np.cross(omega, center), omega,
            a0+np.cross(alpha, center)+np.cross(omega, np.cross(omega, center)), alpha,
            frame, gravity, ACCEL_REFERENCE, spin)
        force += f
        moment += m+np.cross(center, f)
    np.testing.assert_allclose(data['force'].sum(axis=0), force, rtol=4e-14, atol=2e-13)
    np.testing.assert_allclose(np.sum(data['moment']+np.cross(r, data['force']), axis=0),
                               moment, rtol=4e-14, atol=3e-13)


def test_acceleration_reference_change_preserves_physical_wrenches():
    delta = np.array([.7, -.2, .5])
    original = Motion(FRAME_OMEGA, FRAME_ACCEL, FRAME_ALPHA)
    shifted = Motion(FRAME_OMEGA, FRAME_ACCEL+np.cross(FRAME_ALPHA, delta)
                     +np.cross(FRAME_OMEGA, np.cross(FRAME_OMEGA, delta)), FRAME_ALPHA)
    a = network(motion=original)
    b = network(text=fixture_text(reference=ACCEL_REFERENCE+delta), motion=shifted)
    x, _, _ = state(a, curved=True)
    ra, da = evaluate(a, x, fields())
    rb, db = evaluate(b, x, fields())
    np.testing.assert_allclose(ra, rb, rtol=4e-14, atol=2e-14)
    for key in ('force', 'moment', 'element_forces', 'element_moments'):
        np.testing.assert_allclose(da[key], db[key], rtol=4e-14, atol=5e-14)


def test_constructor_and_residual_frame_motion_have_identical_physical_fields():
    frame = Motion(FRAME_OMEGA, FRAME_ACCEL, FRAME_ALPHA)
    a, b = network(motion=frame), network()
    x, _, _ = state(a, curved=True)
    ra, da = evaluate(a, x, fields())
    rb, db = evaluate(b, x, fields(), frame)
    np.testing.assert_array_equal(ra, rb)
    for key in ('force', 'moment', 'element_forces', 'element_moments'):
        np.testing.assert_array_equal(da[key], db[key])


@pytest.mark.parametrize('damping', [False, True])
def test_zero_frame_is_bitwise_identical_to_existing_fixed_source_policy(damping):
    text = fixture_text(damping=damping)
    moving, fixed = network(text=text), network(text=text, cls=SourceDynamicNetwork)
    x, _, _ = state(moving, curved=True)
    rm, dm = evaluate(moving, x, fields())
    rf, df = evaluate(fixed, x, fields())
    np.testing.assert_array_equal(rm, rf)
    for key in ('force', 'moment', 'element_forces', 'element_moments', 'strain_rate', 'mechanical_strain'):
        np.testing.assert_array_equal(dm[key], df[key])
    assert moving.structural_operator == MOVING_POLICY == 'drela-moving-vacuum-v1'
    assert fixed.structural_operator == DYNAMIC_POLICY == 'drela-fixed-vacuum-v1'


@pytest.mark.parametrize('field', ['rates', 'acceleration', 'angular_acceleration'])
def test_fixed_source_guards_remain_active_while_new_policy_accepts_frame_motion(field):
    motion = Motion(**{field: [.1, -.2, .3]})
    with pytest.raises(AnalysisError, match='fixed|stationary'):
        network(cls=SourceDynamicNetwork, motion=motion)
    fixed = network(cls=SourceDynamicNetwork)
    x, _, _ = state(fixed)
    with pytest.raises(AnalysisError, match='fixed|stationary'):
        evaluate(fixed, x, fields(), motion)
    assert np.all(np.isfinite(evaluate(network(motion=motion), x, fields())[0]))


@pytest.mark.parametrize('option', ['allow_signed_point_weights', 'allow_signed_distributed_weights', 'quiescent_density'])
def test_moving_vacuum_does_not_accept_signed_mass_or_apparent_fluid(option):
    with pytest.raises((AnalysisError, ValueError), match='signed|nonnegative|quiescent|fluid'):
        network(**{option: 1.2 if option == 'quiescent_density' else True})


def test_moving_policy_still_rejects_airflow():
    model = parse_asw(fixture_text(), beam_interpolation='drela-segspl-v1')
    with pytest.raises(AnalysisError, match='airflow|vacuum'):
        SourceMovingNetwork(model, 4, FlightCondition(speed=1), [0, 0, 0], [])


def test_free_frame_factory_recovers_gravity_and_full_point_spatial_mass_from_physical_rows():
    from openswing.linear_dynamics import make_system
    text = ('Name\nRigid moving source fixture\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\n'
            'Constant\n10 1.225 340\nEnd\nReference\n4 .2 4\nEnd\nGround\n1 1 0\nEnd\n'
            'Weight\n1 1 .2 0 -.1 20 0 0 0 0 0 30 40 50\nEnd\n'
            'Beam 1\nMassless rigid connector\nt y chord\n1 0 .2\n5 4 .2\nEnd\n')
    model = parse_asw(text, beam_interpolation='drela-segspl-v1')
    gravity = np.array([.3, -.2, -9.])
    system, _ = make_system(model, panels=4, frame='free', gravity=gravity,
                            velocity=[.4, -.3, .2], structural_operator=MOVING_POLICY)
    n = system.network
    zero = np.zeros(system.size)
    residual, _, options = system.residual(zero, zero, detail=True)
    assert np.max(abs(residual)) < 1e-10
    _, data = n.residual(system.base, detail=True, **options)
    np.testing.assert_allclose(data['motion'].acceleration, gravity, atol=1e-10)
    np.testing.assert_allclose(data['motion'].angular_acceleration, 0., atol=1e-10)
    np.testing.assert_allclose(data['force'], 0., atol=1e-10)
    np.testing.assert_allclose(data['moment'], 0., atol=1e-10)
    # Six independent body acceleration columns; no descriptor eigensolver.
    d = np.array([.2, 0., -.1])
    s = np.array([[0., -d[2], d[1]], [d[2], 0., -d[0]], [-d[1], d[0], 0.]])
    expected = np.block([[2*np.eye(3), -2*s], [2*s, np.diag([3., 4., 5.])-2*s@s]])
    measured = np.zeros((6, 6))
    base, _ = n.residual(system.base, detail=True, **options)
    for j, constraint in enumerate(n.operating.constraints):
        trial = system.base.copy()
        increment = 1e-4
        trial[n.operating_start+j] += increment/n.operating.scale[constraint.variable]
        value, dtrial = n.residual(trial, detail=True, **options)
        f = np.sum(dtrial['force']-data['force'], axis=0)
        m = np.sum(dtrial['moment']-data['moment']+np.cross(dtrial['r'], dtrial['force']-data['force']), axis=0)
        measured[:, j] = -np.r_[f, m]/increment
        # The original physical net-load constraint rows contain the same
        # wrench, with their declared F and F*L nondimensional scales.
        scaled = (value-base)[-6:]*np.r_[np.full(3, n.F), np.full(3, n.F*n.L)]
        np.testing.assert_allclose(scaled, np.r_[f, m], atol=2e-12, rtol=2e-10)
    np.testing.assert_allclose(measured, expected, rtol=2e-9, atol=2e-9)
