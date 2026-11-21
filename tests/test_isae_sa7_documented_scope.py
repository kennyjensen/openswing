"""The selected SA7 comparison must use the documented aircraft exactly once."""
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
from scripts import isae_suite_extra_polars as extra


@pytest.fixture(scope='module')
def runner():
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(ROOT/'scripts'))
        spec=importlib.util.spec_from_file_location('sa7_scope_runner',ROOT/'scripts/run-isae-suite.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        yield module


@pytest.fixture(scope='module')
def plans(runner):
    if not (ROOT/extra.SOURCE_PAIRING_AUDIT).is_file():
        pytest.skip('Authenticated ISAE source cache unavailable')
    original=runner.plan_jobs(ROOT,['polars','extra_polars'])
    paired=runner.plan_jobs(ROOT,['polars','extra_polars'],source_pairings=[extra.SOURCE_PAIRING_ID])
    documented=runner.plan_jobs(ROOT,['polars','extra_polars'],comparison_scopes=[extra.DOCUMENTED_SA7_SCOPE])
    return original,paired,documented


def cells(jobs):
    return {(j['table_path'],j['row_index'],j['settings']['panels'],name):field
            for j in jobs if j['case_id']=='SA-7'
            for name,field in j['reference_row']['fields'].items() if name in extra.polar.OUTPUTS}


def test_documented_scope_preserves_every_original_target_without_double_counting(plans):
    original,paired,documented=plans
    assert len(documented)==len(original)
    assert cells(original)==cells(documented)
    family=[j for j in documented if j['case_id']=='SA-7']
    assert len(family)==116 and sum(j['expected_outputs'] for j in family)==812
    assert sum('source_pairing' in j for j in family)==58
    assert sum(j['reference_row']['fields']['CD']['value']<0 for j in family)==42
    assert extra.select_documented_sa7(paired)==documented
    assert [j for j in original if j['case_id']!='SA-7']==[j for j in documented if j['case_id']!='SA-7']


def test_pairing_option_and_documented_scope_do_not_add_duplicate_targets(runner,plans):
    both=runner.plan_jobs(ROOT,['polars','extra_polars'],source_pairings=[extra.SOURCE_PAIRING_ID],
        comparison_scopes=[extra.DOCUMENTED_SA7_SCOPE])
    assert both==plans[2]


@pytest.mark.parametrize('adapters',[['polars'],['extra_polars']])
def test_incomplete_adapter_selection_is_rejected_before_planning(runner,adapters):
    with pytest.raises(ValueError,match='adapter'):
        runner.plan_jobs(ROOT,adapters,comparison_scopes=[extra.DOCUMENTED_SA7_SCOPE])


@pytest.mark.parametrize('fault',['missing_original','changed_sign','changed_mesh','missing_full'])
def test_documented_selection_rejects_partial_or_changed_comparisons(plans,fault):
    jobs=deepcopy(plans[1])
    paired=next(j for j in jobs if j.get('source_pairing',{}).get('id')==extra.SOURCE_PAIRING_ID)
    original=next(j for j in jobs if j['id']==paired['source_pairing']['original_job_id'])
    if fault=='missing_original':jobs.remove(original)
    elif fault=='changed_sign':paired['reference_row']['fields']['CD']['value'] *= -1
    elif fault=='changed_mesh':paired['settings']['panels'] += 1
    elif fault=='missing_full':jobs.remove(next(j for j in jobs if j['case_id']=='SA-7' and 'Fore' not in j['model_path']))
    with pytest.raises(ValueError,match='SA-7'):
        extra.select_documented_sa7(jobs)


def test_selected_fore_job_retains_authenticated_execution_contract(plans):
    job=next(j for j in plans[2] if j.get('source_pairing',{}).get('id')==extra.SOURCE_PAIRING_ID)
    assert extra.validate_source_pairing(ROOT,job)
    assert job['source_pairing']['producer_execution_authenticated'] is False
    assert job['settings']['freeze_influences'] is False
