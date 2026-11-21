"""Primary joint mechanics under each unchanged structural policy.

Synthetic residual checks use independently assembled spatial wrenches and
literal section/centroid inputs. The last three tests make exactly three
solver calls: one expected mechanism rejection and two small equilibria.
No archived aircraft or experimental data are used as fitted targets.
"""
from copy import deepcopy

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from openswing.aero import AnalysisError, FlightCondition
from openswing.asw import parse_asw
from openswing.circulation_tangent import circulation_columns
from openswing.equilibrium_state import capture, restore
from openswing.network import StaticNetwork
from openswing.source_coupled import SourceCoupledNetwork, solve_source_coupled
from openswing.source_discrete import (SourceDiscreteNetwork, SourceSectionNetwork,
                                      STRUCTURAL_POLICY, COUPLED_POLICY,
                                      solve_source_discrete)
from openswing.structured_static import linearization


POLICIES = [StaticNetwork, SourceDiscreteNetwork, SourceSectionNetwork,
            SourceCoupledNetwork]


def source(*, joint=3, ground=0, single=False, distant=True, joint_t=3.,
           rigid=False, offsets=False, mass=False, axis='2 1 3',
           curve='-100 -200\n100 200'):
    """Two literal straight lifting beams; no implicit t=0 mirror."""
    text = ('Name\nSynthetic source joints\nEnd\n'
            'Units\nL 1 m\nT 1 s\nF 1 N\nEnd\n'
            'Constant\n10 1.2 340\nEnd\n'
            'Reference\n.8 .2 4\n.4 -.3 .2\nEnd\n'
            f'Ground\n1 1 {ground}\nEnd\n')
    if not single:
        text += f'Joint\n1 2 {joint_t} 1 {joint}\nEnd\n'
        if joint == 3:
            text += f'Jangle\n1 {axis}\n{curve}\nEnd\n'
        text += 'Sensor\n1 2 3 .1 4 0\nEnd\n'
    for index in range(1, 2 if single else 3):
        x, y, z = ((0., 0., 0.) if index == 1 else
                   ((.4, 2.3, .2) if distant else (0., 2., 0.)))
        text += (f'Beam {index}\nStraight lifting beam {index}\n'
                 't x y z chord Xax Cdf Cdp Cm dCLda\n'
                 f'1 {x} {y} {z} .25 .35 .006 .01 -.02 6\n'
                 f'3 {x} {y+2} {z} .18 .45 .008 .015 -.01 6.2\n')
        if not rigid:
            text += ('t EIcc GJ EInn EIcs EIcn EIsn EA\n'
                     '1 800 600 1200 40 -30 20 100000\n'
                     '3 1000 800 1500 60 -20 30 120000\n')
        if offsets:
            text += ('t Cea Nea Cta Nta GKc GKn\n'
                     '1 .03 -.01 .04 .02 40000 50000\n'
                     '3 .03 -.01 .04 .02 40000 50000\n')
        if mass:
            text += ('t mg Ccg Ncg Dmg DCcg DNcg\n'
                     '1 1.2 .04 .02 .3 .01 -.015\n'
                     '3 1.2 .04 .02 .3 .01 -.015\n')
        text += 'End\n'
    return text


def model(**kwargs):
    return parse_asw(source(**kwargs), beam_interpolation='drela-segspl-v1')


def mounted_source():
    """Small synthetic mounted fixture reusable by a separately owned browser check."""
    return source(distant=False, offsets=True, mass=True, axis='1 0 0')


def mounted_condition():
    return FlightCondition(speed=8., alpha=5., beta=1., density=1.2, mach=0.,
                           gravity_magnitude=0.)


def trial(n):
    x = np.zeros(n.size)
    u = np.linspace(.1, 1., n.nn)
    pose = x[:6*n.nn].reshape(n.nn, 6)
    pose[:, :3] = np.c_[.015*u, -.01*u*u, .02*u]/n.L
    pose[:, 3:] = np.c_[.12*u, -.08*u, .15*u*u]
    forces = x[6*n.nn:6*(n.nn+n.ne)].reshape(n.ne, 6)
    forces[:, :3] = np.array([2., -1., 3.])/n.F
    forces[:, 3:] = np.array([5., 7., 11.])/(n.F*n.L)
    if n.ng:
        x[n.gamma_start:n.operating_start] = .03*np.sin(np.linspace(.3, 2.6, n.ng))
    return x


def spatial_state(n, x):
    pose = x[:6*n.nn].reshape(n.nn, 6)
    return n.rj+pose[:, :3]*n.L, Rotation.from_rotvec(pose[:, 3:]).as_matrix()


def install_reaction(n, x, constraint, force, couple):
    y = x.copy()
    block = y[6*(n.nn+n.ne):n.gamma_start]
    typ = constraint['type']
    physical = (np.r_[force/n.F, couple/(n.F*n.L)] if typ in (0, 3)
                else force/n.F if typ == 1 else couple/(n.F*n.L))
    block[constraint['sl']] = physical
    return y


@pytest.mark.parametrize('cls', POLICIES)
@pytest.mark.parametrize('kind', [0, 1, 2])
def test_ground_types_keep_independent_reaction_and_kinematic_rows(cls, kind):
    n = cls(model(single=True, ground=kind), 4, None, [0., 0., 0.], [])
    x = trial(n); c = n.constraints[0]
    f, m = np.array([3., -2., 5.]), np.array([7., 11., -13.])
    y = install_reaction(n, x, c, f, m)
    base = n.residual(x); actual, detail = n.residual(y, detail=True)
    expected = np.zeros(n.size); start = 6*n.ne
    if kind != 2: expected[start+3*c['a']:start+3*c['a']+3] = f/n.F
    if kind != 1:
        offset = start+3*n.nn+3*c['a']; expected[offset:offset+3] = m/(n.F*n.L)
    np.testing.assert_allclose(actual-base, expected, rtol=0, atol=3e-14)
    r, q = spatial_state(n, x)
    rows = []
    if kind != 2: rows.extend((r[c['a']]-n.rj[c['a']])/n.L)
    if kind != 1: rows.extend(Rotation.from_matrix(q[c['a']]).as_rotvec())
    np.testing.assert_allclose(actual[6*(n.ne+n.nn):n.gamma_start], rows, atol=3e-14)
    reaction = detail['reactions'][0]
    np.testing.assert_allclose(reaction['force'], f if kind != 2 else np.zeros(3), atol=1e-13)
    np.testing.assert_allclose(reaction['moment'], m if kind != 1 else np.zeros(3), atol=1e-13)


@pytest.mark.parametrize('cls', POLICIES)
@pytest.mark.parametrize('kind', [0, 1, 2, 3])
def test_joint_types_conserve_offaxis_wrench_and_use_finite_rotations(cls, kind):
    n = cls(model(joint=kind), 4, None, [0., 0., 0.], [])
    x = trial(n); c = next(c for c in n.constraints if c['kind'] == 'joint')
    force, couple = np.array([3., -2., 5.]), np.array([7., 11., -13.])
    y = install_reaction(n, x, c, force, couple)
    base = n.residual(x); actual, detail = n.residual(y, detail=True)
    r, q = spatial_state(n, x); a, b = c['a'], c['b']; d = r[b]-r[a]
    f = np.zeros(3) if kind == 2 else force
    t = np.zeros(3) if kind == 1 else couple
    pair = [(a, f, t+np.cross(d, f)), (b, -f, -t)]
    expected = np.zeros(n.size); start = 6*n.ne
    for node, nf, nm in pair:
        expected[start+3*node:start+3*node+3] += nf/n.F
        offset = start+3*n.nn+3*node
        expected[offset:offset+3] += nm/(n.F*n.L)
    np.testing.assert_allclose(actual-base, expected, rtol=0, atol=5e-14)
    report = detail['reactions'][-1]
    np.testing.assert_allclose(report['moment'], pair[0][2], atol=2e-13)
    np.testing.assert_allclose(report['other_moment'], pair[1][2], atol=2e-13)
    for origin in [np.zeros(3), np.array([.4, -.3, .2]), np.array([-2., 1., 3.])]:
        total = sum(nm+np.cross(r[node]-origin, nf) for node, nf, nm in pair)
        np.testing.assert_allclose(total, 0., atol=2e-14)
    rows = []
    if kind != 2: rows.extend((d-q[a]@(n.rj[b]-n.rj[a]))/n.L)
    if kind != 1:
        relative = Rotation.from_matrix(q[a].T@q[b]).as_rotvec()
        if kind == 3:
            h0 = np.array([2., 1., 3.])/np.sqrt(14)
            e = c['element']; sign = -1 if c['end'] else 1
            dr = r[n.b[e]]-r[n.a[e]]
            trace = np.array([5., 7., 11.])+sign*np.cross(dr, [2., -1., 3.])/2
            mh = trace@(q[a]@h0)
            relative -= np.deg2rad(2*mh)*h0
            assert detail['hinges'][0]['structural_moment'] == pytest.approx(mh, abs=2e-13)
        rows.extend(relative)
    start = 6*(n.ne+n.nn)+c['sl'].start
    np.testing.assert_allclose(actual[start:start+len(rows)], rows, atol=3e-13)
    # A pin is not a force-only attachment on both beams when its pylon is long.
    if kind == 1:
        assert np.linalg.norm(report['moment']) > .1
        np.testing.assert_array_equal(report['other_moment'], [0., 0., 0.])


@pytest.mark.parametrize('joint_t,side', [(1., 'right'), (2., 'left'), (3., 'left')])
def test_hinge_moment_uses_source_gravity_and_aero_endpoint_trace(joint_t, side):
    n = SourceCoupledNetwork(model(offsets=True, mass=True, joint_t=joint_t), 4,
                             mounted_condition(), [1., -2., -10.], [])
    x = trial(n); factor = .6
    _, data = n.residual(x, factor, detail=True)
    r, q = spatial_state(n, x)
    expected_couples = []
    for mesh in data['meshes']:
        sl = n.beam_elements[mesh.beam.index]; a, b = n.a[sl], n.b[sl]
        ds = np.linalg.norm(n.rj[b]-n.rj[a], axis=1)
        mass_couple = np.zeros((len(ds), 3))
        for weight, arm in [(1.2, np.array([.04, 0., .02])), (.3, np.array([.01, 0., -.015]))]:
            aa, ab = q[a]@arm, q[b]@arm
            mass_couple += weight/10*ds[:, None]/2*(np.cross(aa, n.gravity)+np.cross(ab, n.gravity))
        strips = data['aero']['strips'][sl]
        f = np.asarray([s['force'] for s in strips]); m = np.asarray([s['moment'] for s in strips])
        p = np.asarray([s['position'] for s in strips])
        total = mass_couple+m+np.cross(p-(r[a]+r[b])/2, f)
        expected_couples.extend(np.repeat((total/2)[:, None, :], 2, axis=1))
    expected_couples = np.asarray(expected_couples)
    np.testing.assert_allclose(data['element_moments'], expected_couples, rtol=2e-13, atol=2e-13)
    c = next(c for c in n.constraints if c['type'] == 3); i, e = c['a'], c['element']
    sign = -1 if c['end'] else 1; dr = r[n.b[e]]-r[n.a[e]]
    body_trace = np.array([5., 7., 11.])+sign*np.cross(dr, [2., -1., 3.])/2
    body_trace += sign*factor*expected_couples[e, int(c['end'])]
    axis = q[i]@np.array([2., 1., 3.])/np.sqrt(14)
    actual = data['hinges'][0]
    assert actual['moment_trace'] == side
    assert actual['structural_moment'] == pytest.approx(body_trace@axis, abs=3e-13)
    assert abs(actual['structural_moment']-np.array([5., 7., 11.])@axis) > 1e-4
    assert abs(factor*expected_couples[e, int(c['end'])]@axis) > 1e-6


def test_source_hinge_direct_circulation_rows_match_two_stencil_widths():
    n = SourceCoupledNetwork(model(offsets=True, mass=True), 4, mounted_condition(), [1., -2., -10.], [])
    x, factor = trial(n), .6
    with linearization(n, x, factor, capture_circulation=True) as (fields, _):
        direct = circulation_columns(n, fields, factor)
    c = next(c for c in n.constraints if c['type'] == 3)
    row = 6*(n.ne+n.nn)+c['sl'].start+3
    assert np.max(np.abs(direct[row:row+3])) > 1e-7
    for step in (1e-5, 3e-6):
        columns = []
        for col in range(n.gamma_start, n.operating_start):
            delta = np.zeros_like(x); delta[col] = step
            columns.append((n.residual(x+delta, factor)-n.residual(x-delta, factor))/(2*step))
        expected = np.column_stack(columns)
        assert np.max(abs(direct-expected)/(1+abs(expected))) < 2e-7
    assert n.iteration_fields is None and n.tangent_influences is None


def test_all_policies_keep_natural_jangle_separate_from_beam_spline():
    for cls in POLICIES:
        n = cls(model(curve='-5 -4\n0 1\n5 9'), 4, None, [0., 0., 0.], [])
        # Independent natural-cubic second derivatives are [0, .18, 0].
        assert np.rad2deg(n.hinges[1].angle(2.5)) == pytest.approx(151/32, abs=1e-14)
        assert np.rad2deg(n.hinges[1].angle(2.5)) != pytest.approx(4.625, abs=1e-6)


def assert_balanced(result):
    assert result['residual'] < 1e-8
    np.testing.assert_allclose(result['force_balance'], 0., atol=2e-8)
    np.testing.assert_allclose(result['moment_balance'], 0., atol=2e-8)


def assert_v2_restore(n, result):
    saved = result['equilibrium_state']; original = deepcopy(saved)
    assert saved['version'] == 2 and len(saved['hinge_charts']) == 1
    assert 'launch' not in saved
    x = restore(n, saved)
    assert saved == original
    assert max(abs(n.residual(x))) < 1e-8
    again = capture(n, x, include_launch=False)
    assert again['identity'] == saved['identity']
    assert again['hinge_charts'][0]['angle_rad'] == pytest.approx(saved['hinge_charts'][0]['angle_rad'], abs=5e-14)
    shifted = deepcopy(saved); shifted['hinge_charts'][0]['angle_rad'] += 2*np.pi
    whole_turn = restore(n, shifted)
    assert max(abs(n.residual(whole_turn))) > 6.


def test_solve_isolated_pinned_ground_mechanism_is_rejected():
    with pytest.raises(AnalysisError, match='mechanism|redundant|singular'):
        solve_source_discrete(model(single=True, ground=1), panels=4, gravity=[0., 0., 0.])


def test_solve_source_rigid_links_matches_analytic_thirty_degree_hinge():
    m = model(rigid=True, distant=False, axis='1 0 0', curve='-100 -100\n100 100')
    loads = [dict(beam=2, t=3, moment=[30., 0., 0.])]
    result = solve_source_discrete(m, panels=4, gravity=[0., 0., 0.], loads=loads)
    assert_balanced(result)
    assert result['structural_operator'] == STRUCTURAL_POLICY
    tip = [row for row in result['nodes'] if row['beam'] == 2][-1]
    np.testing.assert_allclose(tip['position'], [0., 2+np.sqrt(3), 1.], atol=2e-9)
    assert result['hinges'][0]['angle_deg'] == pytest.approx(30., abs=2e-8)
    assert result['hinges'][0]['structural_moment'] == pytest.approx(30., abs=2e-8)
    n = SourceDiscreteNetwork(m, 4, None, [0., 0., 0.], loads)
    assert_v2_restore(n, result)


def test_solve_mounted_articulated_source_and_restore_owned_chart():
    m = parse_asw(mounted_source(), beam_interpolation='drela-segspl-v1'); c = mounted_condition()
    result = solve_source_coupled(m, c, panels=4)
    assert_balanced(result)
    assert result['structural_operator'] == COUPLED_POLICY
    assert np.linalg.norm(result['surface_force']) > .1
    angle = result['hinges'][0]['angle_deg']
    assert .01 < abs(angle) < 30.
    assert abs(angle-2*result['hinges'][0]['structural_moment']) < 2e-8
    n = SourceCoupledNetwork(m, 4, c, None, [])
    assert_v2_restore(n, result)
