"""Independent Eqs.57/58/60/62 damping checks; no aircraft fixtures.

Translation uses the published approximation, not an invented exact inverse
of the nonorthogonal transform average. Curvature differences independently
differentiate the literal Euler expression. Scalar spectra retain relaxation
poles in rigid directions instead of silently filtering them.
"""
import json
import numpy as np
import pytest

from openswing.aero import AnalysisError
from openswing.asw import AswError, parse_asw
from openswing.source_discrete import SourceSectionNetwork
from openswing.source_dynamics import DYNAMIC_POLICY, SourceDynamicNetwork, source_strain_rates


def cross_matrix(v):
    x, y, z = v
    return np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])


def rotation(v):
    angle = np.linalg.norm(v)
    if angle == 0:
        return np.eye(3)
    k = cross_matrix(np.asarray(v)/angle)
    return np.eye(3)+np.sin(angle)*k+(1-np.cos(angle))*k@k


def frame(q):
    """Literal steady Eq.4, transposed to local-to-body convention."""
    phi, theta, psi = q
    cf, sf, ct, st, cp, sp = np.cos(phi), np.sin(phi), np.cos(theta), np.sin(theta), np.cos(psi), np.sin(psi)
    return np.array([[ct*cp, ct*sp*cf+st*sf, ct*sp*sf-st*cf],
                     [-sp, cp*cf, cp*sf],
                     [st*cp, st*sp*cf-ct*sf, st*sp*sf+ct*cf]]).T


def angles(r):
    """Independent Eq.4 inverse in the test's small, nonsingular chart."""
    phi = np.arctan2(r[2, 1], r[1, 1])
    psi = np.arctan2(-r[0, 1], np.hypot(r[1, 1], r[2, 1]))
    theta = np.arctan2(r[0, 2], r[0, 0])
    return np.array([phi, theta, psi])


def k_matrix(q):
    _, theta, psi = q
    return np.array([[np.cos(psi)*np.cos(theta), 0., -np.sin(theta)],
                     [-np.sin(psi), 1., 0.],
                     [np.cos(psi)*np.sin(theta), 0., np.cos(theta)]])


def geometric_measures(pa, pb, ra, rb, lengths):
    projected, curvature = [], []
    for a, b, r, s, h in zip(pa, pb, ra, rb, lengths):
        qa, qb = angles(r), angles(s)
        projected.append((r.T+s.T)@(b-a)/(2*h))
        curvature.append((k_matrix(qa)+k_matrix(qb))@(qb-qa)/(2*h))
    return np.c_[projected, curvature]


def finite_rate(pa, pb, ra, rb, va, vb, wa, wb, lengths, step=2e-6):
    values = []
    for sign in (-1, 1):
        r = np.array([rotation(sign*step*w)@q for w, q in zip(wa, ra)])
        s = np.array([rotation(sign*step*w)@q for w, q in zip(wb, rb)])
        values.append(geometric_measures(pa+sign*step*va, pb+sign*step*vb, r, s, lengths))
    return (values[1]-values[0])/(2*step)


def sample_fields():
    pa = np.array([[.1, .2, -.1], [-.2, .7, .1], [.3, -.1, .2]])
    pb = pa+np.array([[.1, .8, .3], [.3, 1.1, -.2], [-.2, .7, .1]])
    ra = np.array([frame(q) for q in [[.2, -.3, .1], [-.25, .2, -.15], [.1, .25, -.2]]])
    rb = np.array([frame(q) for q in [[-.1, .15, -.2], [.15, -.1, .3], [-.3, -.15, .15]]])
    va = np.array([[.2, -.1, .1], [.1, .05, -.2], [-.1, .3, .2]])
    vb = np.array([[-.1, .3, .2], [.3, -.2, .1], [.2, -.05, -.1]])
    wa = np.array([[.3, -.2, .1], [-.1, .25, -.15], [.2, .1, -.3]])
    wb = np.array([[-.15, .1, -.2], [.2, -.3, .1], [-.1, -.2, .25]])
    return pa, pb, ra, rb, va, vb, wa, wb, np.array([.85, 1.15, .75])


def eq60(pa, pb, ra, rb, va, vb, wa, wb, h):
    return np.array([(r.T+s.T)@(v-u-np.cross((w+z)/2, b-a))/(2*ds)
                     for a, b, r, s, u, v, w, z, ds in zip(pa, pb, ra, rb, va, vb, wa, wb, h)])


def test_finite_euler_curvature_rate_matches_independent_time_differences():
    args = sample_fields()
    got = source_strain_rates(*args)
    np.testing.assert_allclose(got[:, :3], eq60(*args), rtol=3e-14, atol=3e-14)
    for step in (2e-6, 1e-6):
        expected = finite_rate(*args, step=step)
        np.testing.assert_allclose(got[:, 3:], expected[:, 3:], rtol=2e-8, atol=2e-10)


def test_translation_covariance_term_is_explicitly_an_approximation():
    args = sample_fields(); pa, pb, ra, rb, _, _, wa, wb, h = args
    exact_projection = finite_rate(*args)[:, :3]
    published = eq60(*args)
    difference = np.array([-(s.T-r.T)@np.cross(z-w, b-a)/(4*ds)
                           for a, b, r, s, w, z, ds in zip(pa, pb, ra, rb, wa, wb, h)])
    np.testing.assert_allclose(exact_projection-published, difference, rtol=2e-8, atol=2e-10)
    assert np.max(abs(difference)) > .01


def test_unequal_time_translation_is_covariant_and_bare_eq61_is_not():
    args = sample_fields(); pa, pb, ra, rb, va, vb, wa, wb, h = args
    u = rotation([.6, -.35, .2]); offset = np.array([.5, -.8, .3])
    rotated = (pa@u.T+offset, pb@u.T+offset, u@ra, u@rb, va@u.T, vb@u.T, wa@u.T, wb@u.T, h)
    original_rates, rotated_rates = source_strain_rates(*args), source_strain_rates(*rotated)
    np.testing.assert_allclose(rotated_rates[:, :3], original_rates[:, :3], rtol=2e-14, atol=2e-14)
    d = np.diag([.02, .07, .02])
    correction = np.array([(r+s)@d@rate*ds/2 for r, s, rate, ds in zip(ra, rb, original_rates[:, :3], h)])
    transformed = np.array([(r+s)@d@rate*ds/2 for r, s, rate, ds in zip(u@ra, u@rb, rotated_rates[:, :3], h)])
    np.testing.assert_allclose(transformed, correction@u.T, rtol=2e-14, atol=2e-14)
    quarter_turn = rotation([np.pi/2, 0., 0.]); extension = np.array([0., 1., 0.])
    assert np.linalg.norm(d@(quarter_turn@extension)-quarter_turn@(d@extension)) == pytest.approx(.05)


def test_equal_frames_rigid_translation_and_spin_have_zero_rates():
    r = frame([.3, -.25, .2]); h = np.array([.6, 1.2])
    ra = np.repeat(r[None], 2, axis=0); rb = ra.copy()
    pa = np.array([[.1, .4, -.2], [.3, -.4, .1]]); pb = pa+h[:, None]*r[:, 1]
    w = np.tile([.2, -.3, .4], (2, 1)); drift = np.array([.5, -.2, .1])
    va, vb = drift+np.cross(w, pa), drift+np.cross(w, pb)
    np.testing.assert_allclose(source_strain_rates(pa, pb, ra, rb, va, vb, w, w, h), 0., atol=5e-16)


def model_text(damping='t tdeps tdgam\n1 .01 .03\n3 .09 .19\n5 .25 .51\n'):
    return ('Name\nIndependent source damping fixture\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\n'
            'Constant\n10 1.225 340\nEnd\nReference\n4 .2 4\nEnd\nGround\n1 1 0\nEnd\n'
            'Beam 1\nCoupled offset beam\nt x y z chord\n1 0 0 0 .2\n5 0 4 0 .2\n'
            't EIcc GJ EInn EIcs EIcn EIsn EA GKc GKn Cea Nea Cta Nta\n'
            '1 100 75 150 8 -13 9 800 300 400 -.1 .07 .3 -.2\n'
            '5 140 100 160 6 2 5 1600 900 1000 .2 -.03 -.1 .4\n'
            't mg mgcc mgnn Ccg Ncg\n1 20 2 3 .1 -.1\n5 24 3 4 -.05 .15\n'
            +damping+'End\n')


def network(text=None, cls=SourceDynamicNetwork):
    model = parse_asw(model_text() if text is None else text, beam_interpolation='drela-segspl-v1')
    return cls(model, {'default': 4, 'beams': {'1': {'nodes': [1., 2., 3., 4., 5.]}}}, None, [0., 0., 0.], [])


def state(net):
    x = np.zeros(net.size)
    vrot = np.array([[.1, -.2, .15], [-.2, .1, -.1], [.05, .2, -.15], [.15, -.1, .2], [-.1, .05, .1]])
    r = np.c_[.04*np.arange(5)**2, np.arange(5)+.03*np.arange(5)**2, .02*np.arange(5)**2]
    x[:6*net.nn].reshape(-1, 6)[:, :3] = (r-net.rj)/net.L
    x[:6*net.nn].reshape(-1, 6)[:, 3:] = vrot
    forces = np.array([[1., 2., -1.], [-2., 1., .5], [.5, 3., -.2], [-.3, 1., .4]])
    moments = np.array([[.2, -.3, .1], [.1, .2, -.4], [-.3, .1, .2], [.2, .4, -.1]])
    x[6*net.nn:6*(net.nn+net.ne)].reshape(-1, 6)[:] = np.c_[forces/net.F, moments/(net.F*net.L)]
    return x, r, np.array([rotation(q) for q in vrot]), forces, moments


def velocities():
    v = np.array([[.1, -.2, .05], [-.1, .1, .2], [.2, -.1, -.1], [.05, .2, -.1], [-.1, -.1, .15]])
    w = np.array([[.1, .2, -.1], [.2, -.1, .15], [-.1, .15, .2], [.05, -.1, .1], [.2, .05, -.15]])
    return v, w, np.zeros((5, 3)), np.zeros((5, 3))


def test_coupled_offset_law_rates_residual_and_recovery_use_source_sampling():
    n = network(); x, r, q, forces, moments = state(n); motion = velocities()
    got, data = n.residual(x, detail=True, elastic_motion=motion)
    args = (r[:-1], r[1:], q[:-1], q[1:], motion[0][:-1], motion[0][1:], motion[1][:-1], motion[1][1:], np.ones(4))
    rates = np.c_[eq60(*args), finite_rate(*args)[:, 3:]]
    t = np.arange(1., 6.); te = .01*(t[:-1]**2+t[1:]**2)/2; tg = 2*te+.01
    times = np.stack([tg, te, tg, te, tg, te], axis=1)
    np.testing.assert_allclose(n.damping_times, times, atol=2e-16)
    assert np.max(abs(te-.01*((t[:-1]+t[1:])/2)**2)) > .002
    np.testing.assert_allclose(data['strain_rate'], rates, rtol=2e-8, atol=2e-10)
    expected, strains, curvatures = [], [], []
    for j in range(4):
        f = (q[j].T+q[j+1].T)@forces[j]/2; m = (q[j].T+q[j+1].T)@moments[j]/2
        s = (j+.5)/4
        ecc, gj, enn, ecs, ecn, esn = np.array([100, 75, 150, 8, -13, 9])+s*np.array([40, 25, 10, -2, 15, -4])
        ea, gkc, gkn = np.array([800, 300, 400])+s*np.array([800, 600, 600])
        cea, nea, cta, nta = np.array([-.1, .07, .3, -.2])+s*np.array([.3, -.1, -.4, .6])
        h = np.array([[0., nta, 0.], [-nea, 0., cea], [0., -cta, 0.]])
        e = np.array([[ecc, ecs, ecn], [ecs, gj, esn], [ecn, esn, enn]])
        kap = np.linalg.solve(e, m+h@f)
        eps = f/np.array([gkc, ea, gkn])+h.T@kap
        eps -= times[j, :3]*rates[j, :3]; kap -= times[j, 3:]*rates[j, 3:]
        strains.append(eps); curvatures.append(kap)
        translation = r[j+1]-r[j]-(q[j]+q[j+1])@(eps+[0., 1., 0.])/2
        qa, qb = angles(q[j]), angles(q[j+1])
        curvature = (k_matrix(qa)+k_matrix(qb))@(qb-qa)/2-kap
        expected.append(np.r_[translation/n.L, curvature])
    np.testing.assert_allclose(got[:6*n.ne].reshape(-1, 6), expected, rtol=2e-8, atol=2e-10)
    np.testing.assert_allclose(data['source_discrete']['translation_strain'], strains, rtol=2e-8, atol=2e-10)
    np.testing.assert_allclose(data['source_discrete']['curvature_change'], curvatures, rtol=2e-8, atol=2e-10)
    np.testing.assert_allclose(data['mechanical_strain'], np.c_[strains, curvatures], rtol=2e-8, atol=2e-10)


def test_damping_jump_uses_inward_endpoint_values():
    table = 't tdeps tdgam\n1 .01 .02\n3 .03 .06\n3 .09 .12\n5 .11 .16\n'
    n = network(model_text(table))
    te, tg = np.array([.015, .025, .095, .105]), np.array([.03, .05, .13, .15])
    np.testing.assert_allclose(n.damping_times, np.stack([tg, te, tg, te, tg, te], axis=1), atol=2e-16)


def test_zero_rates_leave_source_static_residual_exactly_unchanged():
    n = network(); static = network(cls=SourceSectionNetwork); x, *_ = state(n)
    zero = np.zeros((5, 3))
    r1, d1 = n.residual(x, detail=True, elastic_motion=(zero, zero, zero, zero))
    r0, d0 = static.residual(x, detail=True)
    np.testing.assert_array_equal(r1, r0)
    for key in ('force', 'moment', 'element_forces', 'element_moments'):
        np.testing.assert_array_equal(d1[key], d0[key])


@pytest.mark.parametrize('field', ['tdeps', 'tdgam'])
@pytest.mark.parametrize('value', ['-.01', 'nan', 'inf'])
def test_invalid_whole_damping_table_is_rejected(field, value):
    text = model_text(f't {field}\n1 {value}\n5 .02\n')
    with pytest.raises((AnalysisError, AswError, ValueError), match='finite|nonnegative|non-finite|Non-finite|positive'):
        network(text)


def test_positive_knots_with_negative_spline_endpoint_are_rejected():
    # Three knots specify (t-2)^2-.5; all file values positive, t=2 negative.
    text = model_text('t tdeps\n1 .5\n3 .5\n5 8.5\n')
    with pytest.raises(AnalysisError, match='endpoint damping.*nonnegative'):
        network(text)


def scalar_text(kind, tau):
    ea, gj = (80., 0.) if kind == 'axial' else (0., 60.)
    mu, icc, inn = (2., 0., 0.) if kind == 'axial' else (0., .2, .3)
    return ('Name\nDamped scalar source oracle\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\n'
            'Constant\n10 1.225 340\nEnd\nReference\n4 .2 4\nEnd\nGround\n1 1 0\nEnd\n'
            'Beam 1\nSingle finite compliance\nt x y z chord\n1 0 0 0 .2\n5 0 4 0 .2\n'
            't EIcc GJ EInn EA GKc GKn mg mgcc mgnn tdeps tdgam\n'
            + ''.join(f'{t} 0 {gj} 0 {ea} 0 0 {10*mu} {10*icc} {10*inn} {tau} {tau}\n' for t in (1, 5))+'End\n')


@pytest.mark.parametrize('kind,tau', [('axial', .002), ('torsion', .2)])
def test_scalar_damped_complete_spectrum_including_twenty_relaxation_poles(kind, tau):
    from scipy.optimize import linear_sum_assignment
    from openswing.linear_dynamics import make_system, linearize, eigensystem
    # Four scalar second-order coordinates yield 8 roots; five rigid strain
    # coordinates per interval yield 20 first-order relaxation roots.
    count = 4; h = 1.; c, density = (80., 2.) if kind == 'axial' else (60., .5)
    omega = 2*np.sqrt(c/density)/h*np.tan((2*np.arange(1, count+1)-1)*np.pi/(4*count))
    physical = np.concatenate([np.roots([1., tau*w*w, w*w]).astype(complex) for w in omega])
    expected = np.r_[physical, np.full(5*count, -1/tau, dtype=complex)]
    model = parse_asw(scalar_text(kind, tau), beam_interpolation='drela-segspl-v1')
    mesh = {'default': 4, 'beams': {'1': {'nodes': [1., 2., 3., 4., 5.]}}}
    print('SOURCE_DAMPED_START '+json.dumps(dict(kind=kind, damping_time=tau)), flush=True)
    system, _ = make_system(model, panels=mesh, frame='fixed', gravity=[0., 0., 0.], structural_operator=DYNAMIC_POLICY)
    a, m = linearize(system, sparse=True)
    modes, meta = eigensystem(a.toarray(), m.toarray(), time_scale=system.W, count=len(expected), method='dense')
    got = np.array([complex(*v['eigenvalue']) for v in modes])
    assert meta['finite_dimension'] == len(got) == 28
    rows, cols = linear_sum_assignment(abs(got[:, None]-expected[None, :]))
    error = abs(got[rows]-expected[cols])/abs(expected[cols])
    backward = max(max(v['right_backward_error'], v['left_backward_error']) for v in modes)
    assert max(error) < 2e-8
    assert backward < 1e-10
    assert np.all(got.real < 0.)
    assert sum(abs(got+1/tau) < 1e-6/tau) == 20
    if kind == 'axial':
        assert all(abs(p.imag) > 0 for p in physical)
    else:
        assert any(abs(p.imag) == 0 for p in physical)
    print('SOURCE_DAMPED_SPECTRUM '+json.dumps(dict(kind=kind, damping_time=tau, finite_dimension=28,
        physical_poles=8, relaxation_poles=20, maximum_relative_pole_error=float(max(error)),
        maximum_backward_error=float(backward))), flush=True)
