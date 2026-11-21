"""Mechanics summary accounting/provenance; fixtures are not fresh solves."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import isae_suite_st2_mechanics as mechanics
from isae_acceptance import apply_reference_acceptance

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

runner=load('st2_summary_runner','scripts/run-isae-suite.py')
summary=load('st2_mechanics_summary','scripts/summarize-isae-suite.py')
fixtures=load('st2_summary_fixtures','tests/test_isae_st2_mechanics.py')
read=lambda p:json.loads(p.read_text())


@pytest.fixture(scope='module')
def jobs():return mechanics.plan(ROOT)


@pytest.fixture(scope='module')
def prepared(jobs):
    prior=read(ROOT/'artifacts/isae/st2-mechanics-runner-20261109/full-plan/plan.json')
    p=deepcopy(prior);p['jobs']=jobs;p['code_sha256']=runner.code_pins(ROOT,['st2'])
    return p,runner.report(p,{},ROOT,0.)


def write_run(folder,plan,report):
    for name,data in [('plan',plan),('report',report),('catalog',plan['catalog'])]:
        (folder/(name+'.json')).write_text(json.dumps(data))


def test_declared_scope_and_pending_targets(jobs,prepared):
    scope=summary.declared_scope(jobs)
    assert scope['original_reference_samples']==91 and scope['unique_model_count']==4
    assert scope['mechanics_static_targets']==77 and scope['mechanics_modal_targets']==14
    assert scope['mechanics_jobs']==43 and 'native_scalar_slots' not in scope
    p,r=prepared;merged=summary.merge_runs([dict(catalog=p['catalog'],report=r)])
    data=summary.summarize(merged);st2=next(c for c in data['families'] if c['id']=='ST-2')
    assert st2['status']=='INCOMPLETE_RUN' and st2['scalar_counts']['unrun_required']==91
    assert st2['scalar_counts']['passed']==0 and data['full_suite_validated'] is False
    text=summary.markdown(data)
    assert '77 static ordinates and 14 modal frequencies in 43 jobs' in text
    assert 'Static, workbook and inventory routes remain blocked' not in text


def test_all_reviewed_result_fixtures_keep_strict_and_five_percent_distinct(jobs):
    rows=[]
    for job in jobs:
        strict=runner.checked_result(job,fixtures.fixture_result(job))
        rows.append(dict(job,result=apply_reference_acceptance(strict)))
    counts=summary.totals(rows)
    assert counts['required']==counts['passed']==91
    assert summary.totals([summary.strict_policy_job(j) for j in rows])['passed']<91


@pytest.mark.parametrize('status',['error','timeout','adapter_contract_failure'])
def test_failed_job_stays_in_denominator(jobs,status):
    job=jobs[-1]
    raw=runner.checked_result(job,dict(status=status,reference_match=False))
    row=dict(job,result=apply_reference_acceptance(raw))
    counts=summary.scalar_counts(row)
    assert counts['required']==counts['failed_job_required']==7 and counts['passed']==0
    assert counts['unrun_required']==0


def test_loader_authenticates_current_complete_unrun_scope(prepared,tmp_path):
    p,r=prepared;write_run(tmp_path,p,r)
    imported=summary.load_runs([tmp_path])
    assert len(imported['jobs'])==43 and summary.totals(imported['jobs'])['required']==91
    summary.verify_summary_sources(imported)


@pytest.mark.parametrize('fault',['no_opt_in','missing_helper','source_bytes'])
def test_loader_rejects_incomplete_provenance(prepared,tmp_path,fault):
    p,r=deepcopy(prepared)
    if fault=='no_opt_in':
        p['execution_policy']['comparison_scopes']=[];r['execution_policy']=deepcopy(p['execution_policy'])
        match='explicit opt-in'
    elif fault=='missing_helper':
        p['code_sha256'].pop('scripts/verify_st2_modal_current.py');r['code_sha256']=deepcopy(p['code_sha256'])
        match='complete helper pins'
    else:
        p['jobs'][0]['source_pins'][0]['bytes']+=1
        r['jobs'][0]['source_pins']=deepcopy(p['jobs'][0]['source_pins'])
        match='source|Source'
    write_run(tmp_path,p,r)
    with pytest.raises(ValueError,match=match):summary.load_runs([tmp_path])


def test_overlapping_archive_cannot_be_added_to_mechanics(prepared):
    p,r=prepared;other=deepcopy(r)
    other['jobs']=[dict(id='legacy',case_id='ST-2',adapter='st2')]
    with pytest.raises(ValueError,match='overlapping archive'):
        summary.merge_runs([dict(report=r,catalog=p['catalog']),dict(report=other,catalog=p['catalog'])])


@pytest.fixture
def saved_static_artifacts(tmp_path,jobs):
    original=ROOT/'artifacts/isae/st2-mechanics-runner-20261109/static-smoke'
    path=next((original/'jobs').glob('*/result.json'));result=read(path)
    stage=next(Path(result['artifact_root']).glob('st2-mechanics-*'))
    copy=tmp_path/'stage';shutil.copytree(stage,copy);result['artifact_root']=str(copy)
    job=next(j for j in jobs if j['id']==result['job_id'])
    return job,result,copy


def test_authenticate_saved_artifacts_without_solver_import(saved_static_artifacts):
    job,result,_=saved_static_artifacts
    before={k for k in sys.modules if k.startswith('openswing')}
    pins=mechanics.verify_artifacts(ROOT,job,result)
    assert len(pins)==14 and all(p['bytes']>0 for p in pins)
    assert {k for k in sys.modules if k.startswith('openswing')}==before


@pytest.mark.parametrize('fault',['result_bytes','report_bytes','missing_request','missing_artifact_entry'])
def test_changed_or_missing_artifacts_rejected(saved_static_artifacts,fault):
    job,result,stage=saved_static_artifacts
    if fault=='result_bytes':(stage/'job-00/result.json').write_text('{}')
    elif fault=='report_bytes':(stage/'job-00/report.json').write_text('{}')
    elif fault=='missing_request':(stage/'job-00/request.json').unlink()
    else:result['states'][0]['artifacts'].pop('result.json')
    with pytest.raises((ValueError,FileNotFoundError)):
        mechanics.verify_artifacts(ROOT,job,result)
