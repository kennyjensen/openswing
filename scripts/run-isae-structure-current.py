"""Run the registered structural adapters in small serial batches.

Uses the existing suite planners, source checks, worker and strict result
accounting. Does not rebuild the unrelated 279-model inventory on each batch.
ST-6's independently reviewed lack of native targets stays explicit.
"""
import argparse
import asyncio
from collections import Counter
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
    folder=BASE/adapter;folder.mkdir()
    jobs=suite.plan_jobs(ROOT,[adapter])
    pins=suite.code_pins(ROOT,[adapter])
    pins[str(Path(__file__).resolve().relative_to(ROOT))]=suite.digest(Path(__file__))
    sources=suite.verify_registered_upstream_inputs(ROOT,jobs,'f62943df20e9e4d7d9f50e070477b22426b5f865')
    plan=dict(jobs=jobs,code_sha256=pins,verified_registered_upstream_inputs=sources,
        scope='All current registered jobs for this adapter; no claim of full-family coverage.',
        strict_reference_tolerances=True,workers=1,timeout_seconds=45)
    suite.write_json(folder/'plan.json',plan)
    for name in pins:
        target=folder/'frozen-code'/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((ROOT/name).read_bytes())
    print(json.dumps(dict(adapter=adapter,jobs=len(jobs),
        numerical_jobs=sum(j.get('execution_route')!='unsupported' for j in jobs),
        required=sum(j['expected_outputs'] for j in jobs))),flush=True)


def run(adapter,maximum):
    folder=BASE/adapter;plan=read(folder/'plan.json');results={}
    assert suite.stable_code(ROOT,plan['code_sha256'])
    for job in plan['jobs']:
        key=hashlib.sha256(job['id'].encode()).hexdigest()[:20]
        sub=folder/'jobs'/key
        if (sub/'result.json').exists():
            assert read(sub/'request.json')==dict(job=job,code_sha256=plan['code_sha256'])
            result=read(sub/'result.json')
            assert result['job_id']==job['id'] and result['execution_completed']
            assert result.get('process_reaped') or result['execution_kind']=='inline_blocker_validation'
            results[job['id']]=suite.checked_result(job,result)
    args=SimpleNamespace(workers=1,max_new_jobs=maximum,timeout_seconds=45)
    batch=asyncio.run(suite.execute(plan,folder,args,results))
    # Store complete strict assessed results, including unavailable comparisons.
    suite.write_json(folder/'assessment.json',dict(batch=batch,jobs=results,
        statuses=dict(Counter(r['status'] for r in results.values())),
        source_sha256=plan['code_sha256']))
    print(json.dumps(dict(adapter=adapter,**batch)),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run'))
    parser.add_argument('adapter',choices=('st1','st2','structure','modes'))
    parser.add_argument('--max-new-jobs',type=int,default=3)
    args=parser.parse_args()
    if args.action=='prepare':prepare(args.adapter)
    else:run(args.adapter,args.max_new_jobs)
