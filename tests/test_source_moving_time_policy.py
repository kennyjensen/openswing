"""Explicit source moving time boundary: validation and intercepted dispatch only."""
from copy import deepcopy
from pathlib import Path
import pytest
from openswing.numerical_policy import (SOURCE_MOVING, SOURCE_DYNAMIC, SOURCE_QUIESCENT,
    default_policy, validate_source_request, validate_saved_policy)

POLICY = dict(beam_interpolation='drela-segspl-v1', structural_operator=SOURCE_MOVING)


def seed():
    return dict(format='openswing-equilibrium', version=1, positions=[[0, 0, 0]],
                identity=deepcopy(POLICY), launch=dict(condition=None, controller=None))


def checkpoint():
    return dict(format='openswing-time-checkpoint', version=1, state=dict(time=.1),
                context=dict(identity=deepcopy(POLICY), method=dict(order=2),
                             setup=dict(condition=None, controller=None, frame='prescribed')))


def request(action='time', frame='prescribed', order=2):
    options = dict(duration=.1, dt=.01, order=order, forcing='', accuracy={'rtol':.001, 'atol':1e-6})
    value = dict(action=action, source='Not parsed in validation', numerics=deepcopy(POLICY), time=options)
    if action != 'resume_time':
        options['frame'] = frame
        if frame == 'mixed':
            options['load_targets'] = {'force.x': 0.}
    if action == 'time':
        value.update(mode='time', condition=None, panels=4)
        options.update(velocity=[1., 2., 3.], position=[1., 0., 2.], attitude=[10., 20., 30.], gravity_magnitude=0.,
                       motion=dict(rates=[.1, .2, .3], acceleration=[1., 2., 3.], angular_acceleration=[.4, .5, .6]))
    elif action == 'launch_time':
        value['equilibrium_state'] = seed()
    else:
        value['checkpoint'] = checkpoint()
    return value


@pytest.mark.parametrize('action', ['time', 'launch_time', 'resume_time'])
@pytest.mark.parametrize('order', [1, 2, 5])
def test_time_routes_and_standard_orders_preserve_request(action, order):
    payload = request(action, order=order); before = deepcopy(payload)
    validate_source_request(payload); validate_saved_policy(payload, POLICY)
    assert payload == before


@pytest.mark.parametrize('frame', ['prescribed', 'free', 'mixed'])
def test_canonical_frame_targets_and_launch_disturbance(frame):
    for action in ('time', 'launch_time'):
        payload = request(action, frame)
        if action == 'launch_time':
            payload['time'].update(disturbance={'frame': {'velocity': [0., .1, 0.]}},
                                   initial_difference_step=.01, initial_rank_tolerance=1e-7)
        validate_source_request(payload)


@pytest.mark.parametrize('operator', [SOURCE_DYNAMIC, SOURCE_QUIESCENT])
@pytest.mark.parametrize('action', ['time', 'launch_time', 'resume_time'])
def test_old_fixed_source_policies_remain_modal_only(operator, action):
    payload = request(action); payload['numerics']['structural_operator'] = operator
    with pytest.raises(ValueError):
        validate_source_request(payload)


@pytest.mark.parametrize('change', [
    {'condition': {'speed': 0}}, {'controller': None}, {'operating_constraints': []},
    {'gravity': [0, 0, 0]}, {'mode': 'modes'}, {'strut_mode': 'unknown'},
    {'initial_loads': [{'beam': 1, 't': 0, 'follower': True}]},
])
def test_cold_top_level_unsupported_options(change):
    payload = request(); payload.update(change)
    with pytest.raises(ValueError):
        validate_source_request(payload)


@pytest.mark.parametrize('change', [
    {'frame': 'fixed'}, {'frame': 'mixed'}, {'vacuum': True}, {'quiescent_density': 1.2},
    {'controller': {}}, {'actuator_constraints': [{'variable': 'control.1'}]},
    {'velocity': [0, True, 0]}, {'motion': {'rates': [0, float('nan'), 0]}},
    {'gravity_magnitude': -1}, {'duration': 0}, {'duration': True}, {'dt': float('inf')},
    {'order': 3}, {'order': True}, {'forcing': {}}, {'load_targets': {'lift': 0}},
    {'disturbance': {'frame': {'velocity': [1, 0, 0]}}},
])
def test_cold_options_do_not_silently_enable_other_physics(change):
    payload = request(); payload['time'].update(change)
    with pytest.raises(ValueError):
        validate_source_request(payload)


@pytest.mark.parametrize('action', ['launch_time', 'resume_time'])
@pytest.mark.parametrize('key', ['velocity', 'motion', 'position', 'attitude', 'gravity_magnitude', 'condition'])
def test_saved_routes_cannot_replace_saved_setup(action, key):
    payload = request(action); payload['time'][key] = [0, 0, 0]
    with pytest.raises(ValueError):
        validate_source_request(payload)


@pytest.mark.parametrize('action', ['launch_time', 'resume_time'])
def test_saved_policy_mismatch_and_unsupported_saved_medium_reject(action):
    payload = request(action)
    container = payload['equilibrium_state'] if action == 'launch_time' else payload['checkpoint']['context']
    container['identity'] = default_policy()
    with pytest.raises(ValueError):
        validate_source_request(payload)
    container['identity'] = deepcopy(POLICY)
    with pytest.raises(ValueError, match='does not match'):
        validate_saved_policy(payload, default_policy())
    setup = container['launch' if action == 'launch_time' else 'setup']
    for key, value in [('condition', {'speed': 0}), ('controller', {}), ('quiescent_density', 1.2),
                       ('actuator_constraints', [{}])]:
        bad = deepcopy(payload)
        stored = bad['equilibrium_state']['launch'] if action == 'launch_time' else bad['checkpoint']['context']['setup']
        stored[key] = value
        with pytest.raises(ValueError):
            validate_source_request(bad)


def test_null_forcing_only_means_keep_saved_table_on_resume():
    for action in ('time', 'launch_time', 'resume_time'):
        payload = request(action); payload['time']['forcing'] = None
        if action == 'resume_time':
            validate_source_request(payload)
        else:
            with pytest.raises(ValueError, match='forcing'):
                validate_source_request(payload)


@pytest.mark.parametrize('action,module,function', [
    ('time', 'openswing.time_integration', 'solve_time'),
    ('launch_time', 'openswing.time_initialization', 'launch_time'),
    ('resume_time', 'openswing.time_state', 'resume_time'),
])
def test_dispatch_routes_source_time_without_physical_solve(monkeypatch, action, module, function):
    import importlib
    from openswing.bridge import dispatch
    from openswing.inertia import Motion
    payload = request(action)
    payload['source'] = (Path(__file__).resolve().parents[1] / 'examples/source-moving-vacuum-check.asw').read_text()
    before = deepcopy(payload); calls = []
    def sentinel(model, argument, *args, **options):
        assert model.beam_interpolation == POLICY['beam_interpolation']
        if action == 'time':
            assert argument is None
            assert options['structural_operator'] == SOURCE_MOVING
            assert isinstance(options['motion'], Motion)
            assert options['motion'].rates.tolist() == payload['time']['motion']['rates']
            assert options['gravity_magnitude'] == 0.
        else:
            assert argument == payload['equilibrium_state' if action == 'launch_time' else 'checkpoint']
        calls.append(options)
        return {'sentinel_no_physics': True}
    monkeypatch.setattr(importlib.import_module(module), function, sentinel)
    result = dispatch(payload)
    assert len(calls) == 1 and result['sentinel_no_physics']
    assert result['numerics'] == POLICY
    assert payload == before
