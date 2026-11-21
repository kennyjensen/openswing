"""Small independent frame/pencil checks for the moving source operator.

No aircraft fixtures. Complete-residual directional stencils are independent
of the assembled derivative helpers. The free axial oscillator selects only
its nonzero elastic roots; no global zero-root census or deflation is assumed.
"""
import numpy as np
import pytest

from openswing.asw import parse_asw
from openswing.inertia import Motion
from openswing.linear_dynamics import DynamicSystem, eigensystem, linearize, make_system
from openswing.source_dynamics import DYNAMIC_POLICY, MOVING_POLICY, SourceDynamicNetwork, SourceMovingNetwork


PANELS = {'default': 4, 'beams': {'1': {'count': 4, 'spacing': 'uniform'}}}
AXIAL_FREQUENCY = np.sqrt(100.*(1/2+1/3))
AXIAL_SOURCE = '''Name
Free source axial two-mass oracle
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
10 1.225 340
End
Reference
2 .2 2
0 0 0
0 0 0
End
Ground
1 1 0
End
Weight
1 1 0 0 0 20 0 0 0 0 0 10 15 20 0 0 0
1 3 0 2 0 30 0 0 0 0 0 12 18 24 0 0 0
End
Beam 1
Massless axial spring with rigid shear and rotation
t x y z chord
1 0 0 0 .2
3 0 2 0 .2
t EA EIcc GJ EInn GKc GKn
1 200 0 0 0 0 0
3 200 0 0 0 0 0
End
'''


def beam_source():
    return '''Name
Moving source frozen-pencil fixture
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
10 1.225 340
End
Reference
1 .2 1
.2 -.3 .1
-.1 .15 .05
End
Ground
1 1 0
End
Beam 1
Straight tapered-mass coupled-section beam
t x y z chord
1 0 0 0 .2
2 0 1 0 .2
t EA EIcc GJ EInn EIcs EIcn EIsn GKc GKn Cea Nea Cta Nta
1 5000 800 650 900 18 -13 11 4000 4500 .02 -.01 .03 -.02
2 5500 900 700 1000 18 -13 11 4200 4800 .03 -.015 .04 -.01
t mg Ccg Ncg mgcc mgnn tdeps tdgam
1 10 .04 -.03 .6 .8 .012 .018
2 13 .06 -.02 .8 1.0 .016 .022
End
'''


def model(text):
    return parse_asw(text, beam_interpolation='drela-segspl-v1')


def earth_rotation(angles):
    """Explicit published body-to-Earth Euler product, radians, no helper."""
    p, t, h = angles
    cp, sp, ct, st, ch, sh = np.cos(p), np.sin(p), np.cos(t), np.sin(t), np.cos(h), np.sin(h)
    return (np.array([[ch, sh, 0], [-sh, ch, 0], [0, 0, 1]])
            @ np.array([[ct, 0, st], [0, 1, 0], [-st, 0, ct]])
            @ np.array([[1, 0, 0], [0, cp, sp], [0, -sp, cp]]))


def directional(function, direction, h=4e-5):
    """Sixth-order symmetric complete-function derivative, not column probes."""
    differences = [function(k*h*direction)-function(-k*h*direction) for k in (1, 2, 3)]
    return (45*differences[0]-9*differences[1]+differences[2])/(60*h)


@pytest.fixture(scope='module')
def moving_pencil():
    motion = Motion(rates=[.17, -.13, .11], acceleration=[.25, -.18, .12],
                    angular_acceleration=[.04, -.03, .02])
    system, _ = make_system(model(beam_source()), panels=PANELS, frame='prescribed',
        motion=motion, attitude=[11., -7., 16.], velocity=[.7, -.4, .2], gravity_magnitude=.8,
        structural_operator=MOVING_POLICY, tolerance=1e-10)
    zero = np.zeros(system.size)
    assert np.max(abs(system.residual(zero, zero))) < 1e-9
    dense = linearize(system, step=1e-5)
    sparse = tuple(a.toarray() for a in linearize(system, step=1e-5, sparse=True))
    return system, dense, sparse


def test_nonzero_frame_dense_sparse_pencil_matches_complete_residual_actions(moving_pencil):
    system, (a, m), (sa, sm) = moving_pencil
    np.testing.assert_allclose(sa, a, rtol=2e-9, atol=2e-10)
    np.testing.assert_allclose(sm, m, rtol=3e-12, atol=3e-12)
    zero = np.zeros(system.size)
    rng = np.random.default_rng(87261)
    # Mixed directions test interactions across geometry, material loads,
    # reactions, relative velocities and all twelve frame coordinates.
    for _ in range(3):
        q = rng.normal(size=system.size)
        q /= np.linalg.norm(q)
        rate = np.zeros(system.size)
        rate[system.dynamic_indices] = rng.normal(size=len(system.dynamic_indices))
        rate /= np.linalg.norm(rate)
        expected_a = directional(lambda v: system.residual(v, zero), q)
        expected_m = -directional(lambda v: system.residual(zero, v), rate, h=.1)
        for aa, mm in ((a, m), (sa, sm)):
            np.testing.assert_allclose(aa@q, expected_a, rtol=2e-8, atol=2e-9)
            np.testing.assert_allclose(mm@rate, expected_m, rtol=2e-10, atol=2e-11)
    assert system.network.structural_operator == MOVING_POLICY
    assert system.state_derivative_diagnostics['mechanical_fallback'] is None
    assert system.state_derivative_diagnostics['direct_mechanical_columns'] == system.network.gamma_start-6*system.network.nn


def test_earth_gravity_attitude_columns_use_current_rotation_and_endpoint_products(moving_pencil):
    system, (a, _), _ = moving_pencil
    n = system.network
    _, rotations, *_ = n.unpack(system.base)
    angle = np.deg2rad(system.attitude)
    force_start = 6*n.ne
    for axis in range(3):
        perturb = angle.astype(complex)
        perturb[axis] += 1e-25j
        dg = np.imag(earth_rotation(perturb).T@np.array([0., 0., -.8]))/1e-25
        force, moment = np.zeros((n.nn, 3)), np.zeros((n.nn, 3))
        for e, (ia, ib) in enumerate(n.ends):
            # Literal linear density/CG tables on the original straight span.
            # The current physical frames, not averaged transforms, rotate CG.
            for i in (ia, ib):
                s = n.rj[i, 1]
                mass = (1+.3*s)*n.ds[e]/2
                arm = rotations[i]@np.array([.04+.02*s, 0., -.03+.01*s])
                f = mass*dg
                force[[ia, ib]] += f/2
                moment[[ia, ib]] += np.cross(arm, f)/2
        column = system.frame_start+9+axis
        expected = np.r_[force.ravel()/n.F, moment.ravel()/(n.F*n.L)]
        np.testing.assert_allclose(a[force_start:force_start+6*n.nn, column], expected,
                                   rtol=2e-8, atol=2e-10)


def test_galilean_velocity_change_preserves_local_mechanics(moving_pencil):
    system, _, _ = moving_pencil
    delta = np.array([1.1, -.8, .6])
    other = DynamicSystem(system.network, system.base, frame='prescribed',
        attitude=system.attitude, position=system.position, velocity=system.U0+delta,
        gravity_magnitude=system.gravity_magnitude)
    zero = np.zeros(system.size)
    q = np.random.default_rng(911).normal(0, .002, system.size)
    rate = np.random.default_rng(912).normal(0, .003, system.size)
    np.testing.assert_array_equal(system.residual(q, rate)[:system.network.size],
                                  other.residual(q, rate)[:system.network.size])
    np.testing.assert_allclose(other.Udot0-system.Udot0, -np.cross(system.Omega0, delta), atol=2e-16)
    np.testing.assert_allclose(other.pdot0-system.pdot0, earth_rotation(np.deg2rad(system.attitude))@delta,
                               atol=4e-16)
    assert np.max(abs(other.residual(zero, zero))) < 1e-9


def test_old_fixed_source_pencil_is_exactly_preserved_at_zero_frame_motion():
    systems = []
    for cls in (SourceDynamicNetwork, SourceMovingNetwork):
        n = cls(model(beam_source()), PANELS, None, [0., 0., 0.], [])
        systems.append(DynamicSystem(n, np.zeros(n.size), frame='fixed'))
    old, new = (linearize(s, step=1e-5) for s in systems)
    for actual, expected in zip(new, old):
        np.testing.assert_array_equal(actual, expected)
    assert systems[0].network.structural_operator == DYNAMIC_POLICY
    assert systems[1].network.structural_operator == MOVING_POLICY


@pytest.mark.parametrize('frame', ['free', 'mixed'])
def test_canonical_frame_closure_matches_independent_rigid_newton_euler(frame):
    # Rigid material directions, two real masses, six local gauge constraints.
    # The independently solved 6x6/3x3 Newton-Euler system has no beam unknowns.
    text = AXIAL_SOURCE.replace('1 200 0 0 0 0 0', '1 0 0 0 0 0 0').replace(
        '3 200 0 0 0 0 0', '3 0 0 0 0 0 0')
    aircraft = model(text)
    rm, ra = np.array([.2, -.3, .1]), np.array([-.1, .15, .05])
    aircraft.reference[1], aircraft.reference[2] = rm, ra
    omega = np.array([.17, -.13, .11])
    prescribed = np.array([0., -.18, 0., .04, 0., .02])
    applied_force, applied_moment = np.array([.6, -.3, .4]), np.array([.15, .2, -.1])
    target = None if frame == 'free' else {'force.x':.07, 'force.z':-.05, 'moment.y':.03}
    selected = np.arange(6) if frame == 'free' else np.array([0, 2, 4])
    desired = np.zeros(6) if frame == 'free' else np.array([.07, -.05, .03])

    def wrench(acceleration):
        acc, alpha = acceleration[:3], acceleration[3:]
        force = applied_force.copy()
        moment = applied_moment+np.cross(-rm, applied_force)
        for mass, position, diagonal in ((2., [0., 0., 0.], [1., 1.5, 2.]),
                                         (3., [0., 2., 0.], [1.2, 1.8, 2.4])):
            position, diagonal = np.asarray(position), np.asarray(diagonal)
            f = -mass*(acc+np.cross(alpha, position-ra)+np.cross(omega, np.cross(omega, position-ra)))
            force += f
            moment += np.cross(position-rm, f)-diagonal*alpha-np.cross(omega, diagonal*omega)
        return np.r_[force, moment]

    baseline = prescribed.copy()
    baseline[selected] = 0.
    w0 = wrench(baseline)
    matrix = np.column_stack([wrench(baseline+np.eye(6)[i])-w0 for i in selected])[selected]
    expected = baseline.copy()
    expected[selected] = np.linalg.solve(matrix, desired-w0[selected])
    system, _ = make_system(aircraft, panels=PANELS, frame=frame, load_targets=target,
        motion=Motion(omega, prescribed[:3], prescribed[3:]), gravity=[0., 0., 0.],
        loads=[dict(beam=1, t=1., force=applied_force, moment=applied_moment)],
        structural_operator=MOVING_POLICY, tolerance=1e-10)
    zero = np.zeros(system.size)
    residual, state, options = system.residual(zero, zero, detail=True)
    _, data = system.network.residual(state.x, detail=True, **options)
    actual = np.r_[data['motion'].acceleration, data['motion'].angular_acceleration]
    np.testing.assert_allclose(actual, expected, rtol=2e-9, atol=2e-10)
    assert np.max(abs(residual)) < 1e-9
    force = data['force'].sum(axis=0)
    moment = np.sum(data['moment']+np.cross(data['r']-rm, data['force']), axis=0)
    np.testing.assert_allclose(np.r_[force, moment], wrench(expected), atol=2e-9, rtol=2e-9)
    support = np.zeros(6)
    for row in data['reactions']:
        assert row['other_node'] is None
        f, m = np.asarray(row['force']), np.asarray(row['moment'])
        support += np.r_[f, m+np.cross(data['r'][row['node']]-rm, f)]
    np.testing.assert_allclose(support+np.r_[force, moment], 0., atol=2e-9)
    assert system.network.nc == 6
    assert system.network.operating.count == len(selected)


def test_free_two_mass_axial_frequency_and_original_pencil_vectors():
    system, _ = make_system(model(AXIAL_SOURCE), panels=PANELS, frame='free',
        gravity=[0., 0., 0.], structural_operator=MOVING_POLICY, tolerance=1e-10)
    a, m = linearize(system, step=1e-5, sparse=True)
    # eigensystem is the dense-input facade; the selected full-pencil method
    # performs its own sparse factorization. Keep this tiny oracle explicit.
    a, m = a.toarray(), m.toarray()
    assert system.network.nc == 6
    assert system.network.operating.count == 6
    assert np.max(abs(system.residual(np.zeros(system.size), np.zeros(system.size)))) < 1e-9
    # Complex shifts select nearby roots; neither call asks for the global
    # Jordan chains or presumes conjugate roots are equally near one shift.
    for sign in (1, -1):
        modes, metadata = eigensystem(a, m, time_scale=system.W, count=1,
            shift=(-.1, sign*AXIAL_FREQUENCY), method='full_shift_invert')
        assert len(modes) == 1
        pole = complex(*modes[0]['eigenvalue'])
        assert pole == pytest.approx(sign*1j*AXIAL_FREQUENCY, rel=2e-8, abs=2e-8)
        v, w = modes[0]['right'], modes[0]['left']
        av, mv = a@v, m@v
        ahw, mhw = a.conj().T@w, m.conj().T@w
        right = np.linalg.norm(av-pole*mv)/(np.linalg.norm(av)+abs(pole)*np.linalg.norm(mv))
        left = np.linalg.norm(ahw-pole.conjugate()*mhw)/(np.linalg.norm(ahw)+abs(pole)*np.linalg.norm(mhw))
        assert right <= 1e-8
        assert left <= 1e-8
        assert abs(np.vdot(w, mv)-1) <= 1e-8
        assert metadata['method'] == 'full_shift_invert'
