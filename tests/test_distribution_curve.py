"""Independent graft polynomials, preserved exteriors, jump sides and symmetry."""
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import AswError, Distribution, parse_asw
from openswing.asw_edit import edit_distribution
from openswing.distribution_curve import graft, symmetry
from openswing.bridge import dispatch

WING = Path('examples/rectangular.asw').read_text()


def hump(t):
    t = np.asarray(t)
    u = np.where(t <= 3, (t-1)/2, (5-t)/2)
    inside = (1 <= t) & (t <= 5)
    return np.where(inside, 3*u*u-2*u*u*u, 0.)


def hump_slope(t):
    t = np.asarray(t)
    u = np.where(t <= 3, (t-1)/2, (5-t)/2)
    return np.where((1 <= t) & (t <= 5), (3*u-3*u*u)*np.where(t <= 3, 1, -1), 0.)


def test_tangent_graft_matches_independent_cubic_and_preserves_exterior():
    original = Distribution('alpha', [0, 6], [0, 0], 0)
    # Order is immaterial; endpoint click values snap to the old curve.
    result, report = graft(original, dict(points=[[5, -9], [1, 7], [3, 1]], tolerance=1e-5), (0, 6))
    query = np.unique(np.r_[np.linspace(0, 6, 12001), result.t])
    assert max(abs(result.evaluate(query)-hump(query))) < 1e-5
    assert 6*max(abs(result.evaluate(query, derivative=1)-hump_slope(query))) < 1e-5
    assert report['maximum_relative_value_error'] < 1e-5
    assert report['maximum_relative_slope_error'] < 1e-5
    np.testing.assert_array_equal(report['points'], [[1, 0], [3, 1], [5, 0]])
    np.testing.assert_array_equal(original.t, [0, 6])
    assert result.breaks.size == 0


@pytest.mark.parametrize('station_scale,value_scale,offset', [(1, 1, 0), (.001, -7, 30), (25, 1e-6, -2e-5)])
def test_graft_covaries_with_station_value_units_and_offset(station_scale, value_scale, offset):
    d = Distribution('alpha', [10, 10+6*station_scale], [offset, offset], 0)
    points = [[10+t*station_scale, offset+v*value_scale] for t, v in [(1, 0), (3, 1), (5, 0)]]
    result, report = graft(d, dict(points=points, tolerance=2e-5), (d.t[0], d.t[-1]))
    t = np.linspace(0, 6, 10001)
    assert max(abs((result.evaluate(10+t*station_scale)-offset)/value_scale-hump(t))) < 2e-5
    assert 6*max(abs(result.evaluate(10+t*station_scale, derivative=1)*station_scale/value_scale-hump_slope(t))) < 2e-5
    assert report['value_scale'] == pytest.approx(abs(value_scale))


def test_free_graft_retains_endpoint_jumps_and_existing_outer_corners():
    d = Distribution('alpha', [0, 1, 1, 6], [0, 0, 2, 2], 0)
    result, report = graft(d, dict(points=[[2, 5], [4, 9]], tangent=False), (0, 6))
    np.testing.assert_array_equal(result.breaks, [1, 2, 4])
    np.testing.assert_allclose(result.evaluate([1, 2, 4], side='left'), [0, 2, 9])
    np.testing.assert_allclose(result.evaluate([1, 2, 4], side='right'), [2, 5, 2])
    np.testing.assert_allclose(result.evaluate([2.5, 3, 3.5]), [6, 7, 8])
    assert report['maximum_relative_value_error'] == 0
    assert report['maximum_relative_slope_error'] == 0


def test_graft_checks_extrapolated_property_domain_and_reloaded_stations():
    d = Distribution('alpha', [1, 2, 3], [0, 1, 0], 0)
    result, report = graft(d, dict(points=[[1.5, 0], [2, 2], [2.5, 0]], tolerance=1e-4), (0, 4))
    assert report['domain'] == [0, 4]
    q = np.r_[np.linspace(0, 1.5, 2001), np.linspace(2.5, 4, 2001)]
    assert max(abs(result.evaluate(q)-d.evaluate(q))) <= report['value_scale']*1e-4
    assert max(abs(result.evaluate(q, derivative=1)-d.evaluate(q, derivative=1)))*4 <= report['value_scale']*1e-4
    reloaded = Distribution('alpha', result.t.copy(), result.values.copy(), 0)
    np.testing.assert_array_equal(reloaded.evaluate(q), result.evaluate(q))


@pytest.mark.parametrize('name', ['alpha', 'y'])
def test_explicit_halves_preserve_curved_mirror_jumps_and_derivatives(name):
    original = Distribution(name, [0, .4, 1, 1, 3, 6], [5, 5.7, 5.9, 8, 10, 9], 0)
    expanded = symmetry(original, 'independent', True)
    q = np.unique(np.r_[np.linspace(-6, 6, 1021), -1, 0, 1])
    for derivative in (0, 1, 2):
        for side in ('left', 'right'):
            np.testing.assert_allclose(expanded.evaluate(q, side=side, derivative=derivative),
                                       original.evaluate(q, mirror=True, side=side, derivative=derivative), atol=2e-13)
    restored = symmetry(expanded, 'positive', True)
    np.testing.assert_array_equal(restored.t, original.t)
    np.testing.assert_array_equal(restored.values, original.values)


def test_mirroring_full_property_adds_center_value_and_retains_positive_stations():
    d = Distribution('y', [-3, -1, 2, 6], [0, 2, 8, 15], 0)
    result = symmetry(d, 'positive', True)
    np.testing.assert_array_equal(result.t, [0, 2, 6])
    assert result.values[0] == d.evaluate(0)
    np.testing.assert_array_equal(result.values[1:], d.values[2:])
    np.testing.assert_allclose(result.evaluate([-2, -6], mirror=True), 2*d.evaluate(0)-d.values[2:])
    positive=Distribution('alpha',[1,2],[2,3],0)
    extended=symmetry(positive,'positive',True)
    np.testing.assert_array_equal(extended.t,[0,1,2])
    np.testing.assert_array_equal(extended.values,[1,2,3])


@pytest.mark.parametrize('specification', [
    dict(points=[[1, 0]]), dict(points=[[1, 0], [1, 2]]),
    dict(points=[[-1, 0], [2, 1]]), dict(points=[[1, 0], [7, 1]]),
    dict(points=[[1, 0], [2, float('nan')]]), dict(points=[[1, 0], [2, 1]], tolerance=0),
    dict(points=[[1, 0], [2, 1]], tangent='yes'), dict(points=[[1, 0], [2, 1]], unknown=1),
])
def test_invalid_graft_is_atomic(specification):
    m = parse_asw(WING)
    with pytest.raises(AswError):
        edit_distribution(m, 1, 'alpha', graft=specification)
    assert m.dumps() == WING


def test_bridge_graft_roundtrip_and_selected_property_symmetry():
    result = dispatch(dict(action='edit_distribution', source=WING, beam=1, name='alpha',
                           edit=dict(points=[[0,0],[6,0]], symmetry='independent', graft=dict(points=[[-5, 0], [-3, 1], [-1, 0]]))))
    model = parse_asw(result['source']);d = model.beams[0].distributions['alpha']
    assert d.t[0] == -6 and not result['distribution']['mirrored']
    assert model.beams[0].distributions['chord'].t[0] == 0
    assert d.evaluate(-3) == 1 and abs(d.evaluate(3)) < 1e-5
    assert model.dumps() == result['source']
    report = result['distribution']['editing']
    assert report['stations'] == len(d.t) and report['maximum_relative_slope_error'] <= report['tolerance']


def test_symmetry_rejects_nonlifting_and_bad_requests():
    d = Distribution('alpha', [0, 1], [0, 1], 0)
    with pytest.raises(AswError, match='lifting'):
        symmetry(d, 'independent', False)
    with pytest.raises(AswError, match='Symmetry'):
        symmetry(d, 'unknown', True)
    with pytest.raises(AswError, match='positive station'):
        symmetry(Distribution('alpha', [-2, -1], [0, 1], 0), 'positive', True)
