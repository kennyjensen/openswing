"""Independent fixed-frame source inertia oracles, with no aircraft fixtures.

Expected equations are frozen in the source-dynamic-inertia test stage before
execution: steady Eqs. 50/55/56/78--83 and unsteady Eqs. 37--40. Completed
endpoint products are averaged; no symmetric FE mass is presumed. Primitive
tests evaluate synthetic residuals only, never an equilibrium or eigenproblem.
"""
import math
import numpy as np
import pytest

from openswing.aero import AnalysisError, FlightCondition
from openswing.asw import parse_asw
from openswing.inertia import Motion
from openswing.source_discrete import SourceSectionNetwork
from openswing.source_dynamics import SourceDynamicNetwork, DYNAMIC_POLICY


T = np.arange(1., 6.)
POINT_MASS = .7
POINT_ARM = np.array([.35, 0., -.15])
POINT_J = np.array([[.2, -.01, .02], [-.01, .3, -.03], [.02, -.03, .4]])


def cross_matrix(v):
    x, y, z = v
    return np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])


def rotation(v):
    """Rodrigues formula independent of the production motion utilities."""
    angle = np.linalg.norm(v)
    if angle == 0:
        return np.eye(3)
    k = cross_matrix(np.asarray(v)/angle)
    return np.eye(3)+np.sin(angle)*k+(1-np.cos(angle))*(k@k)


def properties(t, varying=True, kind='dual'):
    s = t-1 if varying else 0.
    normal = (2+.3*s, np.array([.12+.02*s, 0., -.08+.01*s]), .2+.025*s, .3+.015*s)
    additional = (.6+.1*s, np.array([-.09+.01*s, 0., .06-.005*s]), .04+.01*s, .07+.005*s)
    if kind == 'axial':
        return [(normal[0], np.zeros(3), 0., 0.), (0., np.zeros(3), 0., 0.)]
    if kind == 'torsion':
        return [(0., np.zeros(3), normal[2], normal[3]), (0., np.zeros(3), 0., 0.)]
    return [normal, additional]


def source(*, varying=True, kind='dual', point=False):
    rows = []
    for t in (1., 5.):
        values = [t]
        for mass, arm, icc, inn in properties(t, varying, kind):
            values += [10*mass, arm[0], arm[2], 10*icc, 10*inn]
        rows.append(' '.join(map(str, values)))
    return ('Name\nSource dynamic inertia independent fixture\nEnd\n'
            'Unit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n10 1.225 340\nEnd\n'
            'Reference\n4 .2 4\n.4 -.3 .2\nEnd\nGround\n1 1 0\nEnd\n'
            + ('Weight\n1 3 .35 2 -.15 7 0 0 0 0 0 2 3 4 .1 -.2 .3\nEnd\n' if point else '')
            + 'Beam 1\nStraight synthetic beam\nt x y z chord\n1 0 0 0 .2\n5 0 4 0 .2\n'
            't EIcc GJ EInn EIcs EIcn EIsn EA GKc GKn Cea Nea Cta Nta\n'
            '1 100 75 150 8 -13 9 800 300 400 -.1 .07 .3 -.2\n'
            '5 140 100 160 6 2 5 1600 900 1000 .2 -.03 -.1 .4\n'
            't mg Ccg Ncg mgcc mgnn Dmg DCcg DNcg Dmgcc Dmgnn\n'
            + '\n'.join(rows)+'\nEnd\n')


def make_net(*, varying=True, kind='dual', point=False, gravity=(0., 0., 0.), cls=SourceDynamicNetwork,
             text=None, **kwargs):
    model = parse_asw(source(varying=varying, kind=kind, point=point) if text is None else text,
                      beam_interpolation='drela-segspl-v1')
    return cls(model, {'default': 4, 'beams': {'1': {'nodes': T.tolist()}}}, None, gravity, [], **kwargs)


def state(net, *, curved=False, rigid=False):
    x = np.zeros(net.size)
    q = np.zeros((5, 3))
    r = np.c_[np.zeros(5), T-1, np.zeros(5)]
    if curved:
        q = np.array([[.08, -.12, .03], [.1, .04, -.07], [-.06, .13, .05],
                      [.09, -.08, -.04], [.12, .03, .06]])
        r += np.array([[.02, .01, -.03], [.04, -.02, .06], [-.01, .04, .09],
                       [.03, -.03, .02], [.06, .02, -.04]])
    if rigid:
        q[:] = [.16, -.21, .09]
        r = r@rotation(q[0]).T+np.array([.3, -.4, .2])
    pose = x[:6*net.nn].reshape(net.nn, 6)
    pose[:, :3], pose[:, 3:] = (r-net.rj)/net.L, q
    return x, r, np.array([rotation(v) for v in q])


def evaluate(net, x, values=None):
    z = np.zeros((net.nn, 3))
    return net.residual(x, detail=True, elastic_motion=(z, z, z, z) if values is None else values,
                        circulation_rate=np.empty(0))


def endpoint_oracle(r, rotations, values, gravity, *, varying=True, kind='dual', point=False):
    """Literal density formulas, direct endpoint products and symmetric transfer."""
    _, omega, accel, alpha = values
    ef, em = np.zeros((4, 2, 3)), np.zeros((4, 2, 3))
    force, moment = np.zeros((5, 3)), np.zeros((5, 3))
    for j in range(4):
        h = T[j+1]-T[j]
        for i in (j, j+1):
            for mu, arm, icc, inn in properties(T[i], varying, kind):
                d = rotations[i]@arm
                inertia = rotations[i]@np.diag([icc+mu*h*h/12, icc+inn, inn+mu*h*h/12])@rotations[i].T
                acg = accel[i]+np.cross(alpha[i], d)+np.cross(omega[i], np.cross(omega[i], d))
                f = mu*(gravity-acg)
                m = np.cross(d, f)-inertia@alpha[i]-np.cross(omega[i], inertia@omega[i])
                ef[j] += h*f/4
                em[j] += h*m/4
        force[j:j+2] += ef[j]
        moment[j:j+2] += em[j]
    if point:
        i = 2
        d, inertia = rotations[i]@POINT_ARM, rotations[i]@POINT_J@rotations[i].T
        acg = accel[i]+np.cross(alpha[i], d)+np.cross(omega[i], np.cross(omega[i], d))
        f = POINT_MASS*(gravity-acg)
        m = np.cross(d, f)-inertia@alpha[i]-np.cross(omega[i], inertia@omega[i])
        force[i] += f
        moment[i] += m
    return force, moment, ef, em


@pytest.mark.parametrize('kind', ['axial', 'torsion'])
@pytest.mark.parametrize('varying', [False, True])
def test_two_interval_scalar_action_is_endpoint_product_average(kind, varying):
    n = make_net(kind=kind, varying=varying)
    x, _, _ = state(n)
    assert n.ne == 4 and n.nn == 5
    matrix = np.zeros((3, 3))
    density = [properties(t, varying, kind)[0][0 if kind == 'axial' else 2] for t in T[:3]]
    if kind == 'torsion':
        density = [sum(properties(t, varying, kind)[0][2:]) for t in T[:3]]
    expected = np.zeros((3, 3))
    for j in range(2):
        expected[j:j+2, j:j+2] += np.tile(density[j:j+2], (2, 1))/4
    for k in range(3):
        z = np.zeros((5, 3)); a = z.copy(); a[k, 1] = 1
        values = (z, z, a, z) if kind == 'axial' else (z, z, z, a)
        _, data = evaluate(n, x, values)
        ends = data['element_forces' if kind == 'axial' else 'element_moments']
        for j in range(2):
            matrix[j:j+2, k] -= ends[j, :, 1]
    np.testing.assert_allclose(matrix, expected, atol=4e-16, rtol=3e-15)
    if varying:
        assert np.linalg.norm(matrix-matrix.T) > .01
    else:
        np.testing.assert_allclose(matrix@[1., -1., 1.], 0., atol=4e-16)
        np.testing.assert_allclose(matrix, matrix.T, atol=4e-16)


def test_rotating_nonuniform_dual_centroids_use_completed_endpoint_wrenches():
    gravity = np.array([.4, -.7, -9.])
    n = make_net(gravity=gravity, point=True)
    x, r, q = state(n, curved=True)
    rng = np.random.default_rng(12083)
    values = tuple(rng.normal(0., .3, (5, 3)) for _ in range(4))
    _, data = evaluate(n, x, values)
    expected = endpoint_oracle(r, q, values, gravity, point=True)
    for key, value in zip(('force', 'moment', 'element_forces', 'element_moments'), expected):
        np.testing.assert_allclose(data[key], value, rtol=3e-14, atol=8e-14)
    np.testing.assert_array_equal(data['element_forces'][:, 0], data['element_forces'][:, 1])
    np.testing.assert_array_equal(data['element_moments'][:, 0], data['element_moments'][:, 1])
    for origin in (np.zeros(3), np.array([.4, -.3, .2]), np.array([-1., .6, .8])):
        actual = np.sum(data['moment']+np.cross(r-origin, data['force']), axis=0)
        want = np.sum(expected[1]+np.cross(r-origin, expected[0]), axis=0)
        np.testing.assert_allclose(actual, want, rtol=4e-14, atol=1e-13)


def test_uniform_rigid_segment_and_point_wrench_count_eq80_once():
    gravity = np.array([.2, -.1, -9.])
    n = make_net(varying=False, point=True, gravity=gravity)
    x, r, rotations = state(n, rigid=True)
    q = rotations[0]
    omega, alpha, a0, u0 = map(np.array, ([.3, -.4, .2], [-.2, .3, .1], [.1, .4, -.3], [.7, -.2, .3]))
    values = (u0+np.cross(omega, r), np.broadcast_to(omega, r.shape),
              a0+np.cross(alpha, r)+np.cross(omega, np.cross(omega, r)), np.broadcast_to(alpha, r.shape))
    _, data = evaluate(n, x, values)
    entries = []
    for mu, arm, icc, inn in properties(1., False):
        mass = 4*mu
        center = (r[0]+r[-1])/2+q@arm
        inertia = q@np.diag([4*icc+mu*4**3/12, 4*(icc+inn), 4*inn+mu*4**3/12])@q.T
        entries.append((mass, center, inertia))
    entries.append((POINT_MASS, r[2]+q@POINT_ARM, q@POINT_J@q.T))
    force, moment, tensor = np.zeros(3), np.zeros(3), np.zeros((3, 3))
    for mass, center, inertia in entries:
        f = mass*(gravity-a0-np.cross(alpha, center)-np.cross(omega, np.cross(omega, center)))
        force += f
        moment += np.cross(center, f)-inertia@alpha-np.cross(omega, inertia@omega)
        tensor += inertia+mass*((center@center)*np.eye(3)-np.outer(center, center))
    np.testing.assert_allclose(np.sum(data['force'], axis=0), force, rtol=3e-14, atol=1e-13)
    np.testing.assert_allclose(np.sum(data['moment']+np.cross(r, data['force']), axis=0), moment, rtol=3e-14, atol=2e-13)
    actual_tensor = np.zeros((3, 3)); mass_terms = []
    for entry in data['masses']:
        for mass, center, inertia in zip(entry['mass'], entry['position'], entry['inertia']):
            mass_terms.append(mass)
            actual_tensor += inertia+mass*((center@center)*np.eye(3)-np.outer(center, center))
    assert math.fsum(mass_terms) == pytest.approx(math.fsum(e[0] for e in entries), abs=4e-15)
    np.testing.assert_allclose(actual_tensor, tensor, rtol=3e-14, atol=1e-13)


def test_zero_rate_residual_and_static_gravity_are_exactly_unchanged():
    gravity = np.array([.2, -.4, -9.])
    n = make_net(gravity=gravity, point=True)
    static = make_net(gravity=gravity, point=True, cls=SourceSectionNetwork)
    x, _, _ = state(n, curved=True)
    a, da = static.residual(x, detail=True)
    b, db = evaluate(n, x)
    np.testing.assert_array_equal(a, b)
    for key in ('force', 'moment', 'element_forces', 'element_moments'):
        np.testing.assert_array_equal(da[key], db[key])
    assert n.structural_operator == DYNAMIC_POLICY == 'drela-fixed-vacuum-v1'


def test_zero_linear_mass_keeps_section_rotary_acceleration_and_precession():
    n = make_net(kind='torsion')
    x, r, q = state(n, curved=True)
    z = np.zeros((5, 3)); omega = np.tile([.3, -.2, .4], (5, 1)); alpha = np.tile([-.1, .2, .3], (5, 1))
    values = (z, omega, z, alpha)
    _, data = evaluate(n, x, values)
    expected = endpoint_oracle(r, q, values, np.zeros(3), kind='torsion')
    np.testing.assert_array_equal(data['force'], z)
    np.testing.assert_allclose(data['moment'], expected[1], atol=3e-15, rtol=3e-14)
    assert np.linalg.norm(data['moment']) > .1
    assert sum(np.sum(item['mass']) for item in data['masses']) == 0
    assert sum(np.linalg.norm(item['inertia']) for item in data['masses']) > 1


@pytest.mark.parametrize('option', ['allow_signed_point_weights', 'allow_signed_distributed_weights'])
def test_signed_static_opt_in_is_rejected_even_for_positive_fixture(option):
    with pytest.raises(AnalysisError, match='nonnegative|signed'):
        make_net(**{option: True})


@pytest.mark.parametrize('field', ['mg', 'Dmg', 'mgcc', 'mgnn', 'Dmgcc', 'Dmgnn'])
def test_negative_literal_mass_or_section_inertia_is_rejected(field):
    text = source(kind='axial').replace('End\n', 'End\n', 1)
    # Replace the multi-field table's selected column at both literal rows.
    lines = text.splitlines(); at = next(i for i, line in enumerate(lines) if line.startswith('t mg Ccg'))
    col = lines[at].split().index(field)
    for i in (at+1, at+2):
        row = lines[i].split(); row[col] = '-1'; lines[i] = ' '.join(row)
    with pytest.raises((ValueError, AnalysisError), match='nonnegative|negative|inertia'):
        make_net(text='\n'.join(lines)+'\n')


@pytest.mark.parametrize('field', ['tdeps', 'tdgam'])
def test_negative_material_damping_is_rejected(field):
    text = source()[:-4]+f't {field}\n1 -.01\n5 -.01\nEnd\n'
    with pytest.raises(AnalysisError, match='damping'):
        make_net(text=text)


def test_unknown_tdkap_input_is_rejected_before_dynamics():
    text = source()[:-4]+'t tdkap\n1 .01\n5 .01\nEnd\n'
    with pytest.raises(AnalysisError, match='unrecognized input'):
        make_net(text=text)


@pytest.mark.parametrize('field', ['rates', 'acceleration', 'angular_acceleration'])
def test_moving_frame_is_rejected_on_constructor_and_residual(field):
    motion = Motion(**{field: [.1, 0., 0.]})
    with pytest.raises(AnalysisError, match='motion|fixed'):
        make_net(motion=motion)
    n = make_net(); x, _, _ = state(n)
    with pytest.raises(AnalysisError, match='motion|fixed'):
        n.residual(x, motion_override=motion)


def test_airflow_apparent_fluid_and_nonempty_circulation_are_rejected():
    model = parse_asw(source(), beam_interpolation='drela-segspl-v1')
    with pytest.raises(AnalysisError, match='airflow|vacuum|quiescent'):
        SourceDynamicNetwork(model, 4, FlightCondition(speed=1), [0, 0, 0], [])
    with pytest.raises(AnalysisError, match='airflow|vacuum|quiescent'):
        make_net(quiescent_density=1.23)
    n = make_net(); x, _, _ = state(n)
    with pytest.raises(AnalysisError, match='aerodynamic|airflow|vacuum'):
        n.residual(x, condition_override=FlightCondition(speed=1))
    with pytest.raises(AnalysisError, match='circulation'):
        n.residual(x, circulation_rate=np.ones(1))


def test_descriptor_acceleration_columns_match_independent_endpoint_action():
    from openswing.linear_dynamics import DynamicSystem
    n = make_net(point=True)
    x, r, q = state(n)
    system = DynamicSystem(n, x, frame='fixed')
    z = np.zeros(system.size); zero = np.zeros((5, 3)); step = 1e-3
    for rotational, node, axis in [(False, 0, 1), (False, 1, 0), (True, 2, 1), (True, 3, 2)]:
        col = system.velocity_start+(3*n.nn if rotational else 0)+3*node+axis
        derivative = z.copy(); derivative[col] = step
        measured = -(system.residual(z, derivative)-system.residual(z, -derivative))/(2*step)
        acceleration, angular = zero.copy(), zero.copy()
        (angular if rotational else acceleration)[node, axis] = system.W if rotational else system.V
        f, m, _, _ = endpoint_oracle(r, q, (zero, zero, acceleration, angular), np.zeros(3), point=True)
        expected = np.zeros(system.size)
        expected[6*n.ne:6*n.ne+3*n.nn] = -f.ravel()/n.F
        expected[6*n.ne+3*n.nn:6*(n.ne+n.nn)] = -m.ravel()/(n.F*n.L)
        np.testing.assert_allclose(measured, expected, rtol=4e-13, atol=4e-14)


def scalar_source(kind, varying=False):
    """One compliant coordinate; all other section directions exactly rigid."""
    rows = []
    for t in (1., 5.):
        s = t-1 if varying else 0.
        c = (80+20*s) if kind == 'axial' else (60+10*s)
        ea, gj = (c, 0.) if kind == 'axial' else (0., c)
        mu, icc, inn = (2+.3*s, 0., 0.) if kind == 'axial' else (0., .2+.025*s, .3+.015*s)
        rows.append(f'{t} 0 {gj} 0 {ea} 0 0 {10*mu} {10*icc} {10*inn}')
    return ('Name\nIndependent scalar source dynamics\nEnd\n'
            'Unit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n10 1.225 340\nEnd\n'
            'Reference\n4 .2 4\nEnd\nGround\n1 1 0\nEnd\n'
            'Beam 1\nSingle scalar compliance\nt x y z chord\n1 0 0 0 .2\n5 0 4 0 .2\n'
            't EIcc GJ EInn EA GKc GKn mg mgcc mgnn\n'+'\n'.join(rows)+'\nEnd\n')


def scalar_matrices(kind, count, varying):
    """Direct K and endpoint-product M, with the root removed last."""
    nodes = np.linspace(0., 4., count+1)
    stiffness, mass = np.zeros((count+1, count+1)), np.zeros((count+1, count+1))
    for j, (a, b) in enumerate(zip(nodes[:-1], nodes[1:])):
        h = b-a
        s = np.array([a, b]) if varying else np.zeros(2)
        c = 80+20*s if kind == 'axial' else 60+10*s
        density = 2+.3*s if kind == 'axial' else .5+.04*s
        stiffness[j:j+2, j:j+2] += np.mean(c)/h*np.array([[1., -1.], [-1., 1.]])
        mass[j:j+2, j:j+2] += h/4*np.tile(density, (2, 1))
    return stiffness[1:, 1:], mass[1:, 1:]


@pytest.mark.parametrize('kind', ['axial', 'torsion'])
def test_modal_complete_scalar_spectrum_and_uniform_continuum_convergence(kind):
    import json
    from scipy.linalg import eigvals
    from scipy.optimize import linear_sum_assignment
    from openswing.linear_dynamics import make_system, linearize, eigensystem
    frequencies = []
    for varying, count in [(False, 4), (False, 8), (False, 16), (True, 4)]:
        print('SOURCE_SCALAR_START '+json.dumps(dict(kind=kind, varying=varying, intervals=count)), flush=True)
        model = parse_asw(scalar_source(kind, varying), beam_interpolation='drela-segspl-v1')
        mesh = {'default': count, 'beams': {'1': {'nodes': np.linspace(1., 5., count+1).tolist()}}}
        system, _ = make_system(model, panels=mesh, frame='fixed', gravity=[0, 0, 0],
                                structural_operator=DYNAMIC_POLICY)
        assert type(system.network) is SourceDynamicNetwork
        assert system.network.ne == count and system.network.ng == 0
        k, mass = scalar_matrices(kind, count, varying)
        squared = eigvals(k, mass)
        expected = np.r_[np.sqrt(-squared.astype(complex)), -np.sqrt(-squared.astype(complex))]
        a, m = linearize(system, sparse=True)
        modes, meta = eigensystem(a.toarray(), m.toarray(), time_scale=system.W,
                                  count=2*count, method='dense')
        actual = np.array([complex(*mode['eigenvalue']) for mode in modes])
        assert meta['finite_dimension'] == len(actual) == 2*count
        ii, jj = linear_sum_assignment(abs(actual[:, None]-expected[None, :]))
        relative = abs(actual[ii]-expected[jj])/abs(expected[jj])
        assert np.max(relative) < 2e-8
        assert max(max(x['right_backward_error'], x['left_backward_error']) for x in modes) < 1e-10
        if varying:
            assert np.linalg.norm(mass-mass.T) > .01
        else:
            c, density = (80., 2.) if kind == 'axial' else (60., .5)
            wave = np.sqrt(c/density); h = 4/count
            exact_grid = 2*wave/h*np.tan((2*np.arange(1, count+1)-1)*np.pi/(4*count))
            positive = np.sort(actual.imag[actual.imag > 0])
            np.testing.assert_allclose(positive, exact_grid, rtol=2e-8, atol=2e-9)
            frequencies.append(positive[0])
        print('SOURCE_SCALAR_SPECTRUM '+json.dumps(dict(kind=kind, varying=varying, intervals=count,
            finite_dimension=meta['finite_dimension'], max_relative_pole_error=float(np.max(relative)),
            max_backward_error=max(max(x['right_backward_error'], x['left_backward_error']) for x in modes))), flush=True)
    wave = np.sqrt(80/2) if kind == 'axial' else np.sqrt(60/.5)
    continuum = np.pi*wave/8
    errors = np.asarray(frequencies)/continuum-1
    assert np.all(errors > 0) and np.all(errors[1:] < errors[:-1])
    assert np.all((errors[1:]/errors[:-1] > .20) & (errors[1:]/errors[:-1] < .26))
    assert errors[-1] < .001
