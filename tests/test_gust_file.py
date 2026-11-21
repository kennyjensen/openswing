from pathlib import Path
import json
import numpy as np
import pytest
from openswing.gust_file import import_gust, parse_legacy_gust, export_legacy_gust
from openswing.gust import gust_field
from openswing.bridge import dispatch
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid

SOURCE = '5 ! cosine\n-15 ! onset\n0 ! slope\n15 ! H\n3 ! W\n0\n'


@pytest.mark.parametrize('text', [SOURCE, SOURCE+'0\n', SOURCE.replace('\n', '\r\n'),
    '\ufeff# leading comment\n'+SOURCE.replace('-15', '-1.5D1').replace('15 ! H', '1.5d1 ! H')])
def test_published_layouts_give_independent_piecewise_profile(text):
    imported = import_gust(text)
    assert imported['format'] == 'aswing-gust'
    field = gust_field(imported['gust'])
    # Hand-calculated endpoints, quarter phases and peak; y/z/time have no effect.
    x = np.array([1., -15, -22.5, -30, -37.5, -45, -60])
    expected = np.zeros((7, 3));expected[:, 2] = [0, 0, 1.5, 3, 1.5, 0, 0]
    for time in [-100., 0., 42.]:
        points = np.column_stack([x, np.arange(7), 2*np.arange(7)])
        np.testing.assert_allclose(field.velocity(points, time), expected, atol=5e-15)
    # Conversion preserves the existing compact-wave time-sampling guard.
    assert field.phase_change(np.zeros((2, 3)), np.array([[-15., 1., 0.], [0., 0., 0.]]), 20) == pytest.approx(np.pi)


@pytest.mark.parametrize('text,match', [
    ('8\n-15\n0\n15\n3\n0\n', 'type 8'),
    (SOURCE.replace('0 ! slope', '.2 ! slope'), 'nonzero y slope'),
    (SOURCE.replace('15 ! H', '0 ! H'), 'positive'),
    (SOURCE.replace('15 ! H', '-15 ! H'), 'positive'),
    (SOURCE+'1\n', 'trailing'),
    (SOURCE+'0\n0\n', 'requires'),
    ('5\n-15\n0\n15\n3\n', 'requires'),
    (SOURCE.replace('3 ! W', 'NaN ! W'), 'finite numeric'),
    (SOURCE.replace('3 ! W', '1d999 ! W'), 'finite numeric'),
    (SOURCE.replace('-15 ! onset', '-15 2 ! onset'), 'one finite numeric'),
    ('', 'integer'), ('{}x', 'Invalid JSON'), ('[]', 'JSON object'),
    ('a'*32769, 'at most'),
])
def test_unverified_parameters_and_malformed_records_do_not_become_a_field(text, match):
    with pytest.raises(ValueError, match=match):
        import_gust(text)


def test_canonical_export_preserves_complete_field_and_json_import():
    spec = parse_legacy_gust(SOURCE)['gust']
    spec['amplitude'][2] = -2.5
    spec['origin'] = [4.25, 8., -7.]
    spec['normal'] = [-3., 0., 0.]
    points = np.random.default_rng(5).uniform(-40, 40, (200, 3))
    exported = export_legacy_gust(spec)
    decoded = import_gust(exported['text'])['gust']
    np.testing.assert_array_equal(gust_field(spec).velocity(points), gust_field(decoded).velocity(points))
    assert export_legacy_gust(decoded)['text'] == exported['text']
    assert import_gust(json.dumps(spec))['gust'] == spec
    assert import_gust('null')['gust'] == {'type': 'none'}
    assert dispatch(dict(action='gust_import', text=SOURCE))['gust'] == parse_legacy_gust(SOURCE)['gust']
    assert dispatch(dict(action='gust_export', gust=spec)) == exported


@pytest.mark.parametrize('change', [dict(type='none'), dict(speed=.1),
    dict(normal=[-1., .01, 0.]), dict(normal=[1., 0., 0.]), dict(amplitude=[.1, 0., 3.])])
def test_export_never_drops_unrepresentable_physics(change):
    spec = parse_legacy_gust(SOURCE)['gust']
    if change.get('type') == 'none':
        spec = change
    else:
        spec.update(change)
    with pytest.raises(ValueError, match='Legacy'):
        export_legacy_gust(spec)


def test_imported_field_drives_independent_point_drag_at_a_known_phase():
    model = parse_asw(Path('examples/gust-probe.asw').read_text())
    field = import_gust(SOURCE)['gust']
    condition = FlightCondition(speed=10., alpha=0., mach=0., position_earth=(-30., 4., -6.), gust=field)
    result = solve_rigid(model, condition, 4)
    velocity = np.array([10., 0., 3.])
    expected = .5*1.2*.4*np.linalg.norm(velocity)*velocity
    np.testing.assert_allclose(result['force'], expected, atol=2e-13)
    np.testing.assert_allclose(result['moment'], 0., atol=2e-13)
    np.testing.assert_array_equal(result['gust']['reference_velocity_earth'], [0., 0., 3.])
