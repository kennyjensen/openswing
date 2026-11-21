"""Analytic source-policy arc metrics; no airflow or equilibrium solves.

Expectations come from rigid length conservation and prescribed uniform
axial/shear strain, not archived ASWING outputs or an inverted implementation.
"""
from copy import deepcopy
from dataclasses import fields

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from openswing.aero import AnalysisError, FlightCondition
from openswing.asw import parse_asw
from openswing.network import StaticNetwork
from openswing.equilibrium_state import capture, identity, matching_identity, restore
from openswing.source_coupled import SourceCoupledNetwork
from openswing.source_discrete import SourceDiscreteNetwork, SourceSectionNetwork, source_output_metadata
from openswing.source_dynamics import SourceDynamicNetwork, SourceMovingNetwork
from openswing.source_quiescent import SourceQuiescentNetwork


def model(curved=False):
    coordinates = ('1 0 0 0 .3\n2 .12 1 .18 .3\n3 .45 2 .55 .3\n'
                   if curved else '1 0 0 0 .3\n3 0 2 0 .3\n')
    return parse_asw('Name\nSource arc metric\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\n'
        'Constant\n10 1.2 340\nEnd\nReference\n.6 .3 2\nEnd\nGround\n1 1 0\nEnd\n'
        'Beam 1\nRigid lifting beam\nt x y z chord\n'+coordinates+'End\n')


def network(cls=SourceDiscreteNetwork, *, curved=False, panels=4):
    kwargs = {'quiescent_density': 1.2} if cls is SourceQuiescentNetwork else {}
    condition = FlightCondition(speed=8., alpha=0., mach=0.) if cls is SourceCoupledNetwork else None
    return cls(model(curved), panels, condition, [0., 0., 0.], [], **kwargs)


def prescribed(n, q=(0., 1., 0.), rotations=None):
    """Integrate Eq.48 directly with an independently prescribed strain."""
    Q = np.broadcast_to(np.eye(3), (n.nn, 3, 3)).copy() if rotations is None else rotations
    Ra, Rb = Q[n.a]@n.R0a, Q[n.b]@n.R0b
    q = np.broadcast_to(np.asarray(q), (n.ne, 3))
    increments = .5*(np.einsum('nij,nj->ni', Ra, q)+np.einsum('nij,nj->ni', Rb, q))*n.ds[:, None]
    positions = np.vstack([np.zeros(3), np.cumsum(increments, axis=0)])+n.rj[0]
    return positions, Q


def deformed(n, r, Q):
    return n.deformed_meshes(r, Q, n.geometry(r, Q))


def all_lengths(meshes):
    return np.concatenate([m.length for m in meshes])


def assert_parent_fields_preserved(n, r, Q, actual):
    reference = StaticNetwork.deformed_meshes(n, r, Q, n.geometry(r, Q))
    for result, original, material in zip(actual, reference, n.meshes):
        for field in fields(result):
            if field.name == 'length':
                continue
            a, b = getattr(result, field.name), getattr(original, field.name)
            if isinstance(a, np.ndarray):
                np.testing.assert_array_equal(a, b)
            else:
                assert a is b or a == b
        np.testing.assert_array_equal(result.theta, material.theta)


def test_curved_rigid_zero_strain_preserves_material_arc_and_complete_zero_load_residual():
    n = network(curved=True)
    r, Q = prescribed(n)
    assert np.max(np.linalg.norm(r-n.rj, axis=1)) > 1e-3
    old = StaticNetwork.deformed_meshes(n, r, Q, n.geometry(r, Q))
    assert np.max(abs(all_lengths(old)/n.ds-1)) > 1e-4
    actual = deformed(n, r, Q)
    np.testing.assert_allclose(all_lengths(actual), n.ds, rtol=2e-14, atol=2e-15)
    assert_parent_fields_preserved(n, r, Q, actual)
    state = np.zeros(n.size)
    state[:6*n.nn].reshape(n.nn, 6)[:, :3] = (r-n.rj)/n.L
    residual, data = n.residual(state, detail=True)
    assert np.max(abs(residual)) < 2e-12
    np.testing.assert_array_equal(data['source_discrete']['axial_strain'], 0.)


@pytest.mark.parametrize('q', [(0., 1.2, 0.), (0., .85, 0.), (.3, 1.1, -.2)])
def test_uniform_axial_and_shear_strain_has_analytic_arc_under_differing_frames(q):
    n = network(SourceSectionNetwork, curved=True)
    u = np.linspace(0., 1., n.nn)
    Q = Rotation.from_rotvec(np.c_[.7*u, -.3*u, .2*u*u]).as_matrix()
    r, Q = prescribed(n, q, Q)
    actual = deformed(n, r, Q)
    np.testing.assert_allclose(all_lengths(actual), n.ds*np.linalg.norm(q), rtol=3e-14, atol=3e-15)
    assert_parent_fields_preserved(n, r, Q, actual)
    # Rigid observer rotation and translation cannot change physical length.
    observer = Rotation.from_rotvec([.4, -.6, .3]).as_matrix()
    moved = deformed(n, r@observer.T+np.array([3., -2., .5]), observer@Q)
    np.testing.assert_allclose(all_lengths(moved), all_lengths(actual), rtol=3e-14, atol=3e-15)


def test_zero_strain_finite_bend_is_not_chord_contraction():
    n = network()
    angles = np.linspace(0., 1.2, n.nn)
    Q = Rotation.from_rotvec(np.c_[angles, 0*angles, 0*angles]).as_matrix()
    r, Q = prescribed(n, rotations=Q)
    chord_lengths = np.linalg.norm(r[n.b]-r[n.a], axis=1)
    np.testing.assert_allclose(chord_lengths, n.ds*np.cos(np.diff(angles)/2), rtol=2e-14)
    assert np.max(n.ds-chord_lengths) > .001
    np.testing.assert_allclose(all_lengths(deformed(n, r, Q)), n.ds, rtol=2e-14)


@pytest.mark.parametrize('cls', [SourceDiscreteNetwork, SourceSectionNetwork,
    SourceCoupledNetwork, SourceDynamicNetwork, SourceMovingNetwork, SourceQuiescentNetwork])
def test_source_subclasses_share_metric_without_changing_material_coordinates(cls):
    n = network(cls, curved=True)
    r, Q = prescribed(n)
    actual = deformed(n, r, Q)
    np.testing.assert_allclose(all_lengths(actual), n.ds, rtol=2e-14, atol=2e-15)
    assert_parent_fields_preserved(n, r, Q, actual)
    metadata = source_output_metadata(n)
    assert 'constant-average-strain' in metadata['output_scope']['deformed_interval_measure']
    assert 'nonuniform endpoint' in metadata['output_scope']['deformed_interval_measure']


def test_straight_jig_and_original_non_source_chord_measure_are_preserved():
    source = network()
    Q = np.broadcast_to(np.eye(3), (source.nn, 3, 3)).copy()
    np.testing.assert_allclose(all_lengths(deformed(source, source.rj, Q)), source.ds, rtol=2e-14)
    ordinary = network(StaticNetwork)
    angles = np.linspace(0., 1.2, ordinary.nn)
    Q = Rotation.from_rotvec(np.c_[angles, 0*angles, 0*angles]).as_matrix()
    r, Q = prescribed(ordinary, rotations=Q)
    expected = ordinary.ds*np.linalg.norm(r[ordinary.b]-r[ordinary.a], axis=1)/np.linalg.norm(ordinary.p0b-ordinary.p0a, axis=1)
    np.testing.assert_array_equal(all_lengths(deformed(ordinary, r, Q)), expected)
    assert np.max(abs(expected/ordinary.ds-1)) > .001


@pytest.mark.parametrize('value', [np.nan, np.inf, -np.inf])
@pytest.mark.parametrize('part', [0, 1, 2, 3])
def test_nonfinite_endpoint_positions_or_frames_are_rejected(value, part):
    n = network()
    r, Q = prescribed(n)
    geometry = list(n.geometry(r, Q))
    geometry[part] = geometry[part].copy()
    geometry[part].flat[0] = value
    with pytest.raises(AnalysisError, match='finite endpoint'):
        n.deformed_meshes(r, Q, tuple(geometry))


@pytest.mark.parametrize('ratio,accepted', [(2e-10, True), (.5e-10, False), (0., False)])
def test_averaged_transform_numerical_rank_boundary(ratio, accepted):
    n = network()
    vectors = np.zeros((n.nn, 3))
    vectors[-1, 0] = 2*np.arccos(ratio)
    Q = Rotation.from_rotvec(vectors).as_matrix()
    r, Q = prescribed(n, rotations=Q)
    if accepted:
        np.testing.assert_allclose(all_lengths(deformed(n, r, Q)), n.ds, rtol=3e-14, atol=3e-15)
    else:
        with pytest.raises(AnalysisError, match='singular or ill-conditioned averaged endpoint transform'):
            deformed(n, r, Q)


def test_collapsed_interval_cannot_report_positive_material_length():
    n = network()
    r, Q = prescribed(n, q=(0., 0., 0.))
    with pytest.raises(AnalysisError, match='finite and positive'):
        deformed(n, r, Q)


@pytest.mark.parametrize('cls', [SourceDiscreteNetwork, SourceSectionNetwork,
    SourceCoupledNetwork, SourceDynamicNetwork, SourceMovingNetwork, SourceQuiescentNetwork])
def test_source_saved_identity_declares_metric_and_roundtrips(cls):
    n = network(cls)
    state = np.zeros(n.size)
    saved = capture(n, state, include_launch=False)
    assert saved['identity']['deformed_interval_measure'] == 'drela-eq48-average-strain-norm-v1'
    np.testing.assert_array_equal(restore(n, saved), state)
    for previous in (None, 'chord-ratio-v0'):
        old = deepcopy(saved)
        if previous is None:
            old['identity'].pop('deformed_interval_measure')
        else:
            old['identity']['deformed_interval_measure'] = previous
        assert not matching_identity(old['identity'], identity(n))
        with pytest.raises(AnalysisError, match='interval measure.*[Rr]ecompute'):
            restore(n, old)


def test_ordinary_saved_identity_remains_untagged_and_roundtrips():
    n = network(StaticNetwork)
    state = np.zeros(n.size)
    saved = capture(n, state, include_launch=False)
    assert 'deformed_interval_measure' not in saved['identity']
    np.testing.assert_array_equal(restore(n, saved), state)
