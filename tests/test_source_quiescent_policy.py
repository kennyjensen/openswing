"""The source still-air extension has a distinct, bounded request contract."""
from copy import deepcopy
import pytest
from openswing.bridge import dispatch
from openswing.numerical_policy import request_policy, validate_source_request


def request():
    return dict(action='modes', source='must not be parsed for invalid requests',
        numerics=dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-fixed-still-air-v1'),
        condition=None, modes=dict(frame='fixed', vacuum=False, quiescent_density=1.225))


def test_explicit_positive_density_and_fixed_frame_are_accepted():
    value = request()
    assert request_policy(value) == value['numerics']
    validate_source_request(value)
    del value['modes']['vacuum']
    validate_source_request(value)


@pytest.mark.parametrize('change', [
    {'action': 'time'}, {'action': 'frequency'}, {'action': 'launch_time'},
    {'action': 'resume_time'}, {'action': 'rom'}, {'action': 'stability'},
    {'action': 'solve', 'mode': 'structural'}, {'condition': {'speed': 0}},
    {'mode': 'mounted'}, {'controller': {}}, {'quiescent_density': 1.225},
    {'operating_constraints': [{'variable': 'alpha', 'quantity': 'lift'}]},
])
def test_rejected_routes_do_not_parse_model(change):
    value = request(); value.update(change)
    with pytest.raises(ValueError):
        dispatch(value)


@pytest.mark.parametrize('change', [
    {'frame': 'free'}, {'vacuum': True}, {'vacuum': 0}, {'vacuum': None},
    {'quiescent_density': None}, {'quiescent_density': 0}, {'quiescent_density': -1},
    {'quiescent_density': True}, {'quiescent_density': float('nan')},
    {'quiescent_density': float('inf')}, {'quiescent_density': '1.225'},
    {'controller': {}}, {'load_targets': {'force.z': 0}},
    {'velocity': [0, 0, 0]}, {'structural_operator': 'midpoint-v1'},
])
def test_unsupported_modal_settings_do_not_parse_model(change):
    value = request(); value['modes'].update(deepcopy(change))
    with pytest.raises(ValueError):
        dispatch(value)
