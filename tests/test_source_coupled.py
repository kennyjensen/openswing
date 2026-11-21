"""Independent transfer and integration checks for mounted source aerodynamics.

The rational transfer targets precede the candidate implementation and come
from Eqs. 51, 55–56, 67, 70 and 72. These are synthetic checks, not archived
ASWING targets. Only the two tests named ``solve`` run equilibria.
"""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from openswing.aero import AnalysisError, FlightCondition
from openswing.asw import parse_asw
from openswing.circulation_tangent import circulation_columns
from openswing.equilibrium_state import capture, restore
from openswing.local_motion import NetworkMotion
from openswing.network import network_snapshot
from openswing.source_coupled import SourceCoupledNetwork, solve_source_coupled
from openswing.source_discrete import COUPLED_POLICY, SourceSectionNetwork
from openswing.structured_static import linearization


def source(*, rigid=False, mass=True):
    material = ('' if rigid else
        't EIcc GJ EInn EIcs EIcn EIsn EA GKc GKn\n'
        '1 800 600 1200 50 -30 20 60000 25000 30000\n'
        '3 1200 900 1600 70 -20 35 80000 35000 40000\n')
    return ('Name\nSynthetic mounted source coupling\nEnd\n'
        'Unit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n10 1.2 340\nEnd\n'
        'Reference\n.5 .25 2\n.4 -.3 .2\nEnd\nGround\n1 1 0\nEnd\n'
        'Sensor\n1 1 3 .3 2 .15\nEnd\nBeam 1\nTapered lifting beam\n'
        't x y z chord Xax alpha dCLda Cdf Cdp Cm\n'
        '1 0 0 0 .3 .35 -1 6 .006 .01 -.03\n'
        '3 .2 2 .1 .18 .5 1 6.25 .01 .02 -.02\n'
        + material
        + 't Cea Nea Cta Nta Cshell Nshell Atshell\n'
        '1 -.02 .01 .04 -.02 .1 .03 .002\n'
        '3 .03 -.015 .02 .01 .08 .025 .0015\n'
        't dCLdF1 dCMdF1\n1 .2 -.02\n3 .3 -.015\n'
        + ('t mg Ccg Ncg Dmg DCcg DNcg\n'
           '1 1.2 .02 .01 .2 -.01 .03\n'
           '3 .8 -.01 .02 .3 .04 -.01\n' if mass else '')
        + 'End\n')


def model(**kwargs):
    return parse_asw(source(**kwargs), beam_interpolation='drela-segspl-v1')


def condition(**kwargs):
    return FlightCondition(speed=8., alpha=4., beta=2., density=1.2, mach=0.,
                           controls={1: .15}, **kwargs)


def network(*, flight=True, mass=True, rigid=False):
    return SourceCoupledNetwork(model(mass=mass, rigid=rigid), 4,
        condition() if flight else None, [1., -2., -10.], [])


def trial(n):
    x = np.zeros(n.size)
    u = np.linspace(0., 1., n.nn)
    pose = x[:6*n.nn].reshape(n.nn, 6)
    pose[:, :3] = np.c_[.01*u, -.006*u*u, .02*u*u]/n.L
    pose[:, 3:] = np.c_[.025*u, -.035*u*u, .018*u]
    wrench = x[6*n.nn:6*(n.nn+n.ne)].reshape(n.ne, 6)
    wrench[:, :3] = np.array([1., -.5, 2.])/n.F
    wrench[:, 3:] = np.array([.1, -.2, .15])/(n.F*n.L)
    if n.ng:
        x[n.gamma_start:n.operating_start] = .04*np.sin(np.linspace(.3, 2.8, n.ng))
    return x


def bare_transfer():
    n = SourceCoupledNetwork.__new__(SourceCoupledNetwork)
    n.beam_elements = {1: slice(0, 1)}
    n.a, n.b = np.array([0]), np.array([1])
    mesh = SimpleNamespace(beam=SimpleNamespace(index=1), r0=np.array([[1., 2., -1.]]),
        r1=np.array([[2., 5., 0.]]), rm=np.array([[1.2, 2.6, -.8]]))
    return n, mesh


def test_transfer_matches_exact_noncentral_oracle_and_reference_covariance():
    n, mesh = bare_transfer()
    force, moment = np.array([[-17.5, 0., 33.75]]), np.array([[0., -24.625, 0.]])
    ends = list(n.steady_lifting_wrenches(mesh, force, moment))
    for ids, f, m in ends:
        np.testing.assert_array_equal(f, force/2)
        np.testing.assert_allclose(m, [[-15.1875, -4.625, -7.875]], atol=4e-15)
    np.testing.assert_array_equal(ends[0][0], [0])
    np.testing.assert_array_equal(ends[1][0], [1])
    for origin in [np.zeros(3), np.array([2/3, -1.5, 1/7]), np.array([-10., 4., 9.])]:
        actual = sum((m+np.cross(r-origin, f))[0] for r, (_, f, m) in zip([mesh.r0, mesh.r1], ends))
        expected = (moment+np.cross(mesh.rm-origin, force))[0]
        np.testing.assert_allclose(actual, expected, atol=3e-14)
    # Inherited generic transfer is also globally conservative, but its unequal
    # couples change the physical mean moment unless the mixed M is corrected.
    ja = (moment+np.cross(mesh.rm-mesh.r0, force))/2
    jb = (moment+np.cross(mesh.rm-mesh.r1, force))/2
    correction = .4*(ja-jb)/2
    np.testing.assert_allclose(correction, [[10.125, -5.125, 5.25]], atol=4e-15)
    assert np.linalg.norm(correction) > 10.


def test_transfer_derivative_columns_and_rotation_covariance():
    n, mesh = bare_transfer()
    force = np.array([[[-17.5, 2., 0.], [0., -3., 4.], [33.75, 5., -2.]]])
    moment = np.array([[[0., .1, 2.], [-24.625, .2, -1.], [0., -.3, 4.]]])
    ends = list(n.steady_lifting_wrenches(mesh, force, moment))
    arm = mesh.rm[0]-(mesh.r0[0]+mesh.r1[0])/2
    expected = np.column_stack([(moment[0, :, j]+np.cross(arm, force[0, :, j]))/2 for j in range(3)])
    for _, f, m in ends:
        np.testing.assert_array_equal(f, force/2)
        np.testing.assert_allclose(m[0], expected, atol=4e-15)
    rotation = np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])
    moved = SimpleNamespace(beam=mesh.beam, **{key:getattr(mesh, key)@rotation.T for key in ['r0', 'r1', 'rm']})
    transformed = list(n.steady_lifting_wrenches(moved, rotation@force, rotation@moment))
    for (_, f, m), (_, rf, rm) in zip(ends, transformed):
        np.testing.assert_allclose(rf, rotation@f, atol=2e-15)
        np.testing.assert_allclose(rm, rotation@m, atol=4e-15)


def test_direct_circulation_columns_match_two_full_residual_stencils():
    n = network()
    x, factor = trial(n), .6
    assert n.ne == n.ng == 4
    assert np.max(abs(n.fractions[1]-.5)) > .1
    with linearization(n, x, factor, capture_circulation=True) as (fields, _):
        direct = circulation_columns(n, fields, factor)
    assert n.iteration_fields is None and n.tangent_influences is None
    np.testing.assert_array_equal(direct[:6*n.ne], 0.)
    assert np.max(abs(direct[6*n.ne+3*n.nn:6*(n.ne+n.nn)])) > 1e-4
    for step in [1e-5, 3e-6]:
        columns = []
        for col in range(n.gamma_start, n.operating_start):
            delta = np.zeros_like(x); delta[col] = step
            columns.append((n.residual(x+delta, factor)-n.residual(x-delta, factor))/(2*step))
        expected = np.column_stack(columns)
        assert np.max(abs(direct-expected)/(1+abs(expected))) < 2e-7
    # Compact Newton probes must retain precisely the same source constitutive
    # equations and loads as detailed recovery.
    plain = n.residual(x, factor)
    detailed, _ = n.residual(x, factor, detail=True)
    np.testing.assert_allclose(plain, detailed, rtol=0, atol=2e-14)


def test_gravity_cache_and_f_reac_exclude_aerodynamic_loads():
    n = network()
    x = trial(n)
    before = None
    for multiplier in [1., 1.7]:
        state = x.copy(); state[n.gamma_start:n.operating_start] *= multiplier
        residual, d = n.residual(state, detail=True)
        expected = []
        for mesh in n.meshes:
            f0, f1 = (mesh.t0-1)/2, (mesh.t1-1)/2
            weight = ((1.4-.3*f0)+(1.4-.3*f1))/2
            expected.extend((weight*n.ds/10)[:, None]*n.gravity)
        expected = np.asarray(expected)
        np.testing.assert_allclose(d['distributed_mass_force'], expected, atol=3e-16)
        np.testing.assert_allclose(n.mass_cached[-1].sum(axis=1), expected, atol=3e-16)
        if before is not None:
            np.testing.assert_array_equal(n.mass_cached[0], before)
        before = n.mass_cached[0].copy()
        assert np.linalg.norm(d['force']-n.mass_cached[0]) > .1
        result = network_snapshot(n, residual, d)
        for j, row in enumerate(result['strips']):
            mesh = d['meshes'][0]
            assert row['f_reac'] == pytest.approx(expected[j]@mesh.frames[j, :, 2]/mesh.length[j], abs=2e-14)
        assert 'endpoint-averaged' in result['section_output_definitions']['f_reac_sampling']


def test_zero_airflow_limit_and_saved_operator_identity():
    n = network(flight=False)
    old = SourceSectionNetwork(n.model, 4, None, n.gravity, [])
    x = trial(n)
    np.testing.assert_allclose(n.residual(x), old.residual(x), rtol=0, atol=2e-15)
    packet = capture(n, x, include_launch=False)
    assert packet['identity']['structural_operator'] == COUPLED_POLICY
    np.testing.assert_allclose(restore(n, packet), x, rtol=0, atol=5e-16)
    with pytest.raises(AnalysisError, match='match|operator|policy'):
        restore(old, packet)
    changed = deepcopy(packet); changed['identity']['structural_operator'] = 'invented-policy'
    with pytest.raises(AnalysisError, match='match|operator|policy'):
        restore(n, changed)


def test_stationary_scope_rejects_frame_local_and_circulation_rates():
    for field in ['rates', 'acceleration', 'angular_acceleration']:
        with pytest.raises(AnalysisError, match='motion|zero|static'):
            SourceCoupledNetwork(model(), 4, replace(condition(), **{field:(.01, 0., 0.)}), None, [])
    n = network(); x = trial(n)
    z = np.zeros((n.nn, 3))
    with pytest.raises(AnalysisError, match='dynamic'):
        n.residual(x, elastic_motion=(z,z,z,z))
    with pytest.raises(AnalysisError, match='dynamic'):
        n.residual(x, circulation_rate=np.zeros(n.ng))
    r, q, _, _, _, gamma = n.unpack(x)
    geometry = n.geometry(r,q); meshes = n.deformed_meshes(r,q,geometry)
    velocity = z.copy(); velocity[-1,0] = .01
    moving = NetworkMotion(n,r,q,velocity,z,z,z)
    with pytest.raises(AnalysisError, match='motion|stationary|zero|dynamic'):
        n.external(r,q,meshes,gamma,n.condition,n.motion,('test',),local_motion=moving)


def assert_balanced(result):
    assert result['residual'] < 1e-8
    np.testing.assert_allclose(result['force_balance'], 0., atol=2e-8)
    np.testing.assert_allclose(result['moment_balance'], 0., atol=2e-8)
    assert result['structural_operator'] == COUPLED_POLICY
    assert result['equilibrium_state']['identity']['structural_operator'] == COUPLED_POLICY
    assert 'launch' not in result['equilibrium_state']


def test_solve_rigid_limit_has_exact_jig_shape_and_balanced_airloads():
    m = model(rigid=True, mass=False)
    result = solve_source_coupled(m, condition(), panels=4, gravity=[0.,0.,0.])
    assert_balanced(result)
    for row in result['nodes']:
        np.testing.assert_allclose(row['position'], m.beams[0].position(row['t']), atol=3e-10)
        np.testing.assert_allclose(row['rotation'], np.eye(3), atol=3e-10)
    assert np.linalg.norm(result['surface_force']) > .1
    for element in result['elements']:
        np.testing.assert_allclose(element['strain'], 0., atol=3e-12)
        np.testing.assert_allclose(element['curvature_change'], 0., atol=3e-12)


def test_solve_finite_sections_preserves_mean_resultants_and_translation_strain():
    result = solve_source_coupled(model(), condition(), panels=4, gravity=[1.,-2.,-10.])
    assert_balanced(result)
    assert 1e-6 < result['max_displacement'] < .1
    differences = []
    for element, compact in zip(result['elements'], result['source_discrete_elements']):
        a,b = element['endpoint_traces']
        transform = np.asarray(compact['transform_average'])
        force = (np.asarray(a['force'])+b['force'])/2
        moment = (np.asarray(a['moment'])+b['moment'])/2
        np.testing.assert_allclose(transform@force, compact['force_local'], atol=2e-13)
        np.testing.assert_allclose(transform@moment, compact['moment_local'], atol=2e-13)
        np.testing.assert_allclose(element['strain'], compact['translation_strain'], atol=2e-14)
        differences.append(abs(compact['axial_strain']-element['axial_strain_tension']))
    assert max(differences) > 1e-9
