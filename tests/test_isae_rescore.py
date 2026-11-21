"""Reassessment must preserve unavailable outputs, scopes and original evidence."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import pytest
from test_isae_suite_summary import job, check, policy_job

spec=importlib.util.spec_from_file_location('rescore',Path(__file__).resolve().parents[1]/'scripts/rescore-isae-results.py')
rescore=importlib.util.module_from_spec(spec);spec.loader.exec_module(rescore)


def test_saved_three_percent_view_rescores_at_five_without_mutating_evidence():
    row=policy_job(job('a',[check('lift',1.04,tolerance=1e-6)]))
    old=deepcopy(row)
    data=rescore.score([('job',row)])
    c=data['groups'][0]['counts']
    assert c['required']==c['accepted']==1 and c['passed']==0
    assert row==old and data['physical_calls']==0 and not data['current_source_rerun']


def test_missing_invalid_and_conditional_outputs_stay_separate():
    rows=[job('valid',[check('lift',1.04,tolerance=1e-6)]),
          job('missing',[check('lift',None,tolerance=1e-6)],status='unsupported'),
          job('failed',[check('lift',1.04,tolerance=1e-6)],status='numerical_failure')]
    other=deepcopy(rows[0]);other.update(id='conditional',comparison_scope='alternative')
    groups=rescore.score([('job',r) for r in rows+[other]])['groups']
    assert len(groups)==2
    c=groups[0]['counts'];assert c['accepted']==1 and c['required']==3
    assert c['unsupported_required']==c['failed_job_required']==1
    assert groups[1]['scope']=='alternative' and groups[1]['counts']['accepted']==1


def test_tampered_saved_policy_is_rejected():
    row=policy_job(job('a',[check('lift',1.07,tolerance=1e-6)]))
    row['result']['reference_checks'][0]['passed']=True
    with pytest.raises(ValueError):rescore.score([('job',row)])


def test_streamed_report_matches_json_across_large_string_boundary(tmp_path):
    data={'code_sha256':{'openswing/a.py':'x'},'jobs':[
        job('first',[check('x',1.04,tolerance=1e-6)]),
        dict(job('last',[check('x',1.06,tolerance=1e-6)]),note='escaped\\\n'+'a'*70000)]}
    path=tmp_path/'report.json';path.write_text(json.dumps(data))
    items=list(rescore.report_items(path))
    assert items==[('code_sha256',data['code_sha256'])]+[('job',j) for j in data['jobs']]
    assert rescore.score(items)['groups'][0]['counts']['accepted']==1


def test_selected_original_job_files_keep_missing_jobs_and_pin_read_results(tmp_path):
    import hashlib
    row=job('one',[check('x',1.04,tolerance=1e-6)])
    strict=row.pop('result');strict['id']='one'
    other=dict(row,id='two')
    plan=tmp_path/'plan.json'
    plan.write_text(json.dumps(dict(code_sha256={'openswing/a.py':'original'},jobs=[row,other])))
    folder=tmp_path/'jobs'/hashlib.sha256(b'one').hexdigest()[:20]
    folder.mkdir(parents=True);(folder/'result.json').write_text(json.dumps(strict))
    pins=[]
    data=rescore.score(rescore.directory_items(plan,['SA-1'],pins))
    c=data['groups'][0]['counts']
    assert c['accepted']==1 and c['required']==2 and c['unrun_required']==1
    assert pins==[rescore.pin(folder/'result.json')]
