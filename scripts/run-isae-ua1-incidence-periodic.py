"""Serial inclined UA-1 periodic jobs, each capped and independently receipted."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from isae_ua_incidence_periodic import GATES,CYCLES

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua1-incidence-periodic-20261101'


def digest(p):return sha256(p.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--max-new-jobs',type=int)
    args=parser.parse_args()
    if args.max_new_jobs is not None and args.max_new_jobs<1:parser.error('Positive job limit required')
    reference=json.loads((BASE/'reference.json').read_text())
    assert reference['passed']
    assert json.loads((BASE/'reference-execution.json').read_text())['exit_code']==0
    paths=[*sorted((ROOT/'openswing').glob('*.py')),Path(__file__).resolve(),
        *[ROOT/'scripts'/n for n in ('verify-isae-ua1-incidence-periodic-segment.py',
            'isae_ua_incidence_periodic.py','isae_ua_incidence_reference.py','isae_ua_artifacts.py','isae_suite_unsteady.py')],
        ROOT/'tests/test_isae_ua_incidence_periodic.py',BASE/'reference.json',
        ROOT/'.reference/asw_theory.txt',ROOT/'.reference/asw_uns_theory.txt']
    pins={str(p.relative_to(ROOT)):digest(p) for p in paths}
    jobs=[dict(id=f'n{steps}-part{part:02d}',steps=steps,part=part)
          for steps in (80,160) for part in range(CYCLES*steps//40)]
    if (BASE/'batch-plan.json').exists():
        if not args.resume:parser.error('Use explicit --resume for an existing batch; inspect any live handle first')
        plan=json.loads((BASE/'batch-plan.json').read_text())
        assert plan['source_sha256']==pins and plan['jobs']==jobs
    else:
        plan=dict(scope='UA-1 alpha9 k.94 A/c.5: eight continuous cycles, 4 circulation unknowns, 80/160 steps per cycle',
            source_sha256=pins,jobs=jobs,gates=GATES,serial=True,threads=1,per_job_timeout_seconds=45,
            normalization='Periodic lift and circulation use peak departures from their reference means; rate uses its reference peak. Cold lift/circulation use peak departures from pre-motion steady values. Every strip is checked.',
            last_cycle_change='CL, circulation and rate separately, with their periodic normalization.',
            initial_state='Production steady equilibrium, never the independent periodic solution.',
            fixed_forcing='Complete eight-cycle Ax/Az table present before the first step and preserved across every checkpoint.',
            native_ASWING_comparison=False,production_changed=False,
            registered_rows=[r for r in (ROOT/'docs/validation/ISAE_STATUS.md').read_text().splitlines() if r.startswith('| [')])
        (BASE/'batch-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
        for p in paths:
            target=BASE/'frozen-code'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():assert digest(target)==pins[str(p.relative_to(ROOT))]
            else:shutil.copyfile(p,target)
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    completed=0
    for job in jobs:
        folder=BASE/job['id'];receipt_path=BASE/(job['id']+'-execution.json')
        if folder.exists() or receipt_path.exists():
            if not receipt_path.exists():raise RuntimeError('Job has no terminal receipt; inspect actual live process before any recovery: '+job['id'])
            receipt=json.loads(receipt_path.read_text())
            if receipt['exit_code']!=0:raise RuntimeError('Retained failed job; no automatic restart: '+job['id'])
            assert digest(folder/'report.json')==receipt['report_sha256']
            continue
        command=['timeout','45s',sys.executable,str(ROOT/'scripts/verify-isae-ua1-incidence-periodic-segment.py'),
                 '--steps',str(job['steps']),'--part',str(job['part'])]
        started=time.monotonic()
        print(json.dumps(dict(starting=job['id'])),flush=True)
        with (BASE/(job['id']+'.log')).open('x') as stream:
            process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
            live=dict(job=job['id'],runner_pid=os.getpid(),child_pid=process.pid,command=command,
                      start_time_unix=time.time(),status='running')
            (BASE/'live-job.json').write_text(json.dumps(live,indent=2)+'\n')
            code=process.wait()
        receipt=dict(**live,exit_code=code,wall_seconds=time.monotonic()-started)
        receipt['status']='terminal'
        if code==0:
            receipt['report_sha256']=digest(folder/'report.json')
            report=json.loads((folder/'report.json').read_text())
            print(json.dumps(dict(completed=job['id'],solver_seconds=report['solver_seconds'],
                wall_seconds=receipt['wall_seconds'],maximum_residual=report['maximum_residual'])),flush=True)
        receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
        (BASE/'live-job.json').write_text(json.dumps(receipt,indent=2)+'\n')
        if code!=0:
            print(json.dumps(dict(stopped=job['id'],exit_code=code,log=str(BASE/(job['id']+'.log')))),flush=True)
            raise SystemExit(code if code>0 else 1)
        completed+=1
        if args.max_new_jobs is not None and completed>=args.max_new_jobs:
            print(json.dumps(dict(status='requested_job_limit',new_jobs=completed)),flush=True)
            return
    (BASE/'batch-complete.json').write_text(json.dumps(dict(computed_jobs=len(jobs),serial=True,
        audit_status='Pending full-history audit',full_goal_complete=False),indent=2)+'\n')
    print(json.dumps(dict(status='all_jobs_terminal',computed_jobs=len(jobs))),flush=True)


if __name__=='__main__':main()
