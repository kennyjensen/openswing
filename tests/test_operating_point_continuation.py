"""Physical continuation preserves prescribed targets and failed-point gaps."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pytest

from openswing import bridge
from openswing.aero import solve_rigid, FlightCondition
from openswing.asw import parse_asw
from test_operating_points import request, SOURCE, COUPLED


def warm(points, **kwargs):
    value = request(points, **kwargs)
    value['operating_points']['initialization'] = 'previous'
    return value


def test_rigid_continuation_reuses_physical_circulation_and_rechecks_new_conditions():
    value = warm([{'condition': {'alpha': a}} for a in [2., 4., 4., -1.]])
    original = deepcopy(value)
    out = bridge.dispatch(value)
    assert value == original and out['converged'] and out['initialization'] == 'previous'
    for i, point in enumerate(out['points']):
        expected = solve_rigid(parse_asw(SOURCE), FlightCondition(**point['condition']), 4)
        np.testing.assert_allclose(point['result']['force'], expected['force'], rtol=1e-8, atol=1e-8)
        assert point['actual_condition'] == point['condition']
        assert point['result']['residual'] < 1e-8
        if i:
            start = point['initialization']
            assert start['kind'] == 'previous_point' and start['source_index'] == i-1
            assert not start['cold_fallback']
            seed = point['result']['circulation_solver']['initialization']
            assert seed['seed_attempt']['accepted']
            np.testing.assert_array_equal(seed['initial_circulation'],
                [s['circulation'] for s in out['points'][i-1]['result']['strips']])
        else:
            assert point['initialization']['kind'] == 'cold'


@pytest.mark.parametrize('numerics', [None, COUPLED])
def test_flexible_mounted_continuation_matches_independent_solves(numerics):
    value = warm([{'condition': {'alpha': a}} for a in [2., 3., 3.]],
                 mode='mounted', gravity=[0., 0., 0.])
    value['source'] = Path('tests/data/seeded-corrector-flexible.asw').read_text()
    if numerics is not None:
        value['numerics'] = numerics
    original = deepcopy(value)
    out = bridge.dispatch(value)
    assert out['converged'], [p['error'] for p in out['points']]
    assert value == original
    for i, point in enumerate(out['points']):
        direct = bridge.dispatch({**{k: v for k, v in value.items() if k != 'operating_points'},
                                  'action': 'solve', 'condition': point['condition']})
        assert point['result']['residual'] < 1e-8
        for key in ('positions', 'circulation', 'internal_force', 'internal_moment'):
            np.testing.assert_allclose(point['result']['equilibrium_state'][key],
                direct['equilibrium_state'][key], rtol=2e-7, atol=2e-7)
        if i:
            assert point['initialization']['source_index'] == i-1
            assert point['result']['equilibrium_initialization']['initialization'] == 'saved physical equilibrium'


def test_new_trim_target_is_corrected_and_released_alpha_is_prescribed_again():
    value = warm([{'operating_constraints': [dict(variable='alpha', quantity='CL', target=.2)]},
                  {'operating_constraints': [dict(variable='alpha', quantity='CL', target=.3)]},
                  {'operating_constraints': []}], mode='mounted', gravity=[0, 0, 0])
    out = bridge.dispatch(value)
    assert out['converged']
    for p, cl in zip(out['points'], [.2, .3, 0.]):
        assert p['condition']['alpha'] == 0.
        assert p['result']['CL'] == pytest.approx(cl, abs=1e-8)
    assert out['points'][2]['actual_condition']['alpha'] == 0.
    assert out['points'][2]['initialization']['kind'] == 'previous_point'


@pytest.mark.parametrize('mode', ['rigid', 'mounted'])
def test_failed_circulation_is_not_propagated_and_next_point_starts_cold(mode):
    out = bridge.dispatch(warm([{'condition': {'alpha': 3.}},
        {'condition': {'alpha': 89., 'speed': 600.}}, {'condition': {'alpha': 3., 'speed': 30.}},
        {'condition': {'alpha': 4.}}], mode=mode))
    assert [p['converged'] for p in out['points']] == [True, False, True, True]
    assert 'Mach' in out['points'][1]['error']['message']
    assert out['points'][1]['initialization']['source_index'] == 0
    assert out['points'][2]['initialization']['kind'] == 'cold'
    assert 'failed' in out['points'][2]['initialization']['reason']
    assert out['points'][3]['initialization']['source_index'] == 2


@pytest.mark.parametrize('mode', ['rigid', 'mounted'])
def test_changed_circulation_basis_starts_cold_and_same_basis_then_continues(mode):
    value = warm([{}, {'condition': {'circulation_modes': {'1': 2}}}, {}], mode=mode)
    out = bridge.dispatch(value)
    assert out['converged'], [p['error'] for p in out['points']]
    assert out['points'][1]['initialization']['kind'] == 'cold'
    assert out['points'][1]['initialization']['reason'] == 'Circulation discretization changed.'
    assert out['points'][2]['initialization']['source_index'] == 1


def test_controller_trim_release_restores_prescribed_command_without_seed_leakage():
    from test_feedback import configuration, condition, law
    controller = law(kd=0)
    controller['commands'] = {'RY[2]': 2., 'UY[2]': 0.}
    targets = [dict(variable='command.E1', quantity='force.y', target=5.)]
    value = warm([{'operating_constraints': targets}, {}, {'operating_constraints': []}, {}],
                 mode='mounted', controller=controller, gravity=[0, 0, 0])
    value.update(source=configuration().dumps(), condition=asdict(condition()))
    out = bridge.dispatch(value)
    assert out['converged'], [p['error'] for p in out['points']]
    first, continued, released, last = out['points']
    assert first['result']['feedback']['commands']['E1'] == pytest.approx(7., abs=1e-7)
    assert continued['initialization']['kind'] == 'previous_point'
    assert released['initialization']['kind'] == 'cold'
    assert 'released from trim' in released['initialization']['reason']
    assert released['result']['feedback']['commands']['E1'] == 0.
    assert last['initialization']['kind'] == 'previous_point'
    assert last['result']['feedback']['commands']['E1'] == 0.


def test_implicit_controller_command_does_not_silently_change_between_points():
    from test_feedback import configuration, condition, law
    value = warm([{}, {'condition': {'powers': {'1': 3.}}}], mode='mounted',
                 controller=law(kd=0), gravity=[0, 0, 0])
    value.update(source=configuration().dumps(), condition=asdict(condition()))
    out = bridge.dispatch(value)
    assert out['converged']
    assert out['points'][1]['initialization']['kind'] == 'cold'
    assert 'Implicit controller' in out['points'][1]['initialization']['reason']
    assert out['points'][1]['result']['feedback']['actuators']['E1'] == pytest.approx(3., abs=1e-7)


@pytest.mark.parametrize('options', [{'initialization': 'unknown'}, {'initialization': True},
    {'initialization': []}, {'initialization': 'previous', 'unknown': 1}])
def test_invalid_initialization_rejects_before_solving(monkeypatch, options):
    value = request()
    value['operating_points'].update(options)
    monkeypatch.setattr(bridge, '_solve_steady', lambda *a, **kw: pytest.fail('Invalid input reached solve'))
    with pytest.raises(ValueError):
        bridge.dispatch(value)


def test_explicit_circulation_continuation_cannot_be_combined_with_a_previous_seed(monkeypatch):
    monkeypatch.setattr(bridge, '_solve_steady', lambda *a, **kw: pytest.fail('Invalid input reached solve'))
    with pytest.raises(ValueError, match='explicit circulation continuation'):
        bridge.dispatch(warm([{}, {}], circulation_method='continuation'))
