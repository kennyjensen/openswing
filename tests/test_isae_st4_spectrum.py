import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from isae_st4_spectrum import compare_triplet

TARGETS = [dict(label=label, expected=value, original_absolute_tolerance=.05)
           for label, value in [('fb1', 6.5), ('fb2', 28.), ('ft', 38.)]]
IDENTITY = [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]


def test_complete_spectrum_keeps_original_labels_without_claiming_identity():
    rows = compare_triplet(TARGETS[::-1], [6.5, 28., 38.], [6.5, 28., 38.], IDENTITY)
    assert len(rows) == 3 and all(r['passed'] for r in rows)
    assert [r['original_label'] for r in rows] == ['fb1', 'fb2', 'ft']
    assert not any(r['native_mode_identity_validated'] for r in rows)


@pytest.mark.parametrize('values', [[6.5, 28.], [6.5, 28., 28.],
                                  [6.5, 28., None], [6.5, 28., float('nan')],
                                  [6.5, 28., 0.], [28., 6.5, 38.]])
def test_missing_duplicate_invalid_or_reordered_prediction_rejected(values):
    with pytest.raises(ValueError):
        compare_triplet(TARGETS, values, [6.5, 28., 38.], IDENTITY)


def test_missing_reference_cannot_reduce_denominator():
    targets = copy.deepcopy(TARGETS)
    targets[1]['expected'] = None
    with pytest.raises(ValueError):
        compare_triplet(targets, [6.5, 28., 38.], [6.5, 28., 38.], IDENTITY)


def test_fine_grid_match_cannot_hide_bad_coarse_grid():
    rows = compare_triplet(TARGETS, [6.5, 28., 41.], [6.5, 28., 38.], IDENTITY)
    assert not rows[2]['frequency_pass'] and not rows[2]['passed']


def test_matching_frequencies_require_same_shapes_on_both_grids():
    swapped = [[1., 0., 0.], [0., 0., 1.], [0., 1., 0.]]
    rows = compare_triplet(TARGETS, [6.5, 28., 38.], [6.5, 28., 38.], swapped)
    assert rows[0]['passed'] and not rows[1]['passed'] and not rows[2]['passed']


def test_every_target_used_once_without_best_match_assignment():
    targets = copy.deepcopy(TARGETS)
    targets[1]['expected'], targets[2]['expected'] = 31., 33.
    rows = compare_triplet(targets, [6.5, 31., 38.], [6.5, 31., 38.], IDENTITY)
    assert [r['expected_Hz'] for r in rows] == [6.5, 31., 33.]
    assert sum(r['passed'] for r in rows) == 2


def test_no_cross_rank_rescue_when_upper_prediction_matches_middle_target():
    targets = [dict(label=label, expected=value, original_absolute_tolerance=.001)
               for label, value in [('fb1', 1.), ('fb2', 4.), ('ft', 5.)]]
    rows = compare_triplet(targets, [1., 3.2, 4.], [1., 3.2, 4.], IDENTITY)
    assert [r['passed'] for r in rows] == [True, False, False]
