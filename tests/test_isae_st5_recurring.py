"""ST-5 recurring scope, complete physical evidence and acceptance invariants."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import isae_suite_st5_mechanics as adapter
from isae_acceptance import apply_reference_acceptance


def load(name, file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


runner=load('st5_runner','run-isae-suite.py')
summary=load('st5_summary','summarize-isae-suite.py')


@pytest.fixture(scope='module')
def jobs():return adapter.plan(ROOT,comparison_scopes=[adapter.SCOPE])


def result_for(job):
    original=ROOT/job['reference_input']['reference_plan']
    extension=ROOT/'artifacts/isae/st5-convergence-current-20261109'/job['configuration']
    states=[adapter.state_view(adapter.read((original.parent if i<2 else extension)/f'run-{i}/level{i}/comparison.json')) for i in range(5)]
    return adapter.build_result(job,states)


def test_all_distinct_cases_and_denominators(jobs):
    assert adapter.plan(ROOT)==[]
    assert len(jobs)==16 and sum(j['expected_outputs'] for j in jobs)==16688
    assert summary.declared_scope(jobs)['st5_structural_targets']==16688
    assert summary.totals(jobs)['unrun_required']==16688
    assert runner.plan_jobs(ROOT,['st5'],comparison_scopes=['st5-mechanics'])==jobs
    with pytest.raises(ValueError):adapter.plan(ROOT,comparison_scopes=['st5-mechanics']*2)


def test_complete_reviewed_results_retain_the_native_miss(jobs):
    records=[]
    for job in jobs:
        raw=result_for(job)
        assert adapter.validate_result_contract(job,raw)
        strict=runner.checked_result(job,raw)
        assert strict['status']=='computed',strict.get('contract_error')
        records.append(dict(job,result=apply_reference_acceptance(strict)))
    counts=summary.totals(records)
    assert counts['passed']==16687 and counts['required']==16688
    failed=[c for j in records for c in j['result']['reference_checks'] if not c['passed']]
    assert len(failed)==1 and failed[0]['quantity']=='Fn' and failed[0]['source_line']==67


@pytest.mark.parametrize('fault',['missing_grid','missing_row','missing_field','target','prediction','mesh','deformation','physical','provenance'])
def test_rejects_incomplete_or_detached_evidence(jobs,fault):
    job=jobs[0];r=result_for(job)
    if fault=='missing_grid':r['states'].pop(2)
    elif fault=='missing_row':r['states'][4]['rows'].pop()
    elif fault=='missing_field':r['mesh_checks'].pop()
    elif fault=='target':r['reference_checks'][0]['expected']+=1
    elif fault=='prediction':r['reference_checks'][0]['predicted']+=1
    elif fault=='mesh':r['mesh_checks'][0]['relative_change']=0.
    elif fault=='deformation':r['states'][3]['rows'][0]['structural_deformation'][0]+=1
    elif fault=='physical':r['states'][2]['checks']['fresh_residual']=1.
    else:r['source_pins_unchanged']=False
    with pytest.raises(ValueError):adapter.validate_result_contract(job,r)
    rejected=runner.checked_result(job,r)
    assert rejected['status']=='adapter_contract_failure'
    accepted=apply_reference_acceptance(rejected)
    assert accepted['output_accounting']['passed']==0
    assert summary.totals([dict(job,result=accepted)])['required']==job['expected_outputs']


def test_legacy_scopes_cannot_be_pooled(jobs):
    with pytest.raises(ValueError,match='overlapping'):
        summary.merge_runs([dict(report=dict(jobs=jobs)),dict(report=dict(jobs=[dict(case_id='ST-5',adapter='structure')]))])


def test_additive_rule_is_explicit_and_does_not_change_other_checks():
    raw=dict(status='computed',numerical_pass=True,reference_checks=[dict(name='x',predicted=1.055,expected=1.,tolerance=.01,passed=False)],
        output_accounting=dict(required=1,reported=1,finite=1,missing=0,passed=0))
    assert not apply_reference_acceptance(raw)['reference_checks'][0]['passed']
    raw['reference_checks'][0]['relative_allowance_rule']=adapter.RULE
    view=apply_reference_acceptance(raw)
    assert view['reference_checks'][0]['passed'] and view['reference_checks'][0]['effective_tolerance']==.06
    assert not apply_reference_acceptance(raw,relative_tolerance=0)['reference_checks'][0]['passed']
    raw['numerical_pass']=False
    assert not apply_reference_acceptance(raw)['reference_checks'][0]['passed']


def test_additive_rule_cannot_be_injected_into_another_scope():
    job=dict(adapter='polars',case_id='SA-1',expected_outputs=1)
    raw=dict(status='computed',numerical_pass=True,reference_checks=[dict(name='x',predicted=1.055,expected=1.,tolerance=.01,passed=False,relative_allowance_rule=adapter.RULE)])
    assert runner.checked_result(job,raw)['status']=='adapter_contract_failure'
    with pytest.raises(ValueError,match='declared ST5'):
        summary.scalar_counts(dict(job,result=raw))


def test_new_scope_preserves_other_families(jobs,monkeypatch):
    import isae_suite_structure
    monkeypatch.setattr(isae_suite_structure,'plan',lambda root:[dict(id='old',case_id='ST-5'),dict(id='keep',case_id='ST-3')])
    planned=runner.plan_jobs(ROOT,['structure','st5'],comparison_scopes=['st5-mechanics'])
    assert len(planned)==17 and planned[0]['id']=='keep'
