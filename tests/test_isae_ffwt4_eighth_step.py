"""Eighth-step coverage must retain every time node and the strict dynamic gate."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


refinement = load('ffwt4_refinement_v2', 'assess-isae-ffwt4-refinement-v2.py')
adjacent = load('ffwt4_adjacent_v2', 'assess-isae-ffwt4-adjacent-v2.py')


def histories():
    fine = {i: 100.+i/1592 for i in range(1593)}
    return {i: fine[2*i] for i in range(797)}, fine


def test_eighth_grid_uses_all_shared_ticks_and_keeps_original_native_gate():
    coarse, fine = histories()
    assert adjacent.compare(coarse, fine, 4, 8)['common_samples'] == 797
    assert adjacent.compare(coarse, fine, 4, 8)['passed'] == 2
    assert adjacent.compare(coarse, fine, 4, 8, native_ticks=True)['common_samples'] == 200
    native = {i: fine[8*i] for i in range(200)}
    assert all(v['passed'] for v in refinement.refinement_checks(native, fine, 8).values())


def test_error_between_native_ticks_cannot_hide_behind_the_static_baseline():
    coarse, fine = histories()
    coarse[173] += .01
    assert adjacent.compare(coarse, fine, 4, 8, native_ticks=True)['passed'] == 2
    result = adjacent.compare(coarse, fine, 4, 8)
    assert result['gates']['root_moment']['passed']
    assert not result['gates']['gust_increment']['passed']
    assert result['gates']['gust_increment']['relative_limit'] == .001
    assert result['gates']['gust_increment']['worst_time'] == pytest.approx(173*.003725)


@pytest.mark.parametrize('fault', ['missing_coarse', 'missing_odd_fine', 'nonfinite_odd_fine', 'skipped_grid'])
def test_incomplete_or_invalid_eighth_grid_is_rejected(fault):
    coarse, fine = histories()
    divisor = 4
    if fault == 'missing_coarse':
        coarse.pop(796)
    if fault == 'missing_odd_fine':
        fine.pop(153)
    if fault == 'nonfinite_odd_fine':
        fine[153] = float('nan')
    if fault == 'skipped_grid':
        divisor = 2
    with pytest.raises(ValueError):
        adjacent.compare(coarse, fine, divisor, 8)


def test_saved_eighth_state_requires_the_exact_clock_and_startup_order():
    snapshot = dict(time=.0018625, converged=True, residual=1e-10,
        restart=dict(accepted_method=dict(effective_order=1)),
        sensors=[dict(index=1, load_trace='left', moment_local=[1., 0., 0.])])
    assert refinement.snapshot_value(snapshot, 1, 8) == 1.
    snapshot['restart']['accepted_method']['effective_order'] = 2
    with pytest.raises(ValueError, match='order'):
        refinement.snapshot_value(snapshot, 1, 8)
    snapshot['time'] *= 2
    assert refinement.snapshot_value(snapshot, 2, 8) == 1.
    snapshot['residual'] = 1.01e-8
    with pytest.raises(ValueError, match='Unconverged'):
        refinement.snapshot_value(snapshot, 2, 8)
