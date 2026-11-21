"""Byte-preserving FFWT input compatibility; no residual or equilibrium calls.

The packaged original model is hash pinned. Minimal fixtures cover every rule.
Singleton rigidity and paired Jangle reversal are explicit compatibility rules,
not proof of the original ASWING reader or of archived numerical reproduction.
"""
from copy import deepcopy
import hashlib
from pathlib import Path

import numpy as np
import pytest

from openswing.asw import AswError, Distribution, RIGID, parse_asw
from openswing.asw_edit import distribution_report, edit_distribution, model_data
from openswing.discretization import (
    CHORDAL_MESH_RECIPE, CURRENT_MESH_RECIPE, LEGACY_MESH_RECIPE, requirements,
)
from openswing.geometry import model_meshes
from openswing.joints import HingeLaw, hinge_laws

ROOT = Path(__file__).resolve().parents[1]
LITERAL = ROOT / 'examples/isae-ffwt-flare10.asw'
LITERAL_SHA256 = 'f73fe93bebb9419f0d38d94dc9a365baac7e3437e2996473c72c3c1f459fbf13'
POLICIES = ['natural-v1', 'drela-segspl-v1']
RECIPES = [LEGACY_MESH_RECIPE, CHORDAL_MESH_RECIPE, CURRENT_MESH_RECIPE]
HEADER = '''Name
Portable FFWT input check
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
9.81 1.2256 340.21
End
Reference
1 1 2
0 0 0
End
'''


def source_with(group='', *, lifting=False):
    geometry = 't y chord\n-1 -1 1\n1 1 1' if lifting else 't y\n0 0\n2 2'
    return HEADER + 'Beam 1 1\nPortable beam\n' + geometry + '\n' + group + '\nEnd\n'


def linked_source(curve='-2 -3\n2 5', axis='2 -1 0'):
    return HEADER + f'''Ground
1 0 0
End
Joint
1 2 2 2 3
End
Jangle
1 {axis}
{curve}
End
Beam 1 1
First rigid link
t y
0 0
2 2
End
Beam 2 2
Second rigid link
t y
2 2
4 4
End
'''


@pytest.fixture(autouse=True)
def no_physical_evaluations(monkeypatch):
    """Tripwire: construction, identity and inspection must not evaluate R."""
    from openswing.network import StaticNetwork
    from openswing.source_discrete import SourceDiscreteNetwork
    from openswing.source_coupled import SourceCoupledNetwork

    def forbidden(*args, **kwargs):
        pytest.fail('Input compatibility tests must not evaluate physical residuals.')

    for cls in (StaticNetwork, SourceDiscreteNetwork, SourceCoupledNetwork):
        monkeypatch.setattr(cls, 'residual', forbidden)


@pytest.fixture
def literal_source():
    raw = LITERAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == LITERAL_SHA256
    return raw.decode()


@pytest.mark.parametrize('policy', POLICIES)
def test_literal_bytes_domains_scaled_samples_axes_and_weights(literal_source, policy):
    for source in (literal_source, literal_source.replace('\r\n', '\n').replace('\n', '\r\n') + '! retained annotation\r\n'):
        model = parse_asw(source, beam_interpolation=policy)
        assert model.dumps() == source
        assert deepcopy(model).dumps() == source
        assert not model.diagnostics
        assert [b.physical_index for b in model.beams] == [1, 1, 1]
        assert [b.domain for b in model.beams] == [(-.364, .364), (.364, .5), (-.5, -.364)]
        np.testing.assert_array_equal(model.constants, [9.81, 1.2256, 340.21])
        np.testing.assert_array_equal(model.reference[0], [.5222, .305, .856])
        for beam in model.beams[1:]:
            for name in ('GJ', 'EIcc'):
                d = beam.distributions[name]
                assert d.constant_rigid and d._segments == []
                np.testing.assert_array_equal(d.t, [.182])
                np.testing.assert_array_equal(d.values, [0])
                assert np.isinf(beam.value(name, np.linspace(*beam.domain, 7))).all()
        weight = np.asarray(model.records['weight'])
        expected = np.zeros_like(weight)
        expected[:, :6] = [[1, .1588, .0335, .1588, 0, .3865*9.81],
                          [1, -.1588, .0335, -.1588, 0, .3865*9.81],
                          [2, .4406, .0335, .4406, 0, 0],
                          [3, -.4406, .0335, -.4406, 0, 0]]
        np.testing.assert_array_equal(weight, expected)
        for i, y in enumerate((-.1736, .1736)):
            np.testing.assert_array_equal(model.records['jangle'][i]['header'], [i+1, .9848, y, 0])
        assert np.diff(model.records['jangle'][1]['curve'][:, 0])[0] < 0
        canonical = model.dumps(canonical=True)
        reloaded = parse_asw(canonical, beam_interpolation=policy)
        assert model_data(reloaded) == model_data(model)
        assert reloaded.dumps(canonical=True) == canonical
        assert np.diff(reloaded.records['jangle'][1]['curve'][:, 0])[0] < 0


@pytest.mark.parametrize('policy', POLICIES)
def test_literal_hinges_follow_independent_affine_law(literal_source, policy):
    model = parse_asw(literal_source, beam_interpolation=policy)
    laws = hinge_laws(model.records)
    moments = np.array([-240, -120, -13, 0, 19, 120, 240.])*1.7453e-8
    for i, sign in ((1, 1), (2, -1)):
        law = laws[i]
        expected = sign*moments/1.7453e-8
        np.testing.assert_allclose(np.rad2deg(law.angle(moments)), expected, rtol=3e-15, atol=2e-13)
        np.testing.assert_allclose(law.spline.evaluate(moments, derivative=1), sign/1.7453e-8, rtol=3e-15)
        # Scale derivatives by the literal domain: deg/(N m)^2 magnifies
        # ordinary two-point polynomial roundoff for this extremely soft law.
        moment_span = 240*1.7453e-8
        normalized_curvature = law.spline.evaluate(moments, derivative=2)*moment_span**2/240
        np.testing.assert_allclose(normalized_curvature, 0, atol=64*np.finfo(float).eps)
        assert abs(np.rad2deg(law.zero_angle)) <= 2e-13
        axis = np.array([.9848, (-.1736 if i == 1 else .1736), 0])
        np.testing.assert_array_equal(law.axis, axis/np.linalg.norm(axis))
        record = model.records['jangle'][i-1]
        assert not np.shares_memory(law.curve, record['curve'])
        assert np.all(np.diff(law.curve[:, 0]) > 0)
        increasing = dict(header=record['header'].copy(), curve=record['curve'][np.argsort(record['curve'][:, 0])].copy())
        independent_order = HingeLaw(increasing)
        np.testing.assert_array_equal(law.angle(moments), independent_order.angle(moments))
        assert not law.report(0, law.axis)['extrapolated']
        assert law.report(moments[0], law.axis)['extrapolated']


@pytest.mark.parametrize('name', sorted(RIGID))
@pytest.mark.parametrize('table', ['.182 0', '* 1 0\n.182 19', '* 1 2\n+ 0 -6\n.182 3'])
def test_only_effective_zero_rigid_singletons_are_constant(name, table):
    model = parse_asw(source_with('t '+name+'\n'+table))
    beam = model.beams[0];d = beam.distributions[name]
    assert d.constant_rigid is True and d._segments == [] and d.breaks.size == 0
    np.testing.assert_array_equal(d.t, [.182]);np.testing.assert_array_equal(d.values, [0])
    np.testing.assert_array_equal(d._compiled_t, d.t);np.testing.assert_array_equal(d._compiled_values, d.values)
    assert d._compiled_interpolation == model.beam_interpolation
    with pytest.raises(AttributeError):
        d.constant_rigid = False
    queries = [0., np.array([-10., 0., .182, 2., 10.]), np.array([[-1., 0.], [1., 3.]])]
    for q in queries:
        for side in ('left', 'right'):
            for mirror in (False, True):
                for derivative in range(5):
                    result = d.evaluate(q, side=side, mirror=mirror, derivative=derivative)
                    assert result.shape == np.shape(q)
                    np.testing.assert_array_equal(result, np.zeros_like(q))
            assert np.isinf(beam.value(name, q, side=side)).all()
            for derivative in (1, 2, 3, 4):
                np.testing.assert_array_equal(beam.value(name, q, side=side, derivative=derivative), np.zeros_like(q))
    with pytest.raises(ValueError):d.evaluate(0, derivative=-1)
    with pytest.raises(TypeError):d.evaluate(0, derivative=.5)
    with pytest.raises(ValueError):d.evaluate(0, side='middle')


@pytest.mark.parametrize('group', [
    't GJ mg\n.2 0 0', 't GJ chord\n.2 0 0', 't GJ EIcc\n.2 0 1',
    't EIcn\n.2 0', 't mystery\n.2 0', 't GJ\n.2 1', 't GJ',
    't GJ\n.2 nan', 't GJ\ninf 0', 't x\n.2 0',
])
def test_invalid_whole_singleton_groups_remain_errors(group):
    source = source_with(group)
    with pytest.raises(AswError) as exc:parse_asw(source)
    assert exc.value.line is not None


@pytest.mark.parametrize('name,t,v', [
    ('x', [.2], [0]), ('time', [.2], [0]), ('Jangle 1', [.2], [0]),
    ('EIcn', [.2], [0]), ('GJ', [.2], [1]), ('GJ', [], []),
    ('GJ', [.2], []), ('GJ', [[.2]], [[0]]),
    ('GJ', [np.nan], [0]), ('GJ', [.2], [np.inf]),
])
def test_constant_case_cannot_leak_into_generic_distributions(name, t, v):
    with pytest.raises(AswError):Distribution(name, t, v, 7)


def test_entire_six_column_group_and_nonforcing_admission():
    names = sorted(RIGID)
    model = parse_asw(source_with('t '+' '.join(names)+'\n.182 '+' '.join('0' for _ in names)))
    assert all(model.beams[0].distributions[n].constant_rigid for n in names)
    from openswing.forcing import TimeForcing
    from openswing.inertia import Motion
    with pytest.raises(AswError, match='two time samples'):
        TimeForcing('time Ax\n0 0', model, None, Motion(), 1., 'prescribed')
    with pytest.raises(AswError, match='two moment/angle'):
        parse_asw(linked_source('0 0'))


@pytest.mark.parametrize('curve,axis', [
    ('2 2\n0 0\n-2 -2', '1 0 0'), ('2 2\n-2 -2\n0 0', '1 0 0'),
    ('-2 -2\n0 0\n0 1\n2 2', '1 0 0'), ('0 0\n0 0', '1 0 0'),
    ('-2 -2\n2 2', '0 0 0'),
])
def test_two_point_exception_does_not_admit_invalid_hinges(curve, axis):
    with pytest.raises(AswError):parse_asw(linked_source(curve, axis))


def test_decreasing_pair_private_copy_preserves_sign_offset_axis_and_extrapolation():
    model = parse_asw(linked_source('2 5\n-2 -3'))
    record = model.records['jangle'][0];raw = record['curve'].copy();law = hinge_laws(model.records)[1]
    m = np.array([-5., -2., 0., 2., 7.])
    np.testing.assert_allclose(np.rad2deg(law.angle(m)), 2*m+1, rtol=2e-15, atol=2e-14)
    np.testing.assert_allclose(law.spline.evaluate(m, derivative=1), 2, atol=1e-15)
    assert np.rad2deg(law.zero_angle) == pytest.approx(1)
    np.testing.assert_array_equal(record['curve'], raw)
    assert not np.shares_memory(law.curve, record['curve'])
    record['curve'][0, 1] = 1234
    np.testing.assert_allclose(np.rad2deg(law.angle(m)), 2*m+1, atol=2e-14)


@pytest.mark.parametrize('policy', POLICIES)
def test_existing_splines_mirroring_and_slope_breaks_remain_unchanged(policy):
    d = Distribution('alpha', [0, 1, 2], [0, 1, 0], 1, interpolation=policy)
    x = np.linspace(0, 1, 13)
    if policy == 'natural-v1':
        expected = 1.5*x-.5*x**3;first = 1.5-1.5*x*x;second = -3*x
    else:
        expected = 2*x-x*x;first = 2-2*x;second = np.full_like(x, -2.)
    assert d.constant_rigid is False
    for derivative, expected_values in enumerate((expected, first, second)):
        np.testing.assert_allclose(d.evaluate(x, derivative=derivative), expected_values, atol=2e-15)
    reverse = Distribution('y', [0, -1, -2], [0, -1, -2], 1, interpolation=policy)
    np.testing.assert_array_equal(reverse.t, [-2, -1, 0]);assert reverse.evaluate(-1.5) == -1.5
    jump = Distribution('GJ', [0, 1, 1, 2], [2, 2, 7, 7], 1, interpolation=policy)
    assert jump.evaluate(1, side='left') == jump.evaluate(-1, mirror=True, side='right') == 2
    assert jump.evaluate(1, side='right') == jump.evaluate(-1, mirror=True, side='left') == 7
    law = hinge_laws(parse_asw(linked_source('-2 -2\n0 0\n0 0\n2 4'), beam_interpolation=policy).records)[1]
    assert law.spline.interpolation == 'natural-v1'
    assert law.spline.evaluate(0, derivative=1, side='left') == 1
    assert law.spline.evaluate(0, derivative=1, side='right') == 2


@pytest.mark.parametrize('recipe', RECIPES)
def test_constant_metadata_does_not_change_required_nodes_or_old_meshes(recipe):
    base = parse_asw(source_with(lifting=True))
    extra = parse_asw(source_with('t GJ\n0 0\nt EIcc\n.182 0', lifting=True))
    assert requirements(base, mesh_recipe=recipe) == requirements(extra, mesh_recipe=recipe)
    assert extra.beams[0].mesh_breaks(include_shell=recipe == LEGACY_MESH_RECIPE).size == 0
    left, right = model_meshes(base, 5, mesh_recipe=recipe)[0], model_meshes(extra, 5, mesh_recipe=recipe)[0]
    for name in ('t0', 't1', 'tm', 'r0', 'r1', 'rm', 'frames', 'length', 'ts', 'theta'):
        np.testing.assert_array_equal(getattr(left, name), getattr(right, name))


@pytest.mark.parametrize('recipe', RECIPES)
def test_literal_no_singleton_station_is_inserted(literal_source, recipe):
    model = parse_asw(literal_source)
    required = requirements(model, mesh_recipe=recipe)
    meshes = model_meshes(model, 8, mesh_recipe=recipe)
    for beam, mesh in zip(model.beams[1:], meshes[1:]):
        assert all(row['t'] != .182 for row in required[beam.index])
        assert .182 not in np.r_[mesh.t0, mesh.t1[-1]]
        assert np.min(mesh.t0) == beam.domain[0] and np.max(mesh.t1) == beam.domain[1]


@pytest.mark.parametrize('policy', POLICIES)
def test_constant_edit_roundtrips_and_explicit_replacements(policy):
    source = source_with('t GJ\n.182 0', lifting=True)
    model = parse_asw(source, beam_interpolation=policy)
    for options in (dict(multiplier=0), dict(multiplier=-5), dict(points=[[.182, 2]], multiplier=0)):
        edited = edit_distribution(model, 1, 'GJ', **options)
        assert edited.beams[0].distributions['GJ'].constant_rigid
        np.testing.assert_array_equal(edited.beams[0].distributions['GJ'].t, [.182])
        assert model.dumps() == source
    unrelated = edit_distribution(model, 1, 'chord', multiplier=2)
    assert unrelated.beams[0].distributions['GJ'].constant_rigid
    assert unrelated.beam_interpolation == policy and unrelated.beams[0].value('chord', .4) == 2
    removed = edit_distribution(model, 1, 'GJ', remove=True)
    assert 'GJ' not in removed.beams[0].distributions and np.isinf(removed.beams[0].value('GJ', .4))
    explicit = edit_distribution(model, 1, 'GJ', points=[[-1, 100], [1, 200]])
    assert not explicit.beams[0].distributions['GJ'].constant_rigid
    assert explicit.beams[0].value('GJ', 0) == 150
    assert model.dumps() == source
    canonical = unrelated.dumps(canonical=True)
    assert model_data(parse_asw(canonical, beam_interpolation=policy)) == model_data(unrelated)


@pytest.mark.parametrize('options', [dict(adder=1), dict(points=[[.182, 1]]), dict(symmetry='independent'),
                                    dict(symmetry='positive'), dict(graft=dict(points=[[-.5, 0], [.5, 0]]))])
def test_invalid_singleton_edits_are_atomic(options):
    source = source_with('t GJ\n.182 0', lifting=True);model = parse_asw(source)
    with pytest.raises(AswError) as exc:edit_distribution(model, 1, 'GJ', **options)
    if 'symmetry' in options or 'graft' in options:assert 'multi-point' in str(exc.value)
    assert model.dumps() == source
    np.testing.assert_array_equal(model.beams[0].distributions['GJ'].values, [0])


def test_preview_is_constant_over_beam_domain_and_cache_cannot_lie():
    source = source_with('t GJ\n9 0', lifting=True);model = parse_asw(source)
    report = distribution_report(model, 1, 'GJ')
    assert report['constant_rigid'] is True and report['mirrored'] is False
    assert report['points'] == [[9, 0]] and report['domain'] == [-1, 1]
    assert len(report['segments']) == 1 and report['segments'][0]['extrapolated'] is False
    assert report['segments'][0]['t'][0] == -1 and report['segments'][0]['t'][-1] == 1
    np.testing.assert_array_equal(report['segments'][0]['values'], np.zeros(81))
    assert 'Constant rigid override' in report['limitations'][0]
    d = model.beams[0].distributions['GJ'];d.values[0] = 1
    for operation in (model.dumps, lambda: distribution_report(model, 1, 'GJ'), lambda: edit_distribution(model, 1, 'GJ', multiplier=0)):
        with pytest.raises(AswError, match='rebuilding'):operation()
    d.values[0] = 0;d.t[0] = 8
    with pytest.raises(AswError, match='rebuilding'):model.dumps()


@pytest.mark.parametrize('policy', POLICIES)
@pytest.mark.parametrize('recipe', RECIPES)
def test_existing_network_identity_has_no_new_constant_metadata(policy, recipe):
    from openswing.network import StaticNetwork
    from openswing.equilibrium_state import identity
    source = source_with('t EIcc GJ EInn EA\n0 100 200 300 400\n2 100 200 300 400') + 'Ground\n1 0 0\nEnd\n'
    model = parse_asw(source, beam_interpolation=policy)
    panels = dict(default=4, beams={'1': dict(nodes=[0, .5, 1, 1.5, 2])})
    n = StaticNetwork(model, panels, None, [0, 0, 0], (), mesh_recipe=recipe)
    expected = dict(model_sha256=hashlib.sha256(source.encode()).hexdigest(), nodes=[[0., y, 0.] for y in (0, .5, 1, 1.5, 2)],
                    elements=[[i, i+1] for i in range(4)], stations={'1': [[0., .5, 1., 1.5, 2.], [0, 1, 2, 3, 4]]},
                    constraints=[dict(kind='ground', type=0, a=0, b=None)], circulation_count=0)
    if policy != 'natural-v1':expected['beam_interpolation'] = policy
    if recipe != LEGACY_MESH_RECIPE:expected['mesh_recipe'] = recipe
    assert identity(n) == expected


def test_synthetic_unsolved_v2_packet_keeps_chart_and_exact_identity_guards():
    """Zero coordinates are a serialization witness, never a solved state claim."""
    from openswing.network import StaticNetwork
    from openswing.equilibrium_state import capture, restore, validate
    from openswing.aero import AnalysisError
    model = parse_asw(linked_source('2 5\n-2 -3'))
    n = StaticNetwork(model, 4, None, [0, 0, 0], ())
    x = np.zeros(n.size);saved = capture(n, x, include_launch=False)
    assert saved['version'] == 2 and saved['residual'] is None and 'launch' not in saved
    assert saved['hinge_charts'] == [dict(joint=1, angle_rad=0.)]
    np.testing.assert_array_equal(restore(n, saved), x)
    before = deepcopy(saved)
    for field, wrong in [('model_sha256', 'different bytes'), ('structural_operator', 'drela-steady-section-v1'),
                         ('beam_interpolation', 'drela-segspl-v1')]:
        bad = deepcopy(saved);bad['identity'][field] = wrong
        with pytest.raises(AnalysisError, match='does not match'):restore(n, bad)
    bad = deepcopy(saved);bad['hinge_charts'][0]['angle_rad'] = .5
    with pytest.raises(AnalysisError, match='disagree'):restore(n, bad)
    bad = deepcopy(saved);bad['version'] = 1;bad.pop('hinge_charts')
    with pytest.raises(AnalysisError, match='winding'):validate(n, bad)
    assert saved == before


def test_literal_bridge_inspection_preview_and_canonical_do_not_solve(literal_source):
    from openswing.bridge import dispatch
    policy = dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-steady-coupled-v1')
    common = dict(source=literal_source, panels=8, numerics=policy)
    inspected = dispatch(dict(action='inspect', **common))
    assert inspected['hinge_count'] == 2 and len(inspected['beams']) == 3
    assert [d['domain'] for d in inspected['distributions']] == [[-.364, .364], [.364, .5], [-.5, -.364]]
    assert inspected['numerics'] == policy
    preview = dispatch(dict(action='distribution', beam=2, name='GJ', **common))
    assert preview['constant_rigid'] and preview['points'] == [[.182, 0]]
    normalized = dispatch(dict(action='canonical_asw', **common))['source']
    model = parse_asw(normalized, beam_interpolation='drela-segspl-v1')
    assert model.beams[1].distributions['GJ'].constant_rigid
    assert np.diff(model.records['jangle'][1]['curve'][:, 0])[0] < 0
