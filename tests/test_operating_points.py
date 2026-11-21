"""Explicit steady stacks preserve single-point physics and reject bad plans first."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from openswing import bridge
from openswing.numerical_policy import SOURCE_COUPLED


SOURCE = Path('examples/rectangular.asw').read_text()
COUPLED = dict(beam_interpolation='drela-segspl-v1', structural_operator=SOURCE_COUPLED)


def request(points=None, **options):
    return dict(action='operating_points', source=SOURCE, panels=4,
                condition=dict(speed=30., alpha=0., mach=0.),
                operating_points=dict(points=points if points is not None else [{}, {}]), **options)


def test_rigid_stack_matches_independent_single_points_and_parses_once(monkeypatch):
    value = request([dict(name='base', condition=dict(alpha=2., controls={'1': 1.})),
                     dict(condition=dict(alpha=4.)), dict(condition=dict(controls={'1': 0.}))])
    value['panels'] = dict(default=8, beams={'1': dict(count=8, spacing='modified-cosine')})
    original = deepcopy(value)
    parse, parsed = bridge.parse_asw, []
    def tracked(*args, **kwargs):
        parsed.append(1)
        return parse(*args, **kwargs)
    monkeypatch.setattr(bridge, 'parse_asw', tracked)
    result = bridge.dispatch(value)
    assert len(parsed) == 1
    assert result['converged'] and result['converged_points'] == result['total_points'] == 3
    assert result['failed_points'] == 0 and result['initialization'] == 'cold'
    assert value == original
    for row, alpha, flap in zip(result['points'], [2., 4., 4.], [1., 1., 0.]):
        assert row['condition']['alpha'] == alpha
        assert row['condition']['controls'] == {1: flap}
        direct = bridge.dispatch(dict(action='solve', source=SOURCE, panels=value['panels'],
                                      condition=row['condition']))
        for key in ('force', 'moment', 'CL', 'CD', 'CDi', 'Cm'):
            np.testing.assert_allclose(row['result'][key], direct[key], rtol=0, atol=1e-12)
        np.testing.assert_array_equal([s['circulation'] for s in row['result']['strips']],
                                      [s['circulation'] for s in direct['strips']])
        assert row['actual_condition'] == row['condition']
        assert row['result']['mesh_discretization'] == direct['mesh_discretization']
    json.dumps(result, allow_nan=False)


def test_physical_failure_is_retained_and_later_cold_point_recovers():
    result = bridge.dispatch(request([dict(condition=dict(alpha=3.)),
        dict(name='beyond local Mach scope', condition=dict(alpha=89., speed=600.)),
        dict(name='recovered', condition=dict(alpha=3., speed=30.))]))
    assert not result['converged']
    assert (result['converged_points'], result['failed_points'], result['total_points']) == (2, 1, 3)
    first, failed, last = result['points']
    assert first['converged'] and last['converged']
    assert not failed['converged'] and failed['result'] is None and failed['actual_condition'] is None
    assert 'Mach' in failed['error']['message']
    assert failed['condition']['speed'] == 600.
    np.testing.assert_array_equal([s['circulation'] for s in first['result']['strips']],
                                  [s['circulation'] for s in last['result']['strips']])


def test_mounted_trim_inherits_specifications_not_solved_alpha():
    constraint = [dict(variable='alpha', quantity='CL', target=.3)]
    value = request([dict(name='trim', operating_constraints=constraint), {},
                     dict(name='specified', operating_constraints=[])], mode='mounted', gravity=[0., 0., 0.])
    result = bridge.dispatch(value)
    assert result['converged']
    first, inherited, cleared = result['points']
    assert first['actual_condition']['alpha'] > 1.
    assert first['result']['CL'] == pytest.approx(.3, abs=1e-10)
    assert inherited['actual_condition']['alpha'] == pytest.approx(first['actual_condition']['alpha'], abs=1e-11)
    assert inherited['operating_constraints'] == constraint
    assert all(row['condition']['alpha'] == 0 for row in result['points'])
    assert cleared['actual_condition']['alpha'] == 0
    assert abs(cleared['result']['CL']) < 1e-12
    direct = bridge.dispatch(dict(action='solve', source=SOURCE, panels=4, mode='mounted',
        gravity=[0., 0., 0.], condition=first['condition'], operating_constraints=constraint))
    np.testing.assert_allclose(first['result']['force'], direct['force'], rtol=0, atol=1e-10)


def test_source_coupled_stack_preserves_policy_and_single_point_results():
    value = request([dict(condition=dict(alpha=2.)), dict(condition=dict(alpha=3.))],
                    mode='mounted', numerics=COUPLED, gravity=[0., 0., 0.],
                    tolerance=2e-9, continuation_steps=2)
    result = bridge.dispatch(value)
    assert result['converged'] and result['numerics'] == COUPLED
    for row in result['points']:
        direct = bridge.dispatch({**{key: val for key, val in value.items() if key != 'operating_points'},
                                  'action': 'solve', 'condition': row['condition']})
        assert row['result']['numerics'] == COUPLED
        np.testing.assert_allclose(row['result']['force'], direct['force'], rtol=0, atol=1e-11)
        assert row['result']['equilibrium_state']['identity']['structural_operator'] == SOURCE_COUPLED


def test_options_channels_and_nested_progress_survive_route_sharing(monkeypatch):
    source = SOURCE+'\nEngine\n1 0 1 2 0 2 0 0 1 0 1 0 -1 0 0\nEnd\n'
    value = request([dict(condition=dict(controls={'1': 2.}, powers={'1': 5.})),
                     dict(condition=dict(alpha=4.))], mode='mounted', gravity=[0, 0, 0],
        loads=[dict(beam=1, t=3, force=[0, 0, 1])], strut_mode='wire',
        controller=dict(outputs=[dict(actuator='F1', terms=[dict(input='A', gain=0.)])]),
        derivatives=dict(parameters=['alpha', 'command.F1'], axes='body', step=2e-5))
    value['source'] = source
    calls, events = [], []
    def solve(model, condition, panels, **options):
        calls.append((model, deepcopy(condition), deepcopy({k: v for k, v in options.items() if k != 'progress'})))
        options['progress']('coupled', 2, 5)
        if len(calls) == 2:
            raise ValueError('retained numerical failure')
        return dict(converged=True, operating_values={'alpha': 8., 'attitude.bank': 2.},
                    feedback={'actuators': {'F1': 4., 'E1': 7.}})
    monkeypatch.setattr(bridge, 'solve_static', solve)
    result = bridge.dispatch(value, lambda *args: events.append(args))
    assert len(calls) == 2 and calls[0][0] is calls[1][0]
    assert all(c[1].controls == {1: 2.} and c[1].powers == {1: 5.} for c in calls)
    for _, _, options in calls:
        for key in ('gravity', 'loads', 'strut_mode', 'controller', 'derivatives'):
            assert options[key] == value[key]
        assert options['initial_state'] is None and options['operating_constraints'] == []
    assert events == [('operating_point', 1, 2), ('operating_point/coupled', 2, 5),
                      ('operating_point_done', 1, 2), ('operating_point', 2, 2),
                      ('operating_point/coupled', 2, 5), ('operating_point_failed', 2, 2)]
    actual = result['points'][0]['actual_condition']
    assert actual['alpha'] == 8. and actual['attitude'] == [2., 0., 0.]
    assert actual['controls'] == {1: 4.} and actual['powers'] == {1: 7.}
    assert result['points'][1]['condition']['alpha'] == 4.
    assert result['points'][1]['error'] == dict(type='ValueError', message='retained numerical failure')


@pytest.mark.parametrize('change', [
    {'condition': {'speed': 0}}, {'condition': {'unknown': 2}},
    {'condition': {'controls': {'99': 1}}}, {'condition': {'controls': {'1': float('nan')}}},
    {'condition': {'circulation_modes': {'1': 200}}}, {'condition': {'mach': 1}},
    {'condition': {'mach': -.1}}, {'condition': {'speed': 600, 'mach': None}},
    {'condition': {'gust': {'type': 'not-a-gust'}}}, {'condition': {'rates': [1, 2]}},
    {'name': ''}, {'panels': 8},
    {'operating_constraints': [{'variable': 'alpha', 'quantity': 'not-a-quantity'}]},
    {'operating_constraints': [{'variable': 'alpha', 'quantity': 'CL', 'target': None}]},
])
def test_invalid_later_point_rejects_entire_stack_before_solve(monkeypatch, change):
    monkeypatch.setattr(bridge, '_solve_steady', lambda *a, **kw: pytest.fail('Invalid plan reached a solve'))
    with pytest.raises(ValueError):
        bridge.dispatch(request([{}, change], mode='mounted'))


@pytest.mark.parametrize('options', [
    {'mode': 'free'}, {'mode': 'structural'}, {'initial_state': {}}, {'unknown': 1},
    {'derivatives': {'unknown': 2}}, {'derivatives': {'step': 1}},
    {'derivatives': {'parameters': ['alpha', 'alpha']}}, {'derivatives': {'parameters': ['control.90']}},
    {'derivatives': {'response': 'unknown'}}, {'derivatives': {'basis': 'unknown'}},
    {'derivatives': {'axes': 'unknown'}}, {'controller': {'outputs': [{'actuator': 'F90', 'terms': []}]}},
    {'loads': [{'beam': 1, 't': 99}]}, {'continuation_steps': 2},
])
def test_invalid_global_options_reject_before_solve(monkeypatch, options):
    monkeypatch.setattr(bridge, '_solve_steady', lambda *a, **kw: pytest.fail('Invalid plan reached a solve'))
    value = request(mode='mounted')
    value.update(options)
    with pytest.raises(ValueError):
        bridge.dispatch(value)


def test_nonlifting_mode_and_source_policy_later_restriction_preflight(monkeypatch):
    monkeypatch.setattr(bridge, '_solve_steady', lambda *a, **kw: pytest.fail('Invalid plan reached a solve'))
    value = request([{}, {'condition': {'circulation_modes': {'1': 1}}}], mode='mounted')
    value['source'] = Path('examples/instrumented-oscillator.asw').read_text()
    with pytest.raises(ValueError, match='nonlifting'):
        bridge.dispatch(value)
    value = request([{}, {'condition': {'rates': [0, 0, .1]}}], mode='mounted', numerics=COUPLED)
    monkeypatch.setattr(bridge, 'parse_asw', lambda *a, **kw: pytest.fail('Policy violation reached parser'))
    with pytest.raises(ValueError, match='requires zero rates'):
        bridge.dispatch(value)


@pytest.mark.parametrize('points', [[], [{}]*201, None])
def test_stack_size_and_shape_limits(monkeypatch, points):
    monkeypatch.setattr(bridge, '_solve_steady', lambda *a, **kw: pytest.fail('Invalid plan reached a solve'))
    value = request()
    value['operating_points']['points'] = points
    with pytest.raises(ValueError, match='between 1 and 200'):
        bridge.dispatch(value)


def test_browser_json_stack_boundary_is_finite_and_names_are_stable():
    value = request([dict(name='A', condition=dict(alpha=2.)), {}])
    result = json.loads(bridge.run_json(json.dumps(value)))
    assert result['analysis'] == 'operating_points' and result['converged']
    assert [row['name'] for row in result['points']] == ['A', 'Point 2']
    assert result['points'][1]['condition']['alpha'] == 2.
