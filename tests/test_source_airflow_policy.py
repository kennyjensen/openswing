"""Airflow source policy must preserve the medium and reject unsupported inputs."""
from copy import deepcopy
import pytest

from openswing.numerical_policy import validate_source_request
from test_source_airflow_time import POLICY, SOURCE, CONDITION, PANELS, request as time_request


def request(action):
    if action == 'time':
        return time_request(.002)
    return dict(action=action, mode=action, source=SOURCE, panels=deepcopy(PANELS),
        condition=deepcopy(CONDITION), numerics=deepcopy(POLICY),
        **{action: dict(frame='prescribed', **(dict(inputs=['control.1'], frequencies=[1.,10.])
                                              if action == 'frequency' else {}))})


@pytest.mark.parametrize('action', ['modes','frequency','time'])
def test_airflow_request_keeps_flight_condition(action):
    value = request(action); before = deepcopy(value)
    validate_source_request(value)
    assert value == before
    value['condition'] = None
    with pytest.raises(ValueError, match='FlightCondition'):
        validate_source_request(value)


@pytest.mark.parametrize('action', ['modes','frequency','time'])
@pytest.mark.parametrize('change', [dict(vacuum=True), dict(quiescent_density=1.2),
    dict(velocity=[0.,0.,0.]), dict(motion={'rates':[0.,0.,0.]}),
    dict(frame='mixed', load_targets={'lift':0.})])
def test_other_media_and_unsupported_motion_inputs_do_not_fall_back(action, change):
    value = request(action); value[action].update(change)
    with pytest.raises(ValueError):
        validate_source_request(value)


@pytest.mark.parametrize('action', ['modes','frequency','time'])
def test_source_airflow_policy_preserves_controller(action):
    from test_source_airflow_feedback import strip_law
    value = request(action); value[action]['controller'] = strip_law()
    before = deepcopy(value)
    validate_source_request(value)
    assert value == before
