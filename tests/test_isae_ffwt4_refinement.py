"""Time refinement must not hide dynamic error behind a static baseline or missing rows."""
import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ffwt4_refinement',ROOT/'scripts/assess-isae-ffwt4-refinement.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


def histories():
    # All 200 common samples are exact, with additional interleaved fine states.
    fine={i:100.+i/398 for i in range(399)}
    return {i:fine[2*i] for i in range(200)},fine


def test_complete_identical_common_ticks_pass_both_gates():
    coarse,fine=histories();gates=audit.refinement_checks(coarse,fine,2)
    assert all(g['passed'] for g in gates.values())
    assert gates['gust_increment']['scale']==1
    assert gates['root_moment']['maximum_absolute_difference']==0


def test_small_dynamic_error_cannot_hide_in_large_static_moment():
    coarse,fine=histories();coarse[100]+=.01
    gates=audit.refinement_checks(coarse,fine,2)
    assert gates['root_moment']['passed']
    assert not gates['gust_increment']['passed']
    assert gates['gust_increment']['worst_row']==101
    assert gates['gust_increment']['maximum_percent_of_scale']==pytest.approx(1.)


@pytest.mark.parametrize('which',['coarse','fine','interleaved'])
def test_missing_history_cannot_claim_convergence(which):
    coarse,fine=histories()
    if which=='coarse':coarse.pop(199)
    elif which=='fine':fine.pop(398)
    else:fine.pop(101)
    with pytest.raises(ValueError,match='incomplete'):audit.refinement_checks(coarse,fine,2)


def test_nonfinite_interleaved_state_rejected_by_snapshot_audit():
    snapshot=dict(time=.00745*21,converged=True,residual=1e-10,
        restart=dict(accepted_method=dict(effective_order=2)),
        sensors=[dict(index=1,load_trace='left',moment_local=[float('nan'),0,0])])
    with pytest.raises(ValueError,match='Nonfinite'):audit.snapshot_value(snapshot,21,2)
    snapshot['sensors'][0]['moment_local'][0]=1.
    assert audit.snapshot_value(snapshot,21,2)==1.
    snapshot['restart']['accepted_method']['effective_order']=1
    with pytest.raises(ValueError,match='order'):audit.snapshot_value(snapshot,21,2)


def test_no_interpolation_to_hide_the_wrong_grid():
    snapshot=dict(time=.0149*21,converged=True,residual=1e-10,
        restart=dict(accepted_method=dict(effective_order=2)),
        sensors=[dict(index=1,load_trace='left',moment_local=[1.,0,0])])
    with pytest.raises(ValueError,match='time differs'):audit.snapshot_value(snapshot,21,2)
