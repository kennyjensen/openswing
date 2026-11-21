"""Recover the stopped UA-2 batch serially, retaining its timed-out attempt."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from isae_ua2_periodic_records import records

ROOT=Path(__file__).resolve().parents[1]
BASE=Path(os.environ['OPENSWING_UA2_PERIODIC_BASE']).resolve()


def digest(p):return sha256(p.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-new-jobs',type=int)
    args=parser.parse_args()
    if args.max_new_jobs is not None and args.max_new_jobs<1:parser.error('Positive job limit required')
    plan=json.loads((BASE/'recovery-plan.json').read_text())
    for n,h in plan['source_sha256'].items():assert digest(ROOT/n)==h,n
    assert json.loads((BASE/'batch-execution.json').read_text())['exit_code']==124
    for r in plan['retained_completed']:
        receipt=json.loads((BASE/r['receipt']).read_text())
        assert receipt['exit_code']==0 and digest(BASE/r['folder']/'report.json')==receipt['report_sha256']
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    completed=0
    for job in plan['jobs']:
        folder=BASE/job['folder'];receipt_path=BASE/job['receipt']
        log=BASE/(job['folder']+'.log')
        if folder.exists() or receipt_path.exists() or log.exists():
            if not receipt_path.exists():raise RuntimeError('Inspect live or interrupted recovery before proceeding: '+job['id'])
            receipt=json.loads(receipt_path.read_text())
            assert receipt['exit_code']==0,'Preserve failed recovery: '+job['id']
            assert digest(folder/'report.json')==receipt['report_sha256']
            continue
        log.parent.mkdir(parents=True,exist_ok=True)
        command=['timeout','45s',sys.executable,str(ROOT/'scripts/verify-isae-ua2-periodic-recovery.py'),'--job',str(job['ordinal'])]
        started=time.monotonic()
        print(json.dumps(dict(starting=job['id'])),flush=True)
        with log.open('x') as stream:
            process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
            live=dict(job=job['id'],runner_pid=os.getpid(),child_pid=process.pid,command=command,status='running',start_time_unix=time.time())
            (BASE/'live-recovery.json').write_text(json.dumps(live,indent=2)+'\n')
            code=process.wait()
        receipt={**live,'exit_code':code,'status':'terminal','wall_seconds':time.monotonic()-started}
        if code==0:
            receipt['report_sha256']=digest(folder/'report.json')
            report=json.loads((folder/'report.json').read_text())
            print(json.dumps(dict(completed=job['id'],solver_seconds=report['solver_seconds'],wall_seconds=receipt['wall_seconds'],maximum_residual=report['maximum_residual'])),flush=True)
        receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
        (BASE/'live-recovery.json').write_text(json.dumps(receipt,indent=2)+'\n')
        if code:
            print(json.dumps(dict(stopped=job['id'],exit_code=code,log=str(log))),flush=True)
            raise SystemExit(code if code>0 else 1)
        completed+=1
        if args.max_new_jobs is not None and completed>=args.max_new_jobs:
            print(json.dumps(dict(status='requested_job_limit',new_jobs=completed)),flush=True)
            return
    all_records=[r for n in (320,640) for r in records(BASE,n)]
    for r in all_records:
        receipt=json.loads((BASE/r['receipt']).read_text())
        assert receipt['exit_code']==0 and digest(BASE/r['folder']/'report.json')==receipt['report_sha256']
    (BASE/'batch-complete.json').write_text(json.dumps(dict(computed_jobs=len(all_records),logical_intervals=78,
        retained_completed_jobs=len(plan['retained_completed']),recovery_jobs=len(plan['jobs']),
        retained_failed_attempts=1,serial=True,audit_status='Pending full-history audit',full_goal_complete=False),indent=2)+'\n')
    print(json.dumps(dict(status='all_jobs_terminal',computed_jobs=len(all_records))),flush=True)


if __name__=='__main__':main()
