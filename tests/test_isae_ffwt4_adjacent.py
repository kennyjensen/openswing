"""The adjacent-grid audit must retain interleaved extrema and full time coverage."""
import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ffwt4_adjacent',ROOT/'scripts/assess-isae-ffwt4-adjacent.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


def histories():
    fine={i:100+i/796 for i in range(797)}
    return {i:fine[2*i] for i in range(399)},fine


def test_every_shared_tick_and_native_subset_pass_for_equal_values():
    coarse,fine=histories()
    all_ticks=audit.compare(coarse,fine,2,4)
    native=audit.compare(coarse,fine,2,4,native_ticks=True)
    assert all_ticks['common_samples']==399 and native['common_samples']==200
    assert all_ticks['passed']==native['passed']==2


def test_between_archive_ticks_error_is_not_hidden():
    coarse,fine=histories();coarse[171]+=.01
    assert audit.compare(coarse,fine,2,4,native_ticks=True)['passed']==2
    result=audit.compare(coarse,fine,2,4)
    assert result['gates']['root_moment']['passed']
    assert not result['gates']['gust_increment']['passed']
    assert result['gates']['gust_increment']['worst_coarser_tick']==171
    assert result['gates']['gust_increment']['worst_time']==pytest.approx(171*.00745)


@pytest.mark.parametrize('fault',['missing_coarse','missing_fine','nonfinite_interleaved','wrong_ratio'])
def test_incomplete_or_invalid_grids_are_rejected(fault):
    coarse,fine=histories();cd,fd=2,4
    if fault=='missing_coarse':coarse.pop(398)
    elif fault=='missing_fine':fine.pop(123)
    elif fault=='nonfinite_interleaved':fine[123]=float('nan')
    else:fd=2
    with pytest.raises(ValueError):audit.compare(coarse,fine,cd,fd)


def test_saved_assessment_cannot_shift_its_times():
    coarse,_=histories()
    data=dict(status='REFINED_HISTORY_ASSESSED',complete=True,divisor=2,dt='0.00745',
        accepted_steps=398,rejected_steps=0,
        samples={str(k):dict(time=k*.00745,moment=v,residual=1e-10) for k,v in coarse.items()})
    assert audit.verified_samples(data)==coarse
    data['samples']['171']['time']+=.001
    with pytest.raises(ValueError,match='Saved time'):audit.verified_samples(data)
