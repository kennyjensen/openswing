"""Additional time samples must not relax the original native-time gates."""
import copy
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
spec = importlib.util.spec_from_file_location('ffwt4_field_native', ROOT/'scripts/assess-isae-ffwt4-field-refinement-v2.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def series(divisor):
    frames = []
    for tick in range(199*divisor+1):
        time = float(tick*audit.DT/divisor)
        frames.append(dict(tick=tick, time=time, moment=.7+.4*time/2.9651,
                           displacement=[[0., 0., .003], [0., 0., 0.], [0., 0., .003]],
                           rotation_vector=[[-.01, 0., 0.], [0., 0., 0.], [.01, 0., 0.]]))
    return frames


def test_peak_between_native_times_cannot_hide_original_gate_failure():
    coarse, fine = series(2), series(4)
    # A perfectly matched off-output-time peak changes the dense-grid scale.
    coarse[3]['moment'] = fine[6]['moment'] = 100.
    coarse[2]['moment'] += .002
    shared = audit.base.compare_frames(coarse, fine, kind='temporal', nominals=[32, 32],
        divisors=[2, 4], coarse_stations=[-.5, 0., .5], fine_stations=[-.5, 0., .5])
    assert shared['passed'] == 4
    native = audit.compare_native(audit.native_moments(coarse, 2), audit.native_moments(fine, 4))
    assert native['passed'] == 0
    assert native['gates']['root_moment']['fine_scale'] == pytest.approx(1.1)
    assert native['gates']['gust_increment']['fine_scale'] == pytest.approx(.4)
    assert native['gates']['gust_increment']['worst_native_row'] == 2
    combined = audit.combine(shared, native)
    assert combined['passed'] == 2 and combined['required'] == 4
    assert not combined['gates']['root_moment'] and not combined['gates']['gust_increment']


def test_native_matches_do_not_hide_an_error_between_output_times():
    coarse, fine = series(2), series(4)
    coarse[3]['moment'] += .002
    shared = audit.base.compare_frames(coarse, fine, kind='temporal', nominals=[32, 32],
        divisors=[2, 4], coarse_stations=[-.5, 0., .5], fine_stations=[-.5, 0., .5])
    native = audit.compare_native(audit.native_moments(coarse, 2), audit.native_moments(fine, 4))
    assert native['passed'] == 2 and shared['passed'] == 2
    assert audit.combine(shared, native)['passed'] == 2


@pytest.mark.parametrize('divisor', [2, 4, 8, 16])
def test_exact_time_selection_and_identical_histories_pass(divisor):
    values = audit.native_moments(series(divisor), divisor)
    assert len(values) == 200 and values[-1] == pytest.approx(1.1)
    assert values[67] == pytest.approx(.7+.4*67/199)
    result = audit.compare_native(values, values)
    assert result['passed'] == result['required'] == 2


@pytest.mark.parametrize('fault', ['missing_tail', 'repeated_tick', 'shifted_time', 'nonfinite_off_native'])
def test_invalid_original_time_extraction_is_rejected(fault):
    frames = series(4)
    if fault == 'missing_tail':
        frames.pop()
    elif fault == 'repeated_tick':
        frames[1]['tick'] = 0
    elif fault == 'shifted_time':
        frames[1]['time'] += .0001
    else:
        frames[1]['moment'] = float('nan')
    with pytest.raises(ValueError):
        audit.native_moments(frames, 4)


def test_increment_gate_keeps_its_own_transient_scale():
    fine = [1000.+.4*i/199 for i in range(200)]
    coarse = fine.copy(); coarse[20] += .0005
    gates = audit.compare_native(coarse, fine)['gates']
    assert gates['root_moment']['passed'] and not gates['gust_increment']['passed']
    assert gates['gust_increment']['maximum_percent_of_scale'] == pytest.approx(.125)


@pytest.mark.parametrize('fault', ['missing_moment', 'zero_increment', 'nan'])
def test_native_gate_cannot_pass_invalid_series(fault):
    fine = [.7+.4*i/199 for i in range(200)]
    coarse = fine.copy()
    if fault == 'missing_moment':
        coarse.pop()
    elif fault == 'zero_increment':
        fine = [.7]*200
    else:
        fine[20] = float('nan')
    with pytest.raises(ValueError):
        audit.compare_native(coarse, fine)


def test_combination_rejects_changed_tolerance_or_removed_quantity():
    shared = dict(gates={name: dict(passed=True, relative_limit=.001)
                        for name in ('root_moment', 'gust_increment', 'displacement', 'rotation_vector')})
    native = dict(gates={name: dict(passed=True, relative_limit=.001) for name in ('root_moment', 'gust_increment')})
    assert audit.combine(shared, native)['passed'] == 4
    changed = copy.deepcopy(native)
    changed['gates']['root_moment']['relative_limit'] = .05
    with pytest.raises(ValueError):
        audit.combine(shared, changed)
    del shared['gates']['displacement']
    with pytest.raises(ValueError):
        audit.combine(shared, native)
