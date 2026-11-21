"""Source modal requests preserve their explicit equations and scope."""
from copy import deepcopy
import pytest

from openswing.bridge import dispatch
from openswing.numerical_policy import (SOURCE_DYNAMIC, request_policy,
    validate_source_request, validate_saved_policy)


POLICY = dict(beam_interpolation='drela-segspl-v1', structural_operator=SOURCE_DYNAMIC)


def request(**kwargs):
    return dict(action='modes', source='not parsed for boundary checks',
        numerics=deepcopy(POLICY), modes=dict(frame='fixed', vacuum=True), **kwargs)


def test_source_modal_policy_requires_complete_pair_and_exact_saved_identity():
    value = request()
    assert request_policy(value) == POLICY
    validate_source_request(value)
    for operator in ('midpoint-v1', 'drela-steady-section-v1', 'drela-steady-coupled-v1'):
        value['modes']['initial_state'] = dict(identity={**POLICY, 'structural_operator': operator})
        with pytest.raises(ValueError, match='does not match'):
            validate_saved_policy(value, POLICY)
    value['modes']['initial_state']['identity'] = deepcopy(POLICY)
    validate_saved_policy(value, POLICY)
    value['numerics']['beam_interpolation'] = 'natural-v1'
    with pytest.raises(ValueError, match='Conflicting'):
        request_policy(value)


@pytest.mark.parametrize('change', [
    {'action': 'solve', 'mode': 'structural'},
    {'action': 'frequency'}, {'action': 'time'}, {'action': 'launch_time'},
    {'condition': {'speed': 1}}, {'mode': 'mounted'},
    {'operating_constraints': [{'variable': 'alpha', 'quantity': 'lift'}]},
    {'strut_mode': 'unknown'}, {'loads': [{'beam': 1, 't': 1, 'follower': True}]},
    {'modes': {'frame': 'free'}}, {'modes': {'quiescent_density': 1.2}},
    {'modes': {'vacuum': False}}, {'modes': {'vacuum': 1}},
    {'modes': {'controller': {}}}, {'modes': {'load_targets': {'force.z': 0}}},
    {'modes': {'structural_operator': 'midpoint-v1'}},
    {'modes': {'unsupported': True}},
])
def test_source_modal_boundary_rejects_unimplemented_settings_before_parsing(change):
    value = request()
    value.update(change)
    with pytest.raises(ValueError):
        dispatch(value)


def test_old_static_policy_does_not_acquire_dynamic_permission():
    value = request()
    for operator in ('drela-steady-zero-offset-v1', 'drela-steady-section-v1', 'drela-steady-coupled-v1'):
        value['numerics']['structural_operator'] = operator
        with pytest.raises(ValueError, match='only'):
            validate_source_request(value)
