"""Retry only timed-out structural jobs with a longer serial execution cap.

The numerical request, mesh, physics and strict reference gates are unchanged.
Every original attempt remains in place; completed cases are never rerun.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/st1-st6-current-20261103'
spec=importlib.util.spec_from_file_location('suite',ROOT/'scripts/run-isae-suite.py')
suite=importlib.util.module_from_spec(spec);spec.loader.exec_module(suite)
read=lambda p:json.loads(Path(p).read_text())


def prepare(adapter):
    original=BASE/adapter;source=read(original/'plan.json')
    assert suite.stable_code(ROOT,source['code_sha256'])
    paths={};retry=[]
    for job in source['jobs']:
        key=hashlib.sha256(job['id'].encode()).hexdigest()[:20]
        path=original/'jobs'/key/'result.json';result=read(path)
        assert result['execution_completed'] and result['job_id']==job['id']
        paths[job['id']]=str(path.relative_to(ROOT))
        if result['status']=='timeout':retry.append(job['id'])
    assert retry
    folder=original/'recovery180';folder.mkdir()
    pins=dict(source['code_sha256'])
    pins[str(Path(__file__).resolve().relative_to(ROOT))]=suite.digest(Path(__file__))
    plan=dict(source,code_sha256=pins,timeout_seconds=180,retry_ids=retry,original_result_paths=paths,
        input_sha256={str((original/'plan.json').relative_to(ROOT)):suite.digest(original/'plan.json'),
            **{p:suite.digest(ROOT/p) for p in paths.values()}},
        justification='Observed 45-second timeouts; longer single-case cap, same one thread and numerical problem.')
    suite.write_json(folder/'plan.json',plan)
    print(json.dumps(dict(adapter=adapter,retries=len(retry),timeout_seconds=180)),flush=True)


def run(adapter,maximum):
    folder=BASE/adapter/'recovery180';plan=read(folder/'plan.json');results={};paths={}
    assert suite.stable_code(ROOT,plan['code_sha256'])
    for p,digest in plan['input_sha256'].items():assert suite.digest(ROOT/p)==digest
    for job in plan['jobs']:
        key=hashlib.sha256(job['id'].encode()).hexdigest()[:20]
        path=folder/'jobs'/key/'result.json'
        if path.exists():
            assert read(path.with_name('request.json'))==dict(job=job,code_sha256=plan['code_sha256'])
        elif job['id'] not in plan['retry_ids']:
            path=ROOT/plan['original_result_paths'][job['id']]
        else:continue
        result=read(path);assert result['execution_completed'] and result['job_id']==job['id']
        assert result.get('process_reaped') or result['execution_kind']=='inline_blocker_validation'
        results[job['id']]=suite.checked_result(job,result);paths[job['id']]=str(path.relative_to(ROOT))
    batch=asyncio.run(suite.execute(plan,folder,SimpleNamespace(workers=1,max_new_jobs=maximum,timeout_seconds=180),results))
    for job in plan['jobs']:
        if job['id'] not in results:continue
        if job['id'] in plan['retry_ids']:
            key=hashlib.sha256(job['id'].encode()).hexdigest()[:20]
            paths[job['id']]=str((folder/'jobs'/key/'result.json').relative_to(ROOT))
    suite.write_json(folder/'assessment.json',dict(batch=batch,jobs=results,result_paths=paths,
        original_timeouts_retained=True,source_sha256=plan['code_sha256']))
    print(json.dumps(dict(adapter=adapter,finished_new=batch['finished_new'],remaining=batch['remaining'])),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run'))
    parser.add_argument('adapter',choices=('st1','st2','structure','modes'))
    parser.add_argument('--max-new-jobs',type=int,default=1)
    args=parser.parse_args()
    if args.action=='prepare':prepare(args.adapter)
    else:run(args.adapter,args.max_new_jobs)
