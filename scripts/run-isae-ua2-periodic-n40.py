"""Run the predeclared inclined N40 periodic comparison in small serial jobs."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from isae_ua2_incidence_periodic_n40 import ROOT,BASE,GATES,grid,windows,full_request

AUDIT_JOBS_PER_CHUNK=8


def digest(p):
    h=sha256()
    with p.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def prepare():
    assert not (BASE/'production-plan.json').exists()
    assert json.loads((BASE/'reference-verification-execution.json').read_text())['exit_code']==0
    reference=json.loads((BASE/'reference-verified.json').read_text());assert reference['passed']
    reference_plan=json.loads((BASE/'reference-plan.json').read_text())
    assert reference['reference_plan_sha256']==digest(BASE/'reference-plan.json')
    assert reference['periodic_reference_sha256']==digest(BASE/'periodic-reference.json')
    assert reference['baseline_n20_sha256']==digest(BASE/'baseline-n20.json')
    for n,h in {**reference['source_sha256'],**reference['input_sha256'],**reference_plan['production_sha256']}.items():assert digest(ROOT/n)==h,n
    for t in reference['reference_parts'].values():assert digest(BASE/t['path'])==t['sha256']
    paths=[*sorted((ROOT/'openswing').glob('*.py')),Path(__file__).resolve(),
        ROOT/'scripts/verify-isae-ua2-periodic-n40-segment.py',ROOT/'scripts/audit-isae-ua2-periodic-n40.py',
        ROOT/'scripts/isae_ua_artifacts.py',BASE/'reference-plan.json',BASE/'reference-verified.json',
        BASE/'periodic-reference.json',BASE/'baseline-n20.json',
        *[ROOT/n for n in reference['source_sha256'] if Path(n).suffix in ('.py','.txt')]]
    pins={str(p.relative_to(ROOT)):digest(p) for p in paths}
    plan=dict(source_sha256=pins,reference_input_sha256={**reference['source_sha256'],**reference['input_sha256']},
        full_request=full_request(),times=grid(),gates=GATES,
        jobs=[dict(part=i,start_index=a,end_index=b) for i,(a,b) in enumerate(windows())],
        max_steps_per_job=16,audit_jobs_per_chunk=AUDIT_JOBS_PER_CHUNK,per_job_timeout_seconds=45,serial=True,threads=1,
        registered_rows=[r for r in (ROOT/'docs/validation/ISAE_STATUS.md').read_text().splitlines() if r.startswith('| [')],
        native_ASWING_comparison=False,production_changed=False,new_temporal_refinement_claim=False,
        scope='40-strip periodic time accuracy and 20/40 integrated-lift spatial refinement at fixed fine temporal grid.')
    (BASE/'production-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for p in paths:
        target=BASE/'frozen-code'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert digest(target)==digest(p)
        else:shutil.copyfile(p,target)
    print(json.dumps(dict(prepared=True,production_jobs=len(windows()),audit_chunks=(len(windows())+AUDIT_JOBS_PER_CHUNK-1)//AUDIT_JOBS_PER_CHUNK)))


def run(action,limit):
    plan=json.loads((BASE/'production-plan.json').read_text())
    for n,h in plan['source_sha256'].items():assert digest(ROOT/n)==h,n
    if action=='production':
        jobs=[dict(id=f'part{i:03d}',folder=f'production/part{i:03d}',receipt=f'production/part{i:03d}-execution.json',log=f'production/part{i:03d}.log',
                   output=f'production/part{i:03d}/report.json',script='verify-isae-ua2-periodic-n40-segment.py',args=['--part',str(i)]) for i in range(len(windows()))]
    else:
        assert json.loads((BASE/'production-complete.json').read_text())['computed_jobs']==len(windows())
        jobs=[dict(id=f'audit-chunk{i:03d}',folder=None,receipt=f'audit-chunk{i:03d}-execution.json',log=f'audit-chunk{i:03d}.log',
                   output=f'audit-chunk{i:03d}.json',script='audit-isae-ua2-periodic-n40.py',args=['chunk','--index',str(i)])
              for i in range((len(windows())+AUDIT_JOBS_PER_CHUNK-1)//AUDIT_JOBS_PER_CHUNK)]
        jobs.append(dict(id='audit',folder=None,receipt='audit-execution.json',log='audit.log',output='audit.json',script='audit-isae-ua2-periodic-n40.py',args=['combine']))
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    completed=0
    for job in jobs:
        receipt_path=BASE/job['receipt'];output=BASE/job['output'];log=BASE/job['log']
        exists=receipt_path.exists() or output.exists() or log.exists() or (job['folder'] is not None and (BASE/job['folder']).exists())
        if exists:
            if not receipt_path.exists():raise RuntimeError('Inspect live or interrupted job before any recovery: '+job['id'])
            receipt=json.loads(receipt_path.read_text());assert receipt['exit_code']==0,'Retained failed job: '+job['id']
            assert digest(output)==receipt['report_sha256'];continue
        command=['timeout','45s',sys.executable,str(ROOT/'scripts'/job['script']),*job['args']]
        log.parent.mkdir(parents=True,exist_ok=True);started=time.monotonic()
        print(json.dumps(dict(starting=job['id'])),flush=True)
        with log.open('x') as stream:
            process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
            live=dict(job=job['id'],action=action,runner_pid=os.getpid(),child_pid=process.pid,command=command,status='running',start_time_unix=time.time())
            (BASE/f'live-{action}.json').write_text(json.dumps(live,indent=2)+'\n')
            code=process.wait()
        receipt={**live,'status':'terminal','exit_code':code,'wall_seconds':time.monotonic()-started}
        if output.exists():receipt['report_sha256']=digest(output)
        receipt_path.write_text(json.dumps(receipt,indent=2)+'\n');(BASE/f'live-{action}.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps(dict(completed=job['id'],exit_code=code,wall_seconds=receipt['wall_seconds'])),flush=True)
        if code:raise SystemExit(code if code>0 else 1)
        completed+=1
        if limit is not None and completed>=limit:
            print(json.dumps(dict(status='requested_job_limit',new_jobs=completed)),flush=True);return
    if action=='production':
        (BASE/'production-complete.json').write_text(json.dumps(dict(computed_jobs=len(jobs),serial=True,audit_status='pending',full_goal_complete=False),indent=2)+'\n')
    print(json.dumps(dict(status='all_jobs_terminal',action=action,computed_jobs=len(jobs))),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('prepare','production','audit'));parser.add_argument('--max-new-jobs',type=int)
    args=parser.parse_args()
    if args.max_new_jobs is not None and args.max_new_jobs<1:parser.error('Positive job limit required')
    if args.action=='prepare':prepare()
    else:run(args.action,args.max_new_jobs)
