"""Checkpoint numeric spelling changes in browser JSON retain exact identity."""
from copy import deepcopy
import json
import pytest
from openswing.aero import AnalysisError
from openswing.asw import parse_asw
from openswing.time_state import restore_checkpoint, resume_time, checkpoint
from radau_fixture import INPUTS, saved, check


def browser_numbers(value):
    # JSON.stringify writes integral doubles (including signed zero) as integers.
    # The production-browser workflow separately exercises actual JS transport.
    if isinstance(value, dict):
        return {key: browser_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [browser_numbers(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


@pytest.mark.parametrize('order', [1, 2, 5])
def test_browser_json_checkpoint_replays_and_continues_without_rewriting_history(order):
    model = parse_asw((INPUTS/'rigid.asw').read_text())
    cp = json.loads(json.dumps(browser_numbers(saved())))
    before = deepcopy(cp)
    result = resume_time(model, cp, duration=.02, dt=.02, order=order)
    assert cp == before
    assert result['checkpoint_validation']['discrete_replayed']
    assert result['snapshots'][0]['restart']['accepted_method'] == cp['accepted_method']
    assert result['accepted_steps'] == 1 and result['rejected_steps'] == 0
    check(result, model)
    restore_checkpoint(model, browser_numbers(checkpoint(result, -1)))


@pytest.mark.parametrize('edit', [
    lambda d: d['rows'][0].__setitem__(2, 1e-15),
    lambda d: d['rows'][0].__setitem__(2, False),
    lambda d: d['rows'][0].__setitem__(2, '0'),
    lambda d: d['channels'][0].__setitem__('factor', 1.000000000000001),
    lambda d: d['channels'][0].__setitem__('offset', False),
    lambda d: d['mask'].__setitem__(1, 0),
    lambda d: d.__setitem__('version', True),
    lambda d: d.__setitem__('extra', 0),
    lambda d: d.pop('support'),
])
def test_changed_definition_is_rejected_even_below_numerical_tolerance(edit):
    model = parse_asw((INPUTS/'rigid.asw').read_text())
    cp = browser_numbers(saved())
    edit(cp['context']['method']['position_history']['definition'])
    with pytest.raises(AnalysisError, match='position-history definition'):
        restore_checkpoint(model, cp)


def test_signed_zero_spelling_keeps_existing_signature():
    model = parse_asw((INPUTS/'rigid.asw').read_text())
    cp = saved()
    original = cp['context']['method']['position_history']['signature']
    cp['context']['method']['position_history']['definition']['rows'][0][2] = -0.0
    restore_checkpoint(model, cp)
    assert cp['context']['method']['position_history']['signature'] == original
