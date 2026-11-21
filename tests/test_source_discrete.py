"""Analytic limits and conservation for the opt-in source static operator.

These small synthetic beams test the selected equations, not historical ASWING
parity. No archived response or experimental data define an expected value.
"""
from copy import deepcopy

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from openswing.aero import AnalysisError, FlightCondition
from openswing.asw import parse_asw
from openswing.equilibrium_state import capture, identity, restore
from openswing.inertia import Motion
from openswing.network import StaticNetwork
from openswing.source_discrete import SourceDiscreteNetwork, STRUCTURAL_POLICY, solve_source_discrete
from openswing.structured_static import jacobian


def aircraft(extra='', attachments='Ground\n1 1 0\nEnd\n', stiffness=None):
    """Offset t domain prevents implicit mirroring; s=t-1 spans [0,2]."""
    stiffness = stiffness or 't EA EIcc GJ EInn\n1 1000 0 0 0\n3 1000 0 0 0\n'
    return parse_asw('Name\nSource-discrete analytic tests\nEnd\n'
                     'Unit\nL 1 m\nT 1 s\nF 1 N\nEnd\n'
                     'Constant\n10 1.225 340\nEnd\nReference\n2 1 2\nEnd\n'
                     + attachments + 'Beam 1\nStraight beam\nt x y z chord\n1 0 0 0 .2\n3 0 2 0 .2\n'
                     + stiffness + extra + 'End\n')


def grid(n=4):
    return {'default': n, 'beams': {'1': {'nodes': np.linspace(1., 3., n+1).tolist()}}}


def network(model=None, panels=None, gravity=(0., 0., 0.), loads=(), **kwargs):
    return SourceDiscreteNetwork(aircraft() if model is None else model,
                                 grid() if panels is None else panels, None, gravity, loads, **kwargs)


def assert_balanced(result):
    assert result['residual'] < 1e-10
    np.testing.assert_allclose(result['force_balance'], 0, atol=2e-9)
    np.testing.assert_allclose(result['moment_balance'], 0, atol=2e-9)
    assert result['structural_operator'] == STRUCTURAL_POLICY
    assert result['equilibrium_state']['identity']['structural_operator'] == STRUCTURAL_POLICY
    assert 'launch' not in result['equilibrium_state']


def test_finite_axial_extension_is_exact_and_exports_authoritative_strain():
    result = solve_source_discrete(aircraft(), panels=grid(), gravity=[0, 0, 0],
                                   loads=[dict(beam=1, t=3, force=[0, 10, 0])])
    assert_balanced(result)
    positions = np.array([n['position'] for n in result['nodes']])
    s = np.linspace(0., 2., 5)
    np.testing.assert_allclose(positions, np.c_[0*s, 1.01*s, 0*s], atol=2e-10)
    np.testing.assert_allclose(result['support_force'], [0, -10, 0], atol=2e-10)
    for e in result['source_discrete_elements']:
        assert e['axial_strain'] == pytest.approx(.01, abs=2e-12)
        np.testing.assert_allclose(e['curvature_change'], 0, atol=2e-12)


@pytest.mark.parametrize('axis,stiffness,moment', [
    (0, 't EA EIcc GJ EInn\n1 1000 100 0 0\n3 1000 100 0 0\n', 20.),
    (1, 't EA EIcc GJ EInn\n1 1000 0 80 0\n3 1000 0 80 0\n', 12.),
])
def test_pure_moment_matches_exact_discrete_bending_or_torsion(axis, stiffness, moment):
    m = aircraft(stiffness=stiffness)
    load = np.eye(3)[axis]*moment
    result = solve_source_discrete(m, panels=grid(), gravity=[0, 0, 0],
                                   loads=[dict(beam=1, t=3, moment=load.tolist())])
    assert_balanced(result)
    s = np.linspace(0., 2., 5)
    angle = s*moment/(100. if axis == 0 else 80.)
    frames = Rotation.from_rotvec(angle[:, None]*np.eye(3)[axis]).as_matrix()
    # Eq48 exactly integrates the endpoint tangent trapezoid, not a circular
    # arc at finite mesh width. This distinguishes the source and SO(3) laws.
    increments = (frames[:-1, :, 1]+frames[1:, :, 1])*.25
    expected = np.vstack([np.zeros(3), np.cumsum(increments, axis=0)])
    np.testing.assert_allclose([n['position'] for n in result['nodes']], expected, atol=3e-10)
    np.testing.assert_allclose([n['rotation'] for n in result['nodes']], frames, atol=3e-10)
    np.testing.assert_allclose(result['support_moment'], -load, atol=3e-9)
    if axis == 0:
        continuum_tip = [0, np.sin(angle[-1])/.2, (1-np.cos(angle[-1]))/.2]
        assert np.linalg.norm(expected[-1]-continuum_tip) > 1e-4


@pytest.mark.parametrize('rigid_c', [False, True])
def test_coupled_bending_uses_inverse_averaged_stiffness_and_arithmetic_frame(rigid_c):
    a = np.array([[100., 10., 4.], [10., 80., 3.], [4., 3., 120.]])
    b = np.array([[140., 6., 2.], [6., 100., 5.], [2., 5., 160.]])
    if rigid_c:
        a[0, 0] = b[0, 0] = np.inf
    def row(t, e, ea):
        cc = 0 if np.isinf(e[0, 0]) else e[0, 0]
        return f'{t} {ea} {cc} {e[1,1]} {e[2,2]} {e[0,1]} {e[0,2]} {e[1,2]}\n'
    stiffness = 't EA EIcc GJ EInn EIcs EIcn EIsn\n'+row(1, a, 700)+row(3, b, 1300)
    n = network(aircraft(stiffness=stiffness), panels=grid())
    x = np.zeros(n.size)
    rotations = np.array([[.18, 0, 0], [0, .23, 0], [0, 0, -.16],
                          [.1, -.1, .08], [-.06, .09, .12]])
    x[:6*n.nn].reshape(n.nn, 6)[:, 3:] = rotations
    base = n.residual(x)
    moment = np.array([2., 3., 4.])
    x[6*n.nn:6*(n.nn+n.ne)].reshape(n.ne, 6)[:, 3:] = moment/(n.F*n.L)
    difference = (n.residual(x)-base)[:6*n.ne].reshape(n.ne, 6)
    frames = Rotation.from_rotvec(rotations).as_matrix()
    af, bf = np.where(np.isfinite(a), a, 0), np.where(np.isfinite(b), b, 0)
    endpoint = [(1-f)*af+f*bf for f in np.linspace(0., 1., 5)]
    if rigid_c:
        for e in endpoint:
            e[0, 0] = np.inf
    for e in range(n.ne):
        transform = (frames[e].T+frames[e+1].T)/2
        average = (endpoint[e]+endpoint[e+1])/2
        expected = np.zeros(3)
        active = [1, 2] if rigid_c else [0, 1, 2]
        expected[active] = -.5*np.linalg.solve(average[np.ix_(active, active)], (transform@moment)[active])
        np.testing.assert_allclose(difference[e, 3:], expected, rtol=2e-12, atol=2e-14)
        np.testing.assert_allclose(difference[e, :3], 0, atol=2e-14)
        if not rigid_c:
            wrong = -.25*(np.linalg.solve(endpoint[e], transform@moment)
                          + np.linalg.solve(endpoint[e+1], transform@moment))
            assert np.linalg.norm(expected-wrong) > 1e-6


def loaded_model(weight=3.):
    extra = 't mg\n1 2\n3 6\n'
    attachments = f'Ground\n1 1 0\nEnd\nWeight\n1 2 .3 1 .2 {weight}\nEnd\n'
    return aircraft(extra=extra, attachments=attachments)


NODE_LOADS = [dict(beam=1, t=2, force=[0, 0, 4], moment=[2, 0, 0])]


def test_endpoint_gravity_and_point_pylon_preserve_force_moment_and_jumps():
    m = loaded_model()
    result = solve_source_discrete(m, panels=grid(), loads=NODE_LOADS)
    assert_balanced(result)
    # Four trapezoidal-density intervals have weights 1.25,1.75,2.25,2.75.
    # Symmetric endpoint transfer puts their moments at y=.25,.75,1.25,1.75.
    np.testing.assert_allclose(result['applied_force'], [0, 0, -7], atol=2e-10)
    np.testing.assert_allclose(result['support_force'], [0, 0, 7], atol=2e-10)
    np.testing.assert_allclose(result['applied_moment'], [-6.25, .9, 0], atol=2e-9)
    np.testing.assert_allclose(result['support_moment'], [6.25, -.9, 0], atol=2e-9)
    n = network(m, gravity=None, loads=NODE_LOADS)
    x = restore(n, result['equilibrium_state'])
    residual, d = n.residual(x, detail=True)
    assert np.max(abs(residual)) < 1e-10
    np.testing.assert_array_equal(d['element_forces'][:, 0], d['element_forces'][:, 1])
    np.testing.assert_array_equal(d['element_moments'], 0)
    node = n.node(1, 2)
    left = int(np.flatnonzero(n.b == node)[0]); right = int(np.flatnonzero(n.a == node)[0])
    delta = d['r'][n.b]-d['r'][n.a]
    fl = d['N'][left]-d['element_forces'][left, 1]
    fr = d['N'][right]+d['element_forces'][right, 0]
    ml = d['M'][left]-np.cross(delta[left], d['N'][left])/2
    mr = d['M'][right]+np.cross(delta[right], d['N'][right])/2
    np.testing.assert_allclose(fl-fr, [0, 0, 1], atol=2e-9)
    np.testing.assert_allclose(ml-mr, [2, .9, 0], atol=2e-9)


def test_signed_point_weight_and_rotating_pylon_are_static_loads():
    n = network(loaded_model(-3.), gravity=None, loads=NODE_LOADS, allow_signed_point_weights=True)
    x = np.zeros(n.size)
    i = n.node(1, 2)
    rotation = np.array([.2, -.1, .3])
    x[:6*n.nn].reshape(n.nn, 6)[i, 3:] = rotation
    _, data = n.residual(x, detail=True)
    force = np.array([0., 0., 3.])
    arm = Rotation.from_rotvec(rotation).apply([.3, 0, .2])
    np.testing.assert_allclose(data['moment'][i], np.cross(arm, force)+[2, 0, 0], atol=2e-14)
    np.testing.assert_allclose(data['force'].sum(axis=0), [0, 0, -1], atol=2e-14)
    assert n.inertia_model.signed_point_weights == [1]


def test_sparse_and_full_jacobians_bypass_old_analytic_mechanics(monkeypatch):
    import openswing.mechanical_tangent as mechanical
    original = mechanical.network_mechanical_columns
    calls = []
    def poisoned_midpoint_rows(n, *args, **kwargs):
        matrix, report = original(n, *args, **kwargs)
        matrix = matrix.tolil()
        matrix[:6*n.ne, :] = 12345.
        calls.append(True)
        return matrix.tocsc(), report
    # Source assembly may share nodal balances/reactions, but must replace
    # every midpoint compatibility row with its endpoint-average law.
    monkeypatch.setattr(mechanical, 'network_mechanical_columns', poisoned_midpoint_rows)
    n = network(loaded_model(), panels=grid(), gravity=None, loads=NODE_LOADS)
    x = np.random.default_rng(848).normal(0., .001, n.size)
    before = n.residual(x, .6)
    grouped, counts = jacobian(n, x, .6)
    ungrouped, reference_counts = jacobian(n, x, .6, grouped=False)
    full = n.jacobian(x, .6, _direct_geometry=True)
    assert len(calls) == 2 and n.analytic_mechanics is False
    np.testing.assert_allclose(grouped.toarray(), ungrouped.toarray(), rtol=2e-12, atol=2e-10)
    np.testing.assert_allclose(full, ungrouped.toarray(), rtol=2e-12, atol=2e-10)
    assert counts['evaluations'] < reference_counts['evaluations']
    assert n.iteration_fields is None and n.tangent_influences is None
    np.testing.assert_array_equal(n.residual(x, .6), before)


def test_structural_policy_state_identity_is_checked_in_both_directions():
    m = aircraft()
    source = network(m)
    standard = StaticNetwork(m, grid(), None, [0, 0, 0], [])
    x = np.zeros(source.size)
    candidate = capture(source, x, include_launch=False)
    original = capture(standard, x)
    assert identity(source)['structural_operator'] == STRUCTURAL_POLICY
    assert identity(standard).get('structural_operator') != STRUCTURAL_POLICY
    np.testing.assert_array_equal(restore(network(m), candidate), x)
    np.testing.assert_array_equal(restore(standard, original), x)
    with pytest.raises(AnalysisError, match='match|policy|operator'):
        restore(standard, candidate)
    with pytest.raises(AnalysisError, match='match|policy|operator'):
        restore(source, original)
    tampered = deepcopy(candidate)
    tampered['identity']['structural_operator'] = 'unknown-structural-operator'
    with pytest.raises(AnalysisError, match='match|policy|operator'):
        restore(source, tampered)


@pytest.mark.parametrize('name,value', [('Cea', .1), ('Ccg', .1), ('DNcg', .1),
                                       ('GKc', 100), ('GKn', 100)])
def test_forbidden_interior_properties_cannot_hide_between_mesh_nodes(name, value):
    extra = f't {name}\n1 0\n1.5 0\n2 0\n2.25 {value}\n2.5 0\n3 0\n'
    if name in ('GKc', 'GKn'):
        # Split the finite-shear island from the zero-as-infinity intervals:
        # an unconstrained cubic through an isolated peak can overshoot below
        # zero and fail the parent's positivity guard before reaching scope.
        extra = f't {name}\n1 0\n2 0\n2 0\n2.25 {value}\n2.5 0\n2.5 0\n3 0\n'
    with pytest.raises(AnalysisError, match='zero|shear'):
        network(aircraft(extra=extra), panels=grid())


def test_aero_motion_and_dynamic_rates_are_rejected():
    m = aircraft()
    with pytest.raises(AnalysisError, match='airflow|aerodynamic'):
        SourceDiscreteNetwork(m, grid(), FlightCondition(), [0, 0, 0], [])
    with pytest.raises(AnalysisError, match='motion|dynamic'):
        network(m, motion=Motion(rates=np.array([.01, 0, 0])))
    n = network(m)
    x = np.zeros(n.size)
    with pytest.raises(AnalysisError, match='dynamic|unsteady'):
        n.residual(x, elastic_motion=tuple(np.zeros((n.nn, 3)) for _ in range(4)))
    with pytest.raises(AnalysisError, match='dynamic|unsteady'):
        n.residual(x, circulation_rate=np.zeros(0))


def test_fuselage_chart_is_not_silently_treated_as_surface_chart():
    text = aircraft().dumps().replace('t x y z chord\n1 0 0 0 .2\n3 0 2 0 .2',
                                     't x y z\n1 0 0 0\n3 0 2 0')
    body = network(parse_asw(text))
    assert np.all(body.source_fuselage)
    np.testing.assert_allclose(body.residual(np.zeros(body.size)), 0., atol=1e-14)
