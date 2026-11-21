"""A terminal forcing cutoff owns a valid BDF2 record but no next-step history."""
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1]/'scripts/isae_ua2_browser_cutoff.py'
SPEC = importlib.util.spec_from_file_location('isae_ua2_browser_cutoff_test', SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture(final=True):
    states = [dict(time=float(i), value=[i+.25]) for i in range(3)]
    side = 'left' if final else 'right'
    accepted = dict(kind='bdf', scheme='drela-euler-bdf-v1', effective_order=2,
        endpoint=dict(state=deepcopy(states[2])), previous=deepcopy(states[1]),
        previous2=deepcopy(states[0]), end_time=2., step=1.,
        endpoint_side=side, coefficients=[1.5, -2., .5])
    snapshots = [dict(time=s['time'], restart=dict(state=deepcopy(s))) for s in states]
    snapshots[-1].update(order=2, step=1., forcing_side=side)
    snapshots[-1]['restart'].update(accepted_method=accepted, forcing_side=side,
                                    older=None if final else deepcopy(states[1]))
    return dict(snapshots=snapshots, forcing=dict(end_time=2. if final else 3.,
                                                  breaks=[2. if final else 3.]))


@pytest.mark.parametrize('final', [False, True])
def test_matching_history_policy(final):
    result = MODULE.validate_checkpoint(fixture(final), final=final, expected_end=2.)
    assert result['terminal_cutoff'] is final
    assert result['accepted_history_verified']


@pytest.mark.parametrize('fault', ['missing_previous', 'wrong_previous2', 'wrong_coefficients',
                                  'wrong_side', 'not_cutoff', 'unexpected_older'])
def test_rejects_invalid_terminal_record(fault):
    raw = fixture()
    sample = raw['snapshots'][-1]
    saved = sample['restart']
    accepted = saved['accepted_method']
    if fault == 'missing_previous': accepted['previous'] = None
    elif fault == 'wrong_previous2': accepted['previous2']['value'][0] += 1
    elif fault == 'wrong_coefficients': accepted['coefficients'][0] = 1.
    elif fault == 'wrong_side': sample['forcing_side'] = 'right'
    elif fault == 'not_cutoff': raw['forcing']['end_time'] = 3.
    else: saved['older'] = deepcopy(accepted['previous'])
    with pytest.raises(AssertionError):
        MODULE.validate_checkpoint(raw, final=True, expected_end=2.)


def test_interior_endpoint_must_retain_continuation_history():
    raw = fixture(False)
    raw['snapshots'][-1]['restart']['older'] = None
    with pytest.raises(AssertionError):
        MODULE.validate_checkpoint(raw, final=False, expected_end=2.)


def test_nonuniform_last_step_keeps_its_accepted_coefficients():
    raw = fixture()
    sample = raw['snapshots'][-1]
    saved = sample['restart']
    accepted = saved['accepted_method']
    sample.update(time=2.5, step=1.5)
    saved['state']['time'] = 2.5
    accepted['endpoint']['state']['time'] = 2.5
    accepted.update(end_time=2.5, step=1.5, coefficients=[16/15, -5/3, 3/5])
    raw['forcing'].update(end_time=2.5, breaks=[2.5])
    assert MODULE.validate_checkpoint(raw, final=True, expected_end=2.5)['accepted_history_verified']
