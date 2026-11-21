"""Moving-vacuum boundary checks and intercepted dispatch; no numerical solves."""
from copy import deepcopy
import pytest
from openswing.numerical_policy import (
    SOURCE_DYNAMIC, SOURCE_QUIESCENT, SOURCE_MOVING, SOURCE_MODAL,
    default_policy, request_policy, validate_source_request, validate_saved_policy)

POLICY = dict(beam_interpolation='drela-segspl-v1', structural_operator=SOURCE_MOVING)


def request(frame='prescribed'):
    modes = dict(frame=frame, vacuum=True, velocity=[-12., 2., 3.],
                 motion=dict(rates=[.1, -.2, .3], acceleration=[1., 2., 3.],
                             angular_acceleration=[.4, .5, -.6]),
                 position=[7., 8., 9.], attitude=[10., 20., 30.], gravity_magnitude=9.81)
    if frame == 'mixed':
        modes['load_targets'] = {'force.x': 0., 'moment.z': 1.}
    return dict(action='modes', mode='modes', condition=None, source='Unparsed literal',
                numerics=deepcopy(POLICY), modes=modes)


@pytest.mark.parametrize('frame', ['fixed', 'prescribed', 'free', 'mixed'])
def test_explicit_moving_policy_and_direct_motion_are_valid_without_mutation(frame):
    value = request(frame)
    before = deepcopy(value)
    assert SOURCE_MOVING in SOURCE_MODAL
    assert request_policy(value) == POLICY
    validate_source_request(value)
    assert value == before
    assert request_policy({'action': 'modes'}) == default_policy()


@pytest.mark.parametrize('targets', [{}, {'force.y': -2.}, {'moment.x': 1., 'force.z': 0.}])
def test_free_frame_canonical_load_targets(targets):
    value = request('free')
    value['modes']['load_targets'] = targets
    validate_source_request(value)


@pytest.mark.parametrize('action', ['inspect', 'distribution', 'edit_distribution', 'canonical_asw'])
def test_parse_actions_preserve_moving_policy(action):
    value = dict(action=action, source='Unparsed', numerics=deepcopy(POLICY))
    validate_source_request(value)
    assert request_policy(value) == POLICY


@pytest.mark.parametrize('action', ['solve', 'time', 'launch_time', 'resume_time', 'frequency', 'rom', 'stability', 'flow_survey'])
def test_no_new_permission_for_other_routes(action):
    value = request()
    value['action'] = action
    with pytest.raises(ValueError):
        validate_source_request(value)


@pytest.mark.parametrize('field,value', [
    ('frame', 'invalid'), ('vacuum', False), ('vacuum', 1), ('quiescent_density', 1.2),
    ('controller', {}), ('velocity', [0, 1]), ('velocity', [0, True, 2]),
    ('position', [0, float('nan'), 0]), ('attitude', [0, '1', 0]),
    ('gravity_magnitude', -1), ('gravity_magnitude', True),
    ('motion', []), ('motion', {'speed': 10}), ('motion', {'rates': [0, float('inf'), 0]}),
    ('motion', {'acceleration': [0, False, 0]}), ('motion', {'angular_acceleration': [0, 0]}),
    ('load_targets', {'lift': 1}), ('load_targets', {'force.x': True}),
    ('load_targets', {'moment.z': float('nan')}), ('load_targets', []),
    ('condition', {'speed': 1}), ('structural_operator', SOURCE_DYNAMIC),
])
def test_unsafe_or_malformed_modal_options_fail(field, value):
    payload = request('free')
    payload['modes'][field] = value
    with pytest.raises(ValueError):
        validate_source_request(payload)


@pytest.mark.parametrize('field,value', [
    ('condition', {'speed': 0}), ('controller', None), ('derivatives', {}),
    ('operating_constraints', [{'variable': 'speed', 'quantity': 'lift'}]),
    ('gravity', [0, 0, -9.81]), ('strut_mode', 'unknown'),
])
def test_unsupported_top_level_options_reject(field, value):
    payload = request()
    payload[field] = value
    with pytest.raises(ValueError):
        validate_source_request(payload)


def test_frame_targets_must_match_declared_frame():
    for frame in ('fixed', 'prescribed'):
        payload = request(frame)
        payload['modes']['load_targets'] = {'force.x': 0.}
        with pytest.raises(ValueError, match='cannot have'):
            validate_source_request(payload)
    payload = request('mixed')
    payload['modes'].pop('load_targets')
    with pytest.raises(ValueError, match='at least one'):
        validate_source_request(payload)


def test_saved_policy_cannot_silently_downgrade_to_old_vacuum_or_default():
    payload = request()
    payload['modes']['initial_state'] = {'identity': deepcopy(POLICY)}
    validate_saved_policy(payload, POLICY)
    for policy in (default_policy(), dict(POLICY, structural_operator=SOURCE_DYNAMIC),
                   dict(POLICY, structural_operator=SOURCE_QUIESCENT)):
        with pytest.raises(ValueError, match='does not match'):
            validate_saved_policy(payload, policy)
    payload['numerics']['beam_interpolation'] = 'natural-v1'
    with pytest.raises(ValueError, match='Conflicting'):
        request_policy(payload)


@pytest.mark.parametrize('operator', [SOURCE_DYNAMIC, SOURCE_QUIESCENT])
def test_old_fixed_policies_do_not_acquire_moving_permission(operator):
    payload = request('free')
    payload['numerics']['structural_operator'] = operator
    if operator == SOURCE_QUIESCENT:
        payload['modes'].update(vacuum=False, quiescent_density=1.2)
    with pytest.raises(ValueError):
        validate_source_request(payload)


@pytest.mark.parametrize('motion_kind', ['absent', 'null', 'dict'])
def test_dispatch_preserves_optional_motion_and_decodes_only_dictionary(monkeypatch, motion_kind):
    """Real parsing/routing, but an intercepted solver makes this a no-solve test."""
    from pathlib import Path
    from openswing.bridge import dispatch
    from openswing import linear_dynamics
    from openswing.inertia import Motion

    source = (Path(__file__).resolve().parents[1] / 'examples' /
              'source-moving-vacuum-check.asw').read_text()
    payload = request('prescribed')
    payload.update(source=source, panels=4)
    physical_motion = deepcopy(payload['modes']['motion'])
    if motion_kind == 'absent':
        payload['modes'].pop('motion')
    elif motion_kind == 'null':
        payload['modes']['motion'] = None
    before = deepcopy(payload)
    calls = []

    def sentinel(model, condition, panels, **options):
        assert model.beam_interpolation == POLICY['beam_interpolation']
        assert model.dumps() == source
        assert condition is None
        assert options['structural_operator'] == SOURCE_MOVING
        if motion_kind == 'absent':
            assert 'motion' not in options
        elif motion_kind == 'null':
            assert options['motion'] is None
        else:
            assert isinstance(options['motion'], Motion)
            for field, values in physical_motion.items():
                assert getattr(options['motion'], field).tolist() == values
        calls.append((model, panels, options))
        return {'sentinel_without_physical_solve': True}

    monkeypatch.setattr(linear_dynamics, 'solve_modes', sentinel)
    result = dispatch(payload)
    assert len(calls) == 1
    assert payload == before
    assert result == dict(sentinel_without_physical_solve=True,
                         numerics=POLICY, structural_operator=SOURCE_MOVING)
