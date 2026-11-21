"""Saved-history audits must verify the actual BDF clock and derivative stencil."""
import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ffwt4_history_v3', ROOT/'scripts/assess-isae-ffwt4-history-v3.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def snapshot(tick, divisor=8):
    h = .0149/divisor
    order = 1 if tick == 1 else 2
    coefficients = [1/h,-1/h,0.] if order == 1 else [1.5/h,-2/h,.5/h]
    return dict(time=tick*h,converged=True,residual=1e-12,
        restart=dict(accepted_method=dict(effective_order=order,coefficients=coefficients,scheme='drela-euler-bdf-v1')),
        sensors=[dict(index=1,load_trace='left',moment_local=[.75,0.,0.])])


@pytest.mark.parametrize('divisor',[8,16])
def test_full_clock_and_bdf_stencil_are_consistent(divisor):
    h = .0149/divisor
    for tick in (1,2,199*divisor):
        state = snapshot(tick,divisor)
        assert audit.snapshot_value(state,tick,divisor) == .75
        times = [(tick-j)*h for j in range(len(state['restart']['accepted_method']['coefficients']))]
        if tick == 1:
            derivative = sum(c*t for c,t in zip(state['restart']['accepted_method']['coefficients'],times))
            assert derivative == pytest.approx(1.,abs=1e-12)
        else:
            derivative = sum(c*t*t for c,t in zip(state['restart']['accepted_method']['coefficients'],times))
            assert derivative == pytest.approx(2*tick*h,abs=1e-10)


@pytest.mark.parametrize('fault',['wrong_order','wrong_coefficients','wrong_scheme','shifted_time','residual','trace','nonfinite'])
def test_invalid_history_state_cannot_be_counted(fault):
    state = snapshot(12)
    if fault == 'wrong_order': state['restart']['accepted_method']['effective_order'] = 1
    elif fault == 'wrong_coefficients': state['restart']['accepted_method']['coefficients'][0] *= 1.001
    elif fault == 'wrong_scheme': state['restart']['accepted_method']['scheme'] = 'other'
    elif fault == 'shifted_time': state['time'] += 1e-8
    elif fault == 'residual': state['residual'] = 1.01e-8
    elif fault == 'trace': state['sensors'][0]['load_trace'] = 'right'
    else: state['sensors'][0]['moment_local'][0] = float('nan')
    with pytest.raises(ValueError): audit.snapshot_value(state,12,8)


def test_first_step_cannot_claim_second_order_or_reuse_a_later_stencil():
    state = snapshot(1)
    changed = copy.deepcopy(state)
    changed['restart']['accepted_method'] = snapshot(2)['restart']['accepted_method']
    with pytest.raises(ValueError): audit.snapshot_value(changed,1,8)
    assert audit.snapshot_value(state,1,8) == .75


def test_first_order_padding_must_be_zero_in_the_three_entry_saved_format():
    state = snapshot(1)
    state['restart']['accepted_method']['coefficients'][2] = 1e-6
    with pytest.raises(ValueError): audit.snapshot_value(state,1,8)
