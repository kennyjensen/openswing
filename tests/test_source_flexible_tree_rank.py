"""Production scope and failure controls for the source-tree nullspace proof."""
from copy import deepcopy

import numpy as np
import pytest
from scipy.sparse import csc_matrix

from openswing.aero import AnalysisError, FlightCondition
from openswing.asw import parse_asw
from openswing.joints import HingeLaw
from openswing.source_airflow import SourceAirflowNetwork
from openswing.source_coupled import SourceCoupledNetwork
from openswing.source_discrete import SourceSectionNetwork
from openswing.source_dynamics import SourceDynamicNetwork, SourceMovingNetwork
from openswing.source_initial_rank import source_tree_initial_certificate
from openswing.structured_static import StructuredMatrix, check_initial_rank
from test_source_flexible_zero_load_oracle import setup, variation, oracle


def proof(net, state=None, factor=0.):
    return source_tree_initial_certificate(net, np.zeros(net.size) if state is None else state, factor)


@pytest.mark.parametrize('cls', [SourceSectionNetwork, SourceCoupledNetwork,
    SourceDynamicNetwork, SourceMovingNetwork, SourceAirflowNetwork])
def test_each_source_policy_matches_independent_zero_rate_first_variation(cls):
    base, properties = setup(airflow=False, offsets=True)
    flow = FlightCondition(speed=10., alpha=5., beta=4., mach=0., freeze_influences=True)
    condition = flow if cls in (SourceCoupledNetwork, SourceAirflowNetwork) else None
    kwargs = dict(steady_trim=True) if cls is SourceAirflowNetwork else {}
    net = cls(base.model, 4, condition, [0., 0., 9.81], [], **kwargs)
    report = proof(net)
    assert report['certified'] and report['finite_flexible_compliance_allowed']
    assert report['numerical_condition_bound'] is False
    assert report['cold_equilibrium_claim'] is False
    assert report['loaded_stability_claim'] is False
    assert report['statics_unknowns'] == report['pose_unknowns'] == 6*net.nn
    rng = np.random.default_rng(423)
    for step in (2e-6, 7e-7):
        direction = rng.normal(size=net.size); direction /= max(abs(direction))
        actual = (net.residual(step*direction, 0.)-net.residual(-step*direction, 0.))[:net.gamma_start]/(2*step)
        np.testing.assert_allclose(actual, variation(net, properties, direction[:net.gamma_start]), atol=8e-9, rtol=3e-8)
    result = check_initial_rank(net, np.zeros(net.size))
    assert result['method'] == 'source flexible-tree rank certificate'
    assert result['circulation_rank']['threshold'] == 1e-10


def test_retained_production_matrix_matches_independent_oracle_and_avoids_dense_rank(monkeypatch):
    import openswing.structured_static as structured
    net, properties = setup(offsets=True, rigid_tips=True)
    def forbidden(*args, **kwargs):
        pytest.fail('Scoped source tree must not rebuild or factor the mechanical rank matrix')
    monkeypatch.setattr(net, 'jacobian', forbidden)
    monkeypatch.setattr(structured, 'mechanical_rank_certificate', forbidden)
    monkeypatch.setattr(structured, 'mechanical_svd_certificate', forbidden)
    report, matrix = check_initial_rank(net, np.zeros(net.size), retain_matrix=True)
    assert report['method'] == 'source flexible-tree rank certificate'
    np.testing.assert_allclose(matrix.mechanical.toarray(), oracle(net, properties), atol=2e-7, rtol=2e-7)
    assert not np.any(matrix.force_circulation)


@pytest.mark.parametrize('kind', ['free_tips', 'partial_ground', 'duplicate_ground', 'rigid_cycle', 'hinge_cycle', 'released_joint'])
def test_mechanisms_and_redundant_reactions_reach_numerical_rejection(kind):
    base, _ = setup(airflow=False)
    model = base.model
    if kind == 'free_tips':
        model.records['joint'] = []; model.records['jangle'] = []
    elif kind == 'partial_ground': model.records['ground'][0][-1] = 1
    elif kind == 'duplicate_ground': model.records['ground'].append(model.records['ground'][0].copy())
    elif kind == 'released_joint':
        model.records['joint'][0][-1] = 1
        model.records['jangle'] = [r for r in model.records['jangle'] if r['header'][0] != 1]
    else:
        if kind == 'rigid_cycle':
            for row in model.records['joint']: row[-1] = 0
            model.records['jangle'] = []
        model.records['joint'].append(model.records['joint'][0].copy())
        if kind == 'hinge_cycle':
            law = deepcopy(model.records['jangle'][0]); law['header'][0] = 3
            model.records['jangle'].append(law)
    net = SourceSectionNetwork(model, 4, None, [0., 0., 0.], [])
    assert not proof(net)['certified']
    with pytest.raises(AnalysisError, match='mechanism or redundant'):
        check_initial_rank(net, np.zeros(net.size))


@pytest.mark.parametrize('kind', ['pose', 'rotation', 'internal', 'reaction', 'factor', 'chart',
    'motion', 'step', 'jig_curvature', 'unequal_frames', 'nonidentity_frames', 'nonfinite_compliance',
    'nonfinite_offset', 'invalid_length', 'nonpositive_scale', 'nonfinite_state', 'complex_state',
    'state_layout', 'operator', 'negative_hinge', 'intercept', 'interior_parent', 'offset_hinge'])
def test_unproved_context_declines_without_tolerance_relaxation(kind):
    net, _ = setup()
    state = np.zeros(net.size); factor = 0.
    if kind == 'pose': state[0] = 1e-30
    elif kind == 'rotation': state[3] = 1e-30
    elif kind == 'internal': state[6*net.nn] = 1e-30
    elif kind == 'reaction': state[6*(net.nn+net.ne)] = 1e-30
    elif kind == 'factor': factor = 1e-30
    elif kind == 'chart': net.constraints[-1]['angle_chart'] = 1e-30
    elif kind == 'motion': net.motion.rates[0] = 1e-30
    elif kind == 'step': net.offa[0, 0] = 1e-30
    elif kind == 'jig_curvature': net.source_jig_curvature[0, 0] = 1e-30
    elif kind == 'unequal_frames': net.R0b[0, 0, 0] = np.nextafter(1., np.inf)
    elif kind == 'nonidentity_frames': net.R0a[:] = net.R0b[:] = np.diag([-1., 1., -1.])
    elif kind == 'nonfinite_compliance': net.source_compliance[0, 0, 0] = np.inf
    elif kind == 'nonfinite_offset': net.source_h[0, 0, 0] = np.nan
    elif kind == 'invalid_length': net.ds[0] = 0.
    elif kind == 'nonpositive_scale': net.F = 0.
    elif kind == 'nonfinite_state': state[-1] = np.nan
    elif kind == 'complex_state': state = state.astype(complex)
    elif kind == 'state_layout': net.operating_start += 1
    elif kind == 'operator': net.structural_operator = 'unreviewed-source-operator'
    elif kind == 'negative_hinge':
        record = deepcopy(net.model.records['jangle'][0])
        record['curve'] = np.array(record['curve']); record['curve'][:, 1] *= -1
        net.constraints[1]['law'] = HingeLaw(record)
    elif kind == 'intercept': net.constraints[1]['law'].zero_angle = 1e-30
    elif kind == 'interior_parent': net.constraints[1]['a'] = net.a[1]
    else: net.rj[net.constraints[1]['b'], 0] += 1e-30
    report = proof(net, state, factor)
    assert not report['certified']
    if kind == 'negative_hinge': assert 'nonpositive' in report['reason']


def test_unknown_subclass_cannot_inherit_reviewed_equations():
    class ChangedNetwork(SourceSectionNetwork): pass
    base, _ = setup(airflow=False)
    net = ChangedNetwork(base.model, 4, None, [0., 0., 0.], [])
    assert not proof(net)['certified']


@pytest.mark.parametrize('kind', ['zero_circulation_rank', 'small_circulation_rank', 'force_coupling'])
def test_circulation_rank_and_force_block_cannot_be_bypassed(monkeypatch, kind):
    import openswing.structured_static as structured
    net, _ = setup()
    assert proof(net)['certified']
    nm, ng = net.gamma_start, net.ng
    flow = np.eye(ng); force = np.zeros((nm, ng))
    if kind == 'zero_circulation_rank': flow[:] = 0.
    elif kind == 'small_circulation_rank': flow[:2, :2] = [[1., 1.], [0., 5e-11]]
    else: force[0, 0] = 1e-30
    matrix = StructuredMatrix(csc_matrix(np.eye(nm)), force, csc_matrix((ng, nm)), flow)
    monkeypatch.setattr(structured, 'jacobian', lambda *args, **kwargs: (matrix, {}))
    monkeypatch.setattr(net, 'jacobian', lambda *args, **kwargs: np.zeros((net.size, net.size)))
    with pytest.raises(AnalysisError, match='mechanism or redundant'):
        check_initial_rank(net, np.zeros(net.size))


def test_valid_rotated_frame_retains_numerical_fallback():
    net, _ = setup(airflow=False)
    net.R0a[:] = net.R0b[:] = np.array([[0., 0., 1.], [0., 1., 0.], [-1., 0., 0.]])
    assert not proof(net)['certified']
    assert check_initial_rank(net, np.zeros(net.size))['method'] != 'source flexible-tree rank certificate'


def test_source_rest_defect_is_not_silently_accepted_as_equilibrium():
    net, _ = setup(airflow=False, rigid_tips=True)
    net.ds *= np.linspace(.8, 1.2, net.ne)
    report = proof(net)
    assert report['certified'] and report['maximum_cold_translation_defect'] > 0.
    assert report['cold_equilibrium_claim'] is False
    assert max(abs(net.residual(np.zeros(net.size), 0.))) > .01


@pytest.mark.parametrize('body_beams', [(1,), (1, 2, 3)])
def test_actual_body_and_mixed_material_charts_match_the_same_independent_variation(body_beams):
    base, properties = setup(airflow=False, offsets=True)
    source = base.model.dumps()
    for index in body_beams:
        old = f'Beam {index} 1\nSynthetic source beam\nt x y z chord'
        new = f'Beam {index} 1\nSynthetic source beam\nt x y z radius'
        assert old in source; source = source.replace(old, new)
    net = SourceSectionNetwork(parse_asw(source, beam_interpolation='drela-segspl-v1'), 4, None, [0., 0., 0.], [])
    assert sum(net.source_fuselage) == 4*len(body_beams)
    assert proof(net)['certified']
    rng = np.random.default_rng(209)
    for step in (2e-6, 7e-7):
        direction = rng.normal(size=net.size); direction /= max(abs(direction))
        actual = (net.residual(step*direction, 0.)-net.residual(-step*direction, 0.))/(2*step)
        np.testing.assert_allclose(actual, variation(net, properties, direction), atol=8e-9, rtol=3e-8)


def test_nonzero_circulation_seed_preserves_scoped_mechanics():
    net, _ = setup()
    state = np.zeros(net.size)
    state[net.gamma_start:net.operating_start] = np.linspace(.1, .4, net.ng)
    assert proof(net, state)['certified']
