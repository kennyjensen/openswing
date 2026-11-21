"""A displayed initial order of zero must not conceal lost BDF history."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from isae_ua1_periodic_boundary import check_boundary


def fixture():
    older = dict(time=.25, network=dict(circulation=[1.25], internal_moment=[[20.]]))
    state = dict(time=.5, network=dict(circulation=[1.5], internal_moment=[[25.]]))
    endpoint = dict(time=.75, network=dict(circulation=[1.75], internal_moment=[[30.]]))
    accepted = dict(kind='bdf', scheme='drela-euler-bdf-v1', effective_order=2, end_time=.75,
                    step=.25, coefficients=[6., -8., 2.], endpoint=dict(state=endpoint), previous=state, previous2=older)
    saved = dict(state=state, older=older)
    samples = [dict(time=.5, order=0, restart=dict(state=state, older=older, accepted_method=dict(effective_order=2))),
               dict(time=.75, order=2, step=.25, restart=dict(state=endpoint, accepted_method=accepted))]
    return deepcopy(saved), deepcopy(samples)


def test_presentation_order_zero_preserves_complete_second_order_history():
    saved, samples = fixture()
    assert check_boundary(saved, samples) == []


@pytest.mark.parametrize('fault', ['euler_restart', 'missing_older', 'changed_previous2', 'wrong_coefficients'])
def test_rejects_damaged_history_despite_valid_presentation_record(fault):
    saved, samples = fixture()
    accepted = samples[1]['restart']['accepted_method']
    if fault == 'euler_restart':
        samples[1]['order'] = accepted['effective_order'] = 1
    elif fault == 'missing_older':
        samples[0]['restart']['older'] = None
    elif fault == 'changed_previous2':
        accepted['previous2']['network']['circulation'][0] += .01
    else:
        accepted['coefficients'][0] += .01
    with pytest.raises(AssertionError):
        check_boundary(saved, samples)
