"""Run the eight inclined-wing references and probes serially, with receipts."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua2-incidence-20261101-r2'


def digest(p):return sha256(p.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    BASE.mkdir(parents=True,exist_ok=True)
    paths=[Path(__file__).resolve(),ROOT/'scripts/verify-isae-ua2-incidence.py',
        ROOT/'scripts/isae_ua_wing_incidence.py',ROOT/'scripts/isae_ua_wing_incidence_production.py',
        ROOT/'tests/test_isae_ua_wing_incidence.py',*sorted((ROOT/'openswing').glob('*.py'))]
    pins={str(p.relative_to(ROOT)):digest(p) for p in paths}
    jobs=[dict(id=f'{action}-n{n}-a{a}-k{round(k*1000):04d}',action=action,panels=n,alpha=a,k=k)
          for n in (20,40) for a in (5,9) for k in (.475,.95) for action in ('reference','probe')]
    p=BASE/'batch-plan.json'
    if p.exists():
        if not args.resume:parser.error('Inspect live handle before explicit --resume')
        plan=json.loads(p.read_text());assert plan['source_sha256']==pins and plan['jobs']==jobs
    else:
        plan=dict(jobs=jobs,source_sha256=pins,serial=True,threads=1,per_job_timeout_seconds=45,
            registered_rows=[r for r in (ROOT/'docs/validation/ISAE_STATUS.md').read_text().splitlines() if r.startswith('| [')],
            native_ASWING_comparison=False,production_changed=False)
        p.write_text(json.dumps(plan,indent=2)+'\n')
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    for job in jobs:
        receipt_path=BASE/(job['id']+'-execution.json');folder=BASE/job['id']
        if receipt_path.exists() or folder.exists():
            if not receipt_path.exists():raise RuntimeError('Inspect live process; no terminal receipt: '+job['id'])
            receipt=json.loads(receipt_path.read_text())
            assert receipt['exit_code']==0 and digest(folder/'report.json')==receipt['report_sha256']
            continue
        command=['timeout','45s',sys.executable,str(ROOT/'scripts/verify-isae-ua2-incidence.py'),job['action'],
                 '--panels',str(job['panels']),'--alpha',str(job['alpha']),'--k',str(job['k'])]
        print(json.dumps(dict(starting=job['id'])),flush=True);started=time.monotonic()
        with (BASE/(job['id']+'.log')).open('x') as stream:
            child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
            live=dict(job=job['id'],runner_pid=os.getpid(),child_pid=child.pid,command=command,status='running')
            (BASE/'live-job.json').write_text(json.dumps(live,indent=2)+'\n')
            code=child.wait()
        receipt=dict(**live,exit_code=code,wall_seconds=time.monotonic()-started);receipt['status']='terminal'
        if code==0:
            receipt['report_sha256']=digest(folder/'report.json')
            report=json.loads((folder/'report.json').read_text())
            print(json.dumps(dict(completed=job['id'],seconds=report['seconds'],wall_seconds=receipt['wall_seconds'],passed=report['passed'])),flush=True)
        receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
        (BASE/'live-job.json').write_text(json.dumps(receipt,indent=2)+'\n')
        if code!=0:
            print(json.dumps(dict(stopped=job['id'],exit_code=code,log=str(BASE/(job['id']+'.log')))),flush=True)
            raise SystemExit(code if code>0 else 1)
    assert all(digest(ROOT/n)==h for n,h in pins.items())
    (BASE/'batch-complete.json').write_text(json.dumps(dict(computed_jobs=len(jobs),full_goal_complete=False),indent=2)+'\n')
    print(json.dumps(dict(status='all_jobs_terminal',computed_jobs=len(jobs))),flush=True)


if __name__=='__main__':main()
