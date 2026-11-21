"""Independent section/CG oracles for the broader source static policy.

Expected equations were frozen from rendered ASWING theory pages before the
candidate implementation was inspected. No archived aircraft response is a
target. Only the two tests named ``analytic`` run tiny equilibrium solves.
"""
from copy import deepcopy
import numpy as np
import pytest

from openswing.aero import AnalysisError
from openswing.asw import parse_asw
from openswing.equilibrium_state import capture, restore
from openswing.network import network_snapshot
from openswing.recovery import recover_structure
from openswing.sensors import network_sensors
from openswing.source_discrete import (SourceDiscreteNetwork, SourceSectionNetwork,
    STRUCTURAL_POLICY, SECTION_POLICY, solve_source_discrete)
from openswing.structured_static import jacobian


E0 = np.array([[100., 8., -13.], [8., 75., 9.], [-13., 9., 150.]])
E1 = np.array([[140., 6., 2.], [6., 100., 5.], [2., 5., 160.]])
OFF0 = np.array([-.1, .07, .3, -.2])  # Cea, Nea, Cta, Nta
OFF1 = np.array([.2, -.03, -.1, .4])
LINEAR0 = np.array([300., 800., 400.])  # GKc, EA, GKn
LINEAR1 = np.array([900., 1600., 1000.])
NODES = np.linspace(1., 3., 5)
ANGLES = np.array([0., .12, -.19, .23, -.08])


def grid(count=4):
    return {'default': count, 'beams': {'1': {'nodes': np.linspace(1., 3., count+1).tolist()}}}


def ry(angle):
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def section_fields(t, varying=True):
    f = (t-1)/2 if varying else 0.
    return tuple((1-f)*a+f*b for a, b in [(E0, E1), (OFF0, OFF1), (LINEAR0, LINEAR1)])


def section_source(*, varying=True, mass=False):
    """Reusable literal synthetic fixture; source text carries no policy tags."""
    rows = []
    for t in (1, 3):
        e, o, linear = section_fields(t, varying)
        values = [t, e[0, 0], e[1, 1], e[2, 2], e[0, 1], e[0, 2], e[1, 2],
                  linear[1], linear[0], linear[2], *o]
        rows.append(' '.join(map(str, values)))
    return ('Name\nFull source section synthetic fixture\nEnd\n'
        'Unit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n10 1.225 340\nEnd\n'
        'Reference\n2 1 2\n.4 -.3 2\nEnd\nGround\n1 1 0\nEnd\n'
        'Sensor\n1 1 1 .1 0 .2\n2 1 2 .3 1 -.1\n3 1 3 -.2 2 .1\nEnd\n'
        'Beam 1\nCoupled sections\nt x y z chord\n1 0 0 0 .2\n3 0 2 0 .2\n'
        't EIcc GJ EInn EIcs EIcn EIsn EA GKc GKn Cea Nea Cta Nta\n'
        + '\n'.join(rows) + '\nt Cshell Nshell Atshell\n1 .4 .2 .01\n3 .4 .2 .01\n'
        + ('t mg Ccg Ncg Dmg DCcg DNcg\n1 2 .2 .1 -1 -.2 .4\n3 6 -.1 .3 3 .5 -.2\n' if mass else '')
        + 'End\n')


def section_model(**kwargs):
    return parse_asw(section_source(**kwargs), beam_interpolation='drela-segspl-v1')


def net(*, varying=True, mass=False, gravity=(0., 0., 0.), cls=SourceSectionNetwork):
    return cls(section_model(varying=varying, mass=mass), grid(), None, gravity, [],
               allow_signed_distributed_weights=mass)


def law(e, offsets, linear, force, moment):
    """Explicit scalar Eq18/19 signs, independent of Section.compliance/H."""
    cea, nea, cta, nta = offsets
    shifted = moment+np.array([nta*force[1], -nea*force[0]+cea*force[2], -cta*force[1]])
    k = np.linalg.solve(e, shifted)
    strain = force/linear+np.array([-nea*k[1], nta*k[0]-cta*k[2], cea*k[1]])
    return strain, k, shifted


def prescribed(n, force=None, moment=None, rotate=True):
    force = np.tile([3., -12., 5.], (4, 1)) if force is None else np.asarray(force)
    moment = np.tile([-.08, -.19, 1.83], (4, 1)) if moment is None else np.asarray(moment)
    x = np.zeros(n.size)
    pose = x[:6*n.nn].reshape(n.nn, 6)
    if rotate:
        pose[:, 4] = ANGLES
        pose[:, :3] = np.array([[0, 0, 0], [.02, -.01, .03], [.04, -.03, .07],
                               [.06, -.04, .09], [.09, -.07, .12]])/n.L
    internal = x[6*n.nn:6*(n.nn+n.ne)].reshape(n.ne, 6)
    internal[:, :3], internal[:, 3:] = force/n.F, moment/(n.F*n.L)
    return x


def test_full_coupled_section_exact_oracle_and_shell_translation():
    n = net(varying=False)
    _, d = n.residual(prescribed(n, rotate=False), detail=True)
    e, meta = recover_structure(n, d)
    assert meta['structural_operator'] == SECTION_POLICY
    for item in e:
        np.testing.assert_allclose(item['strain'], [.0114, -.033, .0145], atol=2e-16)
        np.testing.assert_allclose(item['curvature_change'], [.03, -.02, .04], atol=2e-16)
        np.testing.assert_allclose(item['moment_axes'], [2.32, -.9, 5.43], atol=3e-15)
        assert item['axial_strain_tension'] == pytest.approx(-.015, abs=2e-16)
        assert item['shell']['axial_strain'] == pytest.approx(-.005, abs=2e-16)
        assert item['shell']['axial_strain_bound'] == pytest.approx(.037, abs=2e-16)
        assert item['shell']['shear_stress'] == pytest.approx(-45., abs=2e-13)
        force, moment = np.array(item['force_local']), np.array(item['moment_local'])
        strain, k = np.array(item['strain']), np.array(item['curvature_change'])
        assert force@strain+moment@k == pytest.approx(.5773, abs=2e-15)
        # Independent forward constitutive relation recovers input resultants.
        cea, nea, cta, nta = OFF0
        f = LINEAR0*(strain-[ -nea*k[1], nta*k[0]-cta*k[2], cea*k[1]])
        m = E0@k-[nta*f[1], -nea*f[0]+cea*f[2], -cta*f[1]]
        np.testing.assert_allclose(f, force, atol=8e-15)
        np.testing.assert_allclose(m, moment, atol=8e-15)
    sensors = network_sensors(n, d, e)
    for s, j, end in zip(sensors, [0, 1, 3], [0, 1, 1]):
        trace = e[j]['endpoint_traces'][end]
        fl, ml = np.array(trace['force_local']), np.array(trace['moment_local'])
        strain, k, translated = law(E0, OFF0, LINEAR0, fl, ml)
        np.testing.assert_allclose(s['strain'], strain, atol=2e-15)
        assert s['shell_strain'] == pytest.approx(fl[1]/800+.4*k[2]-.2*k[0], abs=2e-15)
        assert s['shell_shear_stress'] == pytest.approx(translated[1]/.02, abs=2e-13)
        assert s['strain_sample_t'] == s['t']


def test_variable_properties_and_nonorthogonal_transform_satisfy_source_rows():
    n = net()
    x = prescribed(n)
    residual, d = n.residual(x, detail=True)
    expected_rows = []
    for j in range(4):
        a, b = section_fields(NODES[j]), section_fields(NODES[j+1])
        e, off, linear = [(u+v)/2 for u, v in zip(a, b)]
        transform = (ry(ANGLES[j]).T+ry(ANGLES[j+1]).T)/2
        force, moment = transform@d['N'][j], transform@d['M'][j]
        strain, k, _ = law(e, off, linear, force, moment)
        dr = d['r'][j+1]-d['r'][j]
        expected_rows.append(np.r_[(dr-transform.T@(strain+[0, 1, 0])*.5)/n.L,
                                   [0, ANGLES[j+1]-ANGLES[j], 0]-k*.5])
        np.testing.assert_allclose(d['source_discrete']['translation_strain'][j], strain, atol=2e-15)
        np.testing.assert_allclose(d['source_discrete']['curvature_change'][j], k, atol=2e-15)
        assert np.linalg.norm(transform@transform.T-np.eye(3)) > 1e-4
        # Averaging already computed endpoint responses is a different law.
        ea, ka, _ = law(*a, force, moment)
        eb, kb, _ = law(*b, force, moment)
        assert np.linalg.norm(np.r_[strain-(ea+eb)/2, k-(ka+kb)/2]) > 1e-5
    np.testing.assert_allclose(residual[:24].reshape(4, 6), expected_rows, rtol=2e-13, atol=2e-15)


def cg_inputs(t):
    f = (t-1)/2
    return [(2+4*f, np.array([.2-.3*f, 0, .1+.2*f])),
            (-1+4*f, np.array([-.2+.7*f, 0, .4-.6*f]))]


def expected_cg(r, gravity, angles=ANGLES):
    forces, moments = np.zeros((4, 3)), np.zeros((4, 3))
    first = np.zeros(3); mass = 0.
    for j in range(4):
        midpoint = (r[j]+r[j+1])/2
        for node in [j, j+1]:
            for weight, arm in cg_inputs(NODES[node]):
                dm = weight*.5/(2*10)
                offset = ry(angles[node])@arm
                forces[j] += dm*gravity
                moments[j] += np.cross(offset, dm*gravity)
                mass += dm
                first += dm*(midpoint+offset)
    return forces, moments, mass, first


def test_signed_dual_cg_rotations_and_origin_covariant_global_balance():
    gravity = np.array([2., -3., -9.])
    n = net(mass=True, gravity=gravity)
    residual, d = n.residual(prescribed(n), detail=True)
    force, moment, mass, first = expected_cg(d['r'], gravity)
    np.testing.assert_allclose(d['element_forces'], np.repeat((force/2)[:, None], 2, axis=1), atol=2e-15)
    np.testing.assert_allclose(d['element_moments'], np.repeat((moment/2)[:, None], 2, axis=1), atol=2e-15)
    np.testing.assert_array_equal(d['element_forces'][:, 0], d['element_forces'][:, 1])
    np.testing.assert_array_equal(d['element_moments'][:, 0], d['element_moments'][:, 1])
    elements, _ = recover_structure(n, d)
    for j, element in enumerate(elements):
        a, b = element['endpoint_traces']
        np.testing.assert_allclose(np.array(b['force'])-a['force']+force[j], 0, atol=3e-15)
        np.testing.assert_allclose(np.array(b['moment'])-a['moment']+moment[j]
            +np.cross(d['r'][j+1]-d['r'][j], (np.array(a['force'])+b['force'])/2), 0, atol=3e-15)
        np.testing.assert_allclose((np.array(a['moment'])+b['moment'])/2, d['M'][j], atol=2e-15)
    for origin in [np.zeros(3), np.array([.4, -.3, 2.]), np.array([-1., 2., .5])]:
        n.model.reference[1] = origin
        result = network_snapshot(n, residual, d)
        np.testing.assert_allclose(result['applied_force'], mass*gravity, atol=4e-15)
        np.testing.assert_allclose(result['applied_moment'], np.cross(first-mass*origin, gravity), atol=8e-15)
        book = result['mass_properties']
        assert book['mass'] == pytest.approx(mass)
        np.testing.assert_allclose(book['first_moment'], first-mass*origin, atol=2e-15)
        assert book['physical'] is False and book['cg'] is None
        assert book['dynamic_inertia_available'] is False
        assert 'reference-axis epsilon_s' in result['output_scope']['strain_components']
        assert 'translated' in result['structure']['limitations'][-1]
        for key in ['inertia_reference', 'inertia_cg', 'spatial_matrix', 'spin_angular_momentum']:
            assert book[key] is None
    # Three positive knots give the independent quadratic
    # w(t)=1-4.5*(t-1)+4.5*(t-1)^2. All four interval midpoints
    # are positive, but the shared endpoint t=1.5 has weight -0.125.
    # Signed bookkeeping must include this endpoint-only negative sample.
    text = section_source()[:-4]+'t mg\n1 1\n2 1\n3 10\nEnd\n'
    model = parse_asw(text, beam_interpolation='drela-segspl-v1')
    with pytest.raises(AnalysisError, match='nonnegative|[Ss]igned'):
        SourceSectionNetwork(model, grid(), None, gravity, [])
    signed = SourceSectionNetwork(model, grid(), None, gravity, [], allow_signed_distributed_weights=True)
    assert any(record['beam'] == 1 and record['field'] == 'mg'
               for record in signed.inertia_model.signed_distributed_weights)


def test_zero_signed_weight_preserves_pure_couple_without_centroid_division():
    text = section_source(mass=True).replace('1 2 .2 .1 -1 -.2 .4\n3 6 -.1 .3 3 .5 -.2',
        '1 3 .2 .1 -3 -.3 .4\n3 3 .2 .1 -3 -.3 .4')
    n = SourceSectionNetwork(parse_asw(text), grid(), None, [0, 0, -10], [], allow_signed_distributed_weights=True)
    residual, d = n.residual(np.zeros(n.size), detail=True)
    result = network_snapshot(n, residual, d)
    np.testing.assert_allclose(result['applied_force'], 0, atol=1e-15)
    np.testing.assert_allclose(result['applied_moment'], [0, 3, 0], atol=2e-15)
    assert result['mass_properties']['mass'] == 0
    assert result['mass_properties']['cg'] is None
    assert result['mass_properties']['dynamic_inertia_available'] is False


def test_analytic_finite_shear_and_extension_with_rigid_bending():
    text = ('Name\nShear exact limit\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\n'
        'Constant\n10 1.225 340\nEnd\nReference\n2 1 2\nEnd\nGround\n1 1 0\nEnd\n'
        'Beam 1\nStraight\nt y chord EA GKc GKn Cea Nea Cta Nta\n'
        '1 0 .2 1000 200 500 .2 -.1 .3 .07\n3 2 .2 1000 200 500 .2 -.1 .3 .07\nEnd\n')
    result = solve_source_discrete(parse_asw(text), panels=grid(), gravity=[0, 0, 0],
        loads=[dict(beam=1, t=3, force=[3, 4, 5])], structural_operator=SECTION_POLICY)
    assert result['residual'] < 1e-10
    tangent = np.array([.015, 1.004, .01])
    np.testing.assert_allclose([v['position'] for v in result['nodes']], (NODES-1)[:, None]*tangent, atol=3e-10)
    np.testing.assert_allclose([v['rotation'] for v in result['nodes']], np.repeat(np.eye(3)[None], 5, axis=0), atol=3e-10)
    np.testing.assert_allclose(result['force_balance'], 0, atol=3e-9)
    np.testing.assert_allclose(result['moment_balance'], 0, atol=3e-9)
    assert result['equilibrium_state']['identity']['structural_operator'] == SECTION_POLICY
    assert 'launch' not in result['equilibrium_state']


def test_analytic_pure_torque_has_offset_induced_reference_axis_shear():
    text = ('Name\nOffset torque exact limit\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\n'
        'Constant\n10 1.225 340\nEnd\nReference\n2 1 2\nEnd\nGround\n1 1 0\nEnd\n'
        'Beam 1\nStraight\nt y chord GJ Cea Nea Cta Nta\n'
        '1 0 .2 40 .2 -.1 .3 .07\n3 2 .2 40 .2 -.1 .3 .07\nEnd\n')
    result = solve_source_discrete(parse_asw(text), panels=grid(), gravity=[0, 0, 0],
        loads=[dict(beam=1, t=3, moment=[0, 4, 0])], structural_operator=SECTION_POLICY)
    frames = np.array([ry(.1*s) for s in NODES-1])
    increments = np.array([((a+b)/2)@[.01, 1, .02]*.5 for a, b in zip(frames[:-1], frames[1:])])
    positions = np.vstack([np.zeros(3), np.cumsum(increments, axis=0)])
    assert result['residual'] < 1e-10
    np.testing.assert_allclose([v['position'] for v in result['nodes']], positions, atol=4e-10)
    np.testing.assert_allclose([v['rotation'] for v in result['nodes']], frames, atol=4e-10)
    for e in result['elements']:
        np.testing.assert_allclose(e['strain'], [.01, 0, .02], atol=3e-11)
        np.testing.assert_allclose(e['curvature_change'], [0, .1, 0], atol=3e-11)
    np.testing.assert_allclose(result['support_moment'], [0, -4, 0], atol=3e-9)


def test_zero_offset_policy_equivalence_and_saved_identity_separation():
    text = ('Name\nCompatible subset\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\n'
        'Constant\n10 1.225 340\nEnd\nReference\n2 1 2\nEnd\nGround\n1 1 0\nEnd\n'
        'Beam 1\nStraight\nt y chord EA EIcc GJ EInn EIcs EIcn EIsn mg\n'
        '1 0 .2 800 100 75 150 8 -13 9 2\n3 2 .2 1600 140 100 160 6 2 5 6\nEnd\n')
    m = parse_asw(text, beam_interpolation='drela-segspl-v1')
    old = SourceDiscreteNetwork(m, grid(), None, [0, 0, -10], [])
    new = SourceSectionNetwork(m, grid(), None, [0, 0, -10], [])
    x = prescribed(old)
    r0, d0 = old.residual(x, detail=True)
    r1, d1 = new.residual(x, detail=True)
    np.testing.assert_allclose(r1, r0, rtol=0, atol=2e-16)
    for key in ['force', 'moment', 'element_forces', 'element_moments']:
        np.testing.assert_array_equal(d0[key], d1[key])
    for key in ['force_local', 'moment_local', 'curvature_change', 'axial_strain']:
        np.testing.assert_array_equal(d0['source_discrete'][key], d1['source_discrete'][key])
    old_packet, new_packet = capture(old, x, include_launch=False), capture(new, x, include_launch=False)
    # Physical position capture subtracts the jig again on restore; allow only
    # floating-point subtraction roundoff, not an exact bytewise x assertion.
    np.testing.assert_allclose(restore(old, old_packet), x, rtol=0, atol=5e-16)
    np.testing.assert_allclose(restore(new, new_packet), x, rtol=0, atol=5e-16)
    assert old_packet['identity']['structural_operator'] == STRUCTURAL_POLICY
    for n, packet in [(old, new_packet), (new, old_packet)]:
        with pytest.raises(AnalysisError, match='match|operator|policy'):
            restore(n, packet)
    with pytest.raises(AnalysisError, match='zero|shear'):
        net(cls=SourceDiscreteNetwork)
    bad = deepcopy(new_packet)
    bad['identity']['structural_operator'] = 'invented-policy'
    with pytest.raises(AnalysisError, match='match|operator|policy'):
        restore(new, bad)


def test_structured_jacobian_includes_full_offset_law_and_rotating_cg_moments():
    gravity = np.array([2., -3., -9.])
    n = net(mass=True, gravity=gravity)
    x = prescribed(n)
    factor = .6
    matrix, _ = jacobian(n, x, factor)
    matrix = matrix.toarray()
    for j in range(4):
        a, b = section_fields(NODES[j]), section_fields(NODES[j+1])
        e, off, linear = [(u+v)/2 for u, v in zip(a, b)]
        transform = (ry(ANGLES[j]).T+ry(ANGLES[j+1]).T)/2
        for component in range(6):
            df = transform[:, component]*n.F if component < 3 else np.zeros(3)
            dm = transform[:, component-3]*(n.F*n.L) if component >= 3 else np.zeros(3)
            strain, k, _ = law(e, off, linear, df, dm)
            expected = np.zeros(24)
            expected[6*j:6*j+6] = np.r_[-transform.T@strain*.5/n.L, -k*.5]
            column = 6*n.nn+6*j+component
            np.testing.assert_allclose(matrix[:24, column], expected, rtol=2e-8, atol=2e-9)
    # The y rotation-vector chart is exact here: dRy/d(angle) can be written
    # analytically, independently of the residual's gravity implementation.
    node = 2
    angle = ANGLES[node]
    derivative = np.array([[-np.sin(angle), 0, np.cos(angle)], [0, 0, 0],
                           [-np.cos(angle), 0, -np.sin(angle)]])
    moment_derivative = np.zeros((5, 3))
    for j in [node-1, node]:
        couple = sum((np.cross(derivative@arm, weight/10*gravity)*.5/2
                      for weight, arm in cg_inputs(NODES[node])), start=np.zeros(3))
        moment_derivative[j] += couple/2
        moment_derivative[j+1] += couple/2
    start = 6*n.ne+3*n.nn
    np.testing.assert_allclose(matrix[start:start+3*n.nn, 6*node+4],
        (factor*moment_derivative/(n.F*n.L)).ravel(), rtol=2e-8, atol=2e-9)
