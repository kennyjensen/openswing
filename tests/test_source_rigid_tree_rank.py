"""Independent zero-load rank oracles for source rigid trees.

These small synthetic networks never run equilibrium.  The oracle uses the
first variation of steady Eqs.48/54 and conservative Eqs.55/56 directly; it
never calls the production tangent or source constitutive helpers.  In
particular h is not assumed equal to the geometric chord.
"""
from copy import deepcopy

import numpy as np
import pytest
from scipy.sparse import csc_matrix

from openswing.aero import AnalysisError
from openswing.asw import parse_asw
from openswing.rigid_initial_rank import rigid_tree_initial_certificate
from openswing.source_coupled import SourceCoupledNetwork
from openswing.source_discrete import SourceDiscreteNetwork, SourceSectionNetwork
from openswing.source_dynamics import SourceDynamicNetwork, SourceMovingNetwork
from openswing.source_quiescent import SourceQuiescentNetwork
from openswing.structured_static import StructuredMatrix, check_initial_rank


STATIC_TYPES = (SourceDiscreteNetwork, SourceSectionNetwork, SourceCoupledNetwork)
AXIS = np.array([2., 1., 3.])/np.sqrt(14.)


def source(*, side='right', three=False):
    """Positive material coordinates prevent implicit zero-origin mirroring."""
    sides = ('right', 'left') if three else (side,)
    joints, laws, beams = [], [], []
    spans = [(-1., 1.)]
    for index, which in enumerate(sides, 2):
        right = which == 'right'
        spans.append((1., 3.) if right else (-3., -1.))
        joints.append(f'1 {index} {3 if right else 1} {1 if right else 3} 3')
        sign = 1 if right else -1
        laws.append(f'Jangle\n{index-1} 2 1 3\n-100 {-100*sign}\n100 {100*sign}\nEnd\n')
    for index, (lo, hi) in enumerate(spans, 1):
        beams.append(f'Beam {index} 1\nRigid synthetic beam\n'
            't x y z chord EIcc GJ EInn EA GKc GKn\n'
            f'1 0 {lo} 0 .2 0 0 0 0 0 0\n'
            f'3 0 {hi} 0 .2 0 0 0 0 0 0\nEnd\n')
    return ('Name\nSource rank oracle\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\n'
            'Constant\n10 1.2 340\nEnd\nReference\n1 .2 4\nEnd\n'
            'Ground\n1 2 0\nEnd\nJoint\n'+'\n'.join(joints)+'\nEnd\n'
            +''.join(laws)+''.join(beams))


def model(**kwargs):
    return parse_asw(source(**kwargs), beam_interpolation='drela-segspl-v1')


def network(cls=SourceSectionNetwork, **kwargs):
    return cls(model(**kwargs), 4, None, [0., 0., 0.], [])


def certificate(net, *, state=None, factor=0.):
    return rigid_tree_initial_certificate(net, np.zeros(net.size) if state is None else state, factor)


def require_rejection(net, fragment=None, **kwargs):
    report = certificate(net, **kwargs)
    assert report['certified'] is False
    if fragment is not None:
        assert fragment in report['reason']
    return report


def first_variation(net, delta):
    """Full independently assembled mixed linear system at the literal jig.

    The two source compatibility formulas are body/local forms of Eqs.48/54.
    Internal endpoint wrenches use the actual chord, including its half lever.
    The fixture's inverse hinge slopes are literal +/- pi/180 rad/(N m).
    """
    pose = delta[:6*net.nn].reshape(net.nn, 6)
    displacement, rotation = net.L*pose[:, :3], pose[:, 3:]
    internal = delta[6*net.nn:6*(net.nn+net.ne)].reshape(net.ne, 6)
    forces, moments = net.F*internal[:, :3], net.F*net.L*internal[:, 3:]
    reactions = delta[6*(net.nn+net.ne):net.gamma_start]
    compatibility = np.empty((net.ne, 6))
    nodal_force, nodal_moment = np.zeros((net.nn, 3)), np.zeros((net.nn, 3))
    for e, (a, b) in enumerate(net.ends):
        frame, length = net.R0a[e], net.ds[e]
        span = frame[:, 1]
        compatibility[e, :3] = (displacement[b]-displacement[a]
            -length/2*np.cross(rotation[a]+rotation[b], span))/net.L
        compatibility[e, 3:] = frame.T@(rotation[b]-rotation[a])
        chord = net.rj[b]-net.rj[a]
        half_lever = np.cross(chord, forces[e])/2
        nodal_force[a] += forces[e]
        nodal_force[b] -= forces[e]
        nodal_moment[a] += moments[e]+half_lever
        nodal_moment[b] += -moments[e]+half_lever
    constraints = []
    for c in net.constraints:
        a, b = c['a'], c['b']
        value = reactions[c['sl']]
        force, couple = net.F*value[:3], net.F*net.L*value[3:]
        nodal_force[a] += force
        nodal_moment[a] += couple
        if b is None:
            constraints.extend(displacement[a]/net.L)
            constraints.extend(rotation[a])
            continue
        chord = net.rj[b]-net.rj[a]
        nodal_force[b] -= force
        nodal_moment[b] -= couple
        nodal_moment[a] += np.cross(chord, force)
        constraints.extend((displacement[b]-displacement[a]-np.cross(rotation[a], chord))/net.L)
        relative = rotation[b]-rotation[a]
        if c['type'] == 3:
            e = c['element']
            edge = net.rj[net.b[e]]-net.rj[net.a[e]]
            trace_sign = -1 if c['end'] else 1
            trace = moments[e]+trace_sign*np.cross(edge, forces[e])/2
            literal_slope = (1 if c['end'] else -1)*np.pi/180
            relative = relative-literal_slope*np.dot(AXIS, trace)*AXIS
        else:
            assert c['type'] == 0
        constraints.extend(relative)
    return np.r_[compatibility.ravel(), (nodal_force/net.F).ravel(),
                 (nodal_moment/(net.F*net.L)).ravel(), constraints]


def oracle_matrix(net):
    identity = np.eye(net.size)
    return np.column_stack([first_variation(net, v) for v in identity])


def finite_difference_matrix(net, step=2e-6):
    identity = np.eye(net.size)
    return np.column_stack([(net.residual(step*v, 0.)-net.residual(-step*v, 0.))/(2*step)
                            for v in identity])


def assert_well_resolved(matrix):
    # This is an independent check only on modest-stiffness synthetic systems;
    # the production certificate makes no numerical conditioning guarantee.
    singular = np.linalg.svd(matrix, compute_uv=False)
    assert singular[-1] > 1e-7*singular[0]


@pytest.mark.parametrize('cls', STATIC_TYPES)
def test_exact_static_source_types_use_actual_rigid_source_law(cls):
    net = network(cls)
    report = certificate(net)
    assert report['certified']
    assert report['method'] == 'source grounded rigid-tree initial rank'
    assert report['source_scope']['cold_equilibrium_claim'] is False
    assert report['source_scope']['energy_hessian_claim'] is False
    assert report['rigid_bodies'] == 2
    assert report['positive_spring_dofs'] == 1
    assert report['numerical_condition_bound'] is False
    assert report['loaded_stability_claim'] is False
    assert net.analytic_mechanics is False


@pytest.mark.parametrize('side,three', [('right', False), ('left', False), ('right', True)])
def test_grounded_source_tree_full_rank_and_directional_first_variation(side, three):
    net = network(side=side, three=three)
    assert certificate(net)['certified']
    expected = oracle_matrix(net)
    assert_well_resolved(expected)
    # Nonzero components exercise every pose, internal wrench and reaction
    # block without importing any production derivative routine.
    rng = np.random.default_rng(731)
    for step in (2e-6, 7e-7):
        for _ in range(3):
            direction = rng.normal(size=net.size)
            direction /= np.max(abs(direction))
            actual = (net.residual(step*direction, 0.)-net.residual(-step*direction, 0.))/(2*step)
            np.testing.assert_allclose(actual, expected@direction, atol=4e-9, rtol=2e-8)
    signs = {h['parent_trace_sign'] for h in certificate(net)['hinges']}
    assert signs == ({-1, 1} if three else {1 if side == 'right' else -1})


def test_rotated_equal_source_frames_obey_independent_first_variation():
    net = network()
    # A physical 90-degree twist about the span changes local components while
    # leaving the literal geometry, hinge axis and body equilibrium unchanged.
    frame = np.array([[0., 0., 1.], [0., 1., 0.], [-1., 0., 0.]])
    net.R0a[:] = frame
    net.R0b[:] = frame
    assert certificate(net)['certified']
    rng = np.random.default_rng(117)
    direction = rng.normal(size=net.size)
    for step in (2e-6, 7e-7):
        actual = (net.residual(step*direction, 0.)-net.residual(-step*direction, 0.))/(2*step)
        np.testing.assert_allclose(actual, first_variation(net, direction), atol=5e-9, rtol=2e-8)


def test_arc_chord_mismatch_preserves_rank_without_claiming_zero_rest_residual():
    net = network(side='left')
    chord = np.linalg.norm(net.rj[net.b]-net.rj[net.a], axis=1)
    net.ds = chord*np.linspace(.65, 1.35, net.ne)
    assert np.any(net.ds != chord)
    report = certificate(net)
    assert report['certified']
    assert report['source_scope']['maximum_cold_translation_defect'] == pytest.approx(
        np.max(abs(chord-net.ds)))
    # The actual source residual is deliberately nonzero; no geometry/model
    # correction is made to obtain the rank result.
    rest = net.residual(np.zeros(net.size), 0.)[:6*net.ne].reshape(net.ne, 6)
    np.testing.assert_allclose(rest[:, 1], (chord-net.ds)/net.L, atol=1e-15)
    assert np.max(abs(rest)) > .01
    expected, actual = oracle_matrix(net), finite_difference_matrix(net)
    np.testing.assert_allclose(actual, expected, atol=3e-9, rtol=2e-8)
    assert_well_resolved(expected)
    assert_well_resolved(actual)


@pytest.mark.parametrize('field,index', [
    ('source_compliance', (0, 0, 0)), ('source_direct_compliance', (0, 0)),
    ('source_direct_compliance', (0, 1)), ('source_direct_compliance', (0, 2))])
def test_midpoint_zero_does_not_hide_nonzero_source_compliance(field, index):
    net = network()
    assert not np.any(net.S)
    getattr(net, field)[index] = 1e-30
    require_rejection(net, 'compliance')


def test_zero_offset_policy_checks_its_actual_axial_compliance():
    net = network(SourceDiscreteNetwork)
    assert not np.any(net.S)
    net.source_axial_compliance[0] = 1e-30
    require_rejection(net, 'compliance')


def test_source_rigidity_is_not_inferred_from_unused_midpoint_arrays():
    net = network()
    net.S[:] = .125
    net.k0[:] = .25
    net.v0[:] = .375
    assert certificate(net)['certified']


def test_finite_section_offset_transform_keeps_exact_rigid_source_limit():
    net = network()
    net.source_h[:] = [[0., .3, 0.], [-.2, 0., .4], [0., -.1, 0.]]
    assert certificate(net)['certified']
    direction = np.linspace(-.25, .5, net.size)
    step = 1e-6
    actual = (net.residual(step*direction, 0.)-net.residual(-step*direction, 0.))/(2*step)
    np.testing.assert_allclose(actual, first_variation(net, direction), atol=3e-9, rtol=2e-8)
    net.source_h[0, 0, 0] = np.nan
    require_rejection(net)


@pytest.mark.parametrize('kind', ['free_component', 'duplicate_ground', 'hinge_cycle', 'rigid_cycle',
                                  'partial_ground', 'interior_parent', 'offset_hinge'])
def test_unproved_source_graphs_do_not_receive_certificate(kind):
    m = model()
    if kind == 'free_component':
        m.records['joint'] = []
        m.records['jangle'] = []
    elif kind == 'duplicate_ground':
        m.records['ground'].append(m.records['ground'][0].copy())
    elif kind in ('hinge_cycle', 'rigid_cycle'):
        if kind == 'rigid_cycle':
            m.records['joint'][0][-1] = 0
            m.records['jangle'] = []
        m.records['joint'].append(m.records['joint'][0].copy())
        if kind == 'hinge_cycle':
            law = deepcopy(m.records['jangle'][0]); law['header'][0] = 2
            m.records['jangle'].append(law)
    elif kind == 'partial_ground':
        m.records['ground'][0][-1] = 1
    elif kind == 'interior_parent':
        m.records['joint'][0][2] = 2.5
    else:
        m.records['joint'][0][3] = 1.5
    net = SourceSectionNetwork(m, 4, None, [0., 0., 0.], [])
    require_rejection(net)


@pytest.mark.parametrize('kind', ['pose', 'internal', 'reaction', 'factor', 'hinge_chart',
                                  'motion', 'step', 'source_jig', 'unequal_frames', 'nonorthogonal'])
def test_nonzero_or_unproved_source_context_declines(kind):
    net = network()
    state, factor = np.zeros(net.size), 0.
    if kind == 'pose': state[0] = 1e-30
    elif kind == 'internal': state[6*net.nn] = 1e-30
    elif kind == 'reaction': state[6*(net.nn+net.ne)] = 1e-30
    elif kind == 'factor': factor = 1e-30
    elif kind == 'hinge_chart': net.constraints[-1]['angle_chart'] = 1e-30
    elif kind == 'motion': net.motion.rates[0] = 1e-30
    elif kind == 'step': net.offa[0, 0] = 1e-30
    elif kind == 'source_jig': net.source_jig_curvature[0, 0] = 1e-30
    elif kind == 'unequal_frames': net.R0b[0] = np.diag([-1., 1., -1.])
    else:
        net.R0a[0, 0, 0] = np.nextafter(1., np.inf)
        net.R0b[:] = net.R0a
    require_rejection(net, state=state, factor=factor)


@pytest.mark.parametrize('frame', [np.diag([1., -1., -1.]), np.diag([-1., 1., -1.]),
                                  np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])])
def test_source_euler_cut_and_pole_are_not_certified(frame):
    net = network()
    net.R0a[:] = frame
    net.R0b[:] = frame
    require_rejection(net, 'Euler chart')


@pytest.mark.parametrize('cls', [SourceDynamicNetwork, SourceMovingNetwork, SourceQuiescentNetwork])
def test_zero_instantaneous_motion_does_not_admit_dynamic_source_policy(cls):
    kwargs = {'quiescent_density': 1.2} if cls is SourceQuiescentNetwork else {}
    net = cls(model(), 4, None, [0., 0., 0.], [], **kwargs)
    require_rejection(net, 'unsupported source operator')


def test_unknown_source_subclass_cannot_inherit_a_proof_for_changed_equations():
    class UnreviewedNetwork(SourceSectionNetwork):
        pass
    require_rejection(network(UnreviewedNetwork), 'unsupported source operator')


def test_coupled_block_guards_remain_required_even_for_certified_source_tree(monkeypatch):
    import openswing.structured_static as structured
    net = network(SourceCoupledNetwork)
    assert certificate(net)['certified']
    mechanical_size = net.size
    net.size += 1
    state = np.zeros(net.size)
    monkeypatch.setattr(net, 'jacobian', lambda *args, **kwargs: np.zeros((net.size, net.size)))
    monkeypatch.setattr(structured, 'mechanical_rank_certificate', lambda *args, **kwargs: False)
    for circulation, coupling in [(np.zeros((1, 1)), np.zeros((mechanical_size, 1))),
                                 (np.ones((1, 1)), np.ones((mechanical_size, 1)))]:
        matrix = StructuredMatrix(csc_matrix(np.eye(mechanical_size)), coupling,
                                  csc_matrix((1, mechanical_size)), circulation)
        monkeypatch.setattr(structured, 'jacobian', lambda *args, **kwargs: (matrix, {}))
        with pytest.raises(AnalysisError, match='mechanism or redundant'):
            check_initial_rank(net, state)
