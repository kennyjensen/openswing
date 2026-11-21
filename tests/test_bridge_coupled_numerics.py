"""Source-coupled request checks using stubs; no residuals or solves."""
from copy import deepcopy
from types import ModuleType
import sys

import pytest

from openswing import bridge
from openswing.numerical_policy import (
    SOURCE_DISCRETE, SOURCE_SECTION, SOURCE_COUPLED, default_policy, request_policy,
)
from test_bridge_numerics import CURVE, PANELS, request


COUPLED = dict(beam_interpolation='drela-segspl-v1', structural_operator=SOURCE_COUPLED)
POLICIES = [default_policy(), *[
    dict(beam_interpolation='drela-segspl-v1', structural_operator=operator)
    for operator in (SOURCE_DISCRETE, SOURCE_SECTION, SOURCE_COUPLED)
]]


def test_fourth_pair_is_explicit_and_defaults_remain_distinct():
    original = deepcopy(COUPLED)
    assert request_policy({'numerics': COUPLED}) == COUPLED
    assert COUPLED == original
    assert len({p['structural_operator'] for p in POLICIES}) == 4
    for value in (dict(COUPLED, beam_interpolation='natural-v1'), dict(COUPLED, extra=1)):
        with pytest.raises(ValueError):
            request_policy({'numerics': value})


@pytest.mark.parametrize('action', ['inspect', 'distribution', 'edit_distribution', 'canonical_asw'])
def test_coupled_parse_edit_requests_preserve_policy(action):
    options = dict(source=CURVE, numerics=COUPLED)
    if action in ('distribution', 'edit_distribution'):
        options.update(beam=1, name='EA')
    if action == 'edit_distribution':
        options['edit'] = dict(multiplier=2)
    value = request(action, **options)
    original = deepcopy(value)
    result = bridge.dispatch(value)
    assert result['numerics'] == COUPLED and value == original
    if action == 'distribution':
        assert result['segments'][0]['values'][20] == pytest.approx(1750.)
    if action == 'inspect':
        assert not result['mass_properties_scope']['selected_operator_mass']
        assert not result['mass_properties_scope']['dynamic_inertia_validated']
        assert 'endpoint-CG gravity couples' in result['mass_properties_scope']['selected_weight_rule']


def test_coupled_route_forwards_condition_and_options_without_reinterpretation(monkeypatch):
    seen = {}
    kernel = ModuleType('openswing.source_coupled')
    def solve(model, condition, panels, **options):
        seen.update(model=model, condition=condition, panels=panels, options=options)
        return dict(analysis='mounted_static', structural_operator=SOURCE_COUPLED,
                    strips=[{'force': [0, 0, 2]}], mass_properties={'inertia_cg': None})
    kernel.solve_source_coupled = solve
    monkeypatch.setitem(sys.modules, 'openswing.source_coupled', kernel)
    monkeypatch.setattr(bridge, 'solve_static', lambda *a, **k: pytest.fail('Default solver used'))
    condition = dict(speed=10., alpha=4., beta=2., density=1.23, mach=0.,
        rates=[0., 0., 0.], acceleration=[0., 0., 0.], angular_acceleration=[0., 0., 0.],
        controls={'1': 3.}, powers={}, freeze_influences=True, ground_effect=1,
        ground_normal=[0., 1., 0.], position_earth=[0., 0., 0.], attitude=[0., 0., 0.],
        gust={'type': 'uniform', 'velocity': [0., 0., .5]}, time=2.)
    seed = {'identity': COUPLED}
    value = request('solve', mode='mounted', numerics=COUPLED, condition=condition,
        initial_state=seed, gravity=[0., 0., -9.81], loads=[dict(beam=1, t=3, moment=[0., .1, 0.])],
        tolerance=2e-9, continuation_steps=3,
        operating_constraints=[dict(variable='alpha', quantity='CL', target=.4)],
        controller=None, derivatives=None, strut_mode='bilateral')
    original = deepcopy(value)
    progress = lambda *a: None
    result = bridge.dispatch(value, progress)
    assert seen['model'].beam_interpolation == 'drela-segspl-v1'
    assert seen['panels'] == PANELS
    for name, expected in condition.items():
        assert getattr(seen['condition'], name) == ({1: 3.} if name == 'controls' else expected)
    assert seen['options'] == dict(gravity=value['gravity'], loads=value['loads'],
        initial_state=seed, progress=progress, tolerance=2e-9, continuation_steps=3,
        operating_constraints=value['operating_constraints'], strut_mode='bilateral')
    assert result['numerics'] == COUPLED and result['analysis'] == 'mounted_static'
    assert result['strips'] == [{'force': [0, 0, 2]}]
    assert 'structural_only' not in result and value == original


@pytest.mark.parametrize('requested', POLICIES)
@pytest.mark.parametrize('saved', POLICIES)
def test_all_policy_identities_checked_before_dispatch(monkeypatch, requested, saved):
    monkeypatch.setattr(bridge, '_dispatch', lambda request, progress, policy: {'received': policy})
    coupled = requested['structural_operator'] == SOURCE_COUPLED
    value = request('solve', mode='mounted' if coupled else 'structural',
        condition={} if coupled else None, numerics=requested, initial_state={'identity': saved})
    if requested != saved:
        with pytest.raises(ValueError, match='Saved state numerical policy'):
            bridge.dispatch(value)
    else:
        assert bridge.dispatch(value)['received'] == requested


@pytest.mark.parametrize('mode', ['structural', 'rigid', 'free', 'modes', 'frequency', 'time'])
def test_coupled_only_accepts_mounted_mode_before_parse(monkeypatch, mode):
    monkeypatch.setattr(bridge, 'parse_asw', lambda *a, **k: pytest.fail('Reached parser'))
    with pytest.raises(ValueError, match='requires solve mode mounted'):
        bridge.dispatch(request('solve', mode=mode, condition={}, numerics=COUPLED))


@pytest.mark.parametrize('action', ['time', 'modes', 'frequency', 'rom', 'stability',
    'resume_time', 'launch_time', 'flow_survey', 'extend_frequency', 'discard_frequency',
    'steady_turn_constraints', 'reference_airflow_constraints', 'gust_import', 'gust_export',
    'gust_sample', 'gust_validate', 'rom_import'])
def test_coupled_rejects_unsupported_actions_before_parse(monkeypatch, action):
    monkeypatch.setattr(bridge, 'parse_asw', lambda *a, **k: pytest.fail('Reached parser'))
    with pytest.raises(ValueError, match='mounted steady solves only'):
        bridge.dispatch(request(action, numerics=COUPLED))


@pytest.mark.parametrize('name', ['rates', 'acceleration', 'angular_acceleration'])
@pytest.mark.parametrize('value', [[0., .1, 0.], [0., 0.], None, [0., float('nan'), 0.], [False, 0., 0.]])
def test_coupled_rejects_nonzero_or_invalid_motion_before_parse(monkeypatch, name, value):
    monkeypatch.setattr(bridge, 'parse_asw', lambda *a, **k: pytest.fail('Reached parser'))
    with pytest.raises(ValueError, match='requires zero '+name):
        bridge.dispatch(request('solve', mode='mounted', condition={name: value}, numerics=COUPLED))


@pytest.mark.parametrize('extra', [
    {'condition': None}, {'condition': []}, {'controller': {}}, {'derivatives': {}},
    {'operating_constraints': [dict(variable='rates.x', quantity='Cl', target=0)]},
    {'operating_constraints': [dict(variable='acceleration.z', quantity='force.z', target=0)]},
    {'operating_constraints': [dict(variable='angular_acceleration.y', quantity='moment.y', target=0)]},
    {'operating_constraints': None}, {'operating_constraints': ['alpha']},
    {'strut_mode': 'unknown'}, {'motion': {}},
    {'time': {}}, {'frequency': {}}, {'allow_signed_point_weights': True},
    {'loads': [dict(beam=1, t=3, force=[0, 1, 0], follower=True)]},
])
def test_coupled_does_not_silently_ignore_unsupported_options(monkeypatch, extra):
    monkeypatch.setattr(bridge, 'parse_asw', lambda *a, **k: pytest.fail('Reached parser'))
    value = request('solve', mode='mounted', condition={}, numerics=COUPLED)
    value.update(extra)
    with pytest.raises(ValueError):
        bridge.dispatch(value)
