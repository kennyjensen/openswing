"""Complete the UA-2 finite-amplitude grid with small serial numerical jobs.

The finished A/c=.5,k=.95 batch is reused explicitly. No numerical worker is
retried automatically, and all numerical workers retain their 45-second cap.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
BASELINE=ROOT/'artifacts/isae/ua2-nonlinear-20261101'


def execute(base,name,command,env,*,cap=True,live=False):
    receipt_path=base/(name+'-execution.json')
    if receipt_path.exists():
        saved=json.loads(receipt_path.read_text())
        if saved['exit_code']!=0:raise RuntimeError('Retained unsuccessful operation; inspect before any retry: '+name)
        return saved
    command=(['timeout','45s'] if cap else [])+command
    start=time.monotonic();print(json.dumps(dict(starting_operation=name)),flush=True)
    if live:
        completed=subprocess.run(command,cwd=ROOT,env=env)
    else:
        with (base/(name+'.log')).open('x') as stream:
            completed=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
    receipt=dict(name=name,command=command,exit_code=completed.returncode,wall_seconds=time.monotonic()-start)
    receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(dict(completed_operation=name,exit_code=completed.returncode)),flush=True)
    if completed.returncode!=0:raise SystemExit(completed.returncode if completed.returncode>0 else 1)
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args();base=args.output_dir.resolve();plan_path=base/'plan.json'
    if base.exists() and not args.resume:parser.error('Use a fresh output directory or explicit inspected --resume')
    cases=[dict(id=f'k{ktag}-a{atag}',k=k,amplitude_ratio=a)
        for k,ktag in ((.475,'0475'),(.95,'095'))
        for a,atag in ((.05,'005'),(.1,'010'),(.3,'030'),(.5,'050')) if (k,a)!=(.95,.5)]
    paths=[*sorted((ROOT/'openswing').glob('*.py')),Path(__file__).resolve(),
        *[ROOT/'scripts'/n for n in ('run-isae-ua2-nonlinear.py','verify-isae-ua2-nonlinear-reference.py',
            'verify-isae-ua2-nonlinear-segment.py','audit-isae-ua2-nonlinear.py','verify-isae-ua-time.py',
            'isae_suite_unsteady.py','isae_ua_wing_nonlinear.py','isae_ua_startup.py','isae_ua_artifacts.py')],
        ROOT/'.reference/asw_theory.txt',ROOT/'.reference/asw_uns_theory.txt']
    pins={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in paths}
    old_plan=json.loads((BASELINE/'batch-plan.json').read_text())
    for name,digest in old_plan['source_sha256'].items():
        assert sha256((BASELINE/'frozen-code'/name).read_bytes()).hexdigest()==digest
        if name.startswith('openswing/') or name.endswith('isae_ua_wing_nonlinear.py'):
            assert sha256((ROOT/name).read_bytes()).hexdigest()==digest
    reused_paths=[BASELINE/n for n in ('completion.json','batch-plan.json','batch-complete.json',
        'reference-n20.json','reference-n40.json','audit-n20.json','audit-n40.json')]
    reused_hashes={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in reused_paths}
    if not plan_path.exists():
        base.mkdir(parents=True,exist_ok=True)
        plan=dict(scope='UA-2 finite-amplitude first-cycle grid: A/c=.05,.1,.3,.5; k=.475,.95; 20/40 strips; nominal 80/160 time steps',
            new_cases=cases,reused_case=dict(k=.95,amplitude_ratio=.5,path=str(BASELINE.relative_to(ROOT)),sha256=reused_hashes),
            new_production_trajectories=28,new_production_segments=154,new_reference_jobs=14,new_audit_jobs=14,
            expected_total_refinement_checks=16,expected_total_mesh_checks=8,
            gates=old_plan['gates'],source_sha256=pins,serial=True,threads=1,numerical_job_timeout_seconds=45,
            production_changed=False,app_defaults_changed=False,native_ASWING_comparison=False,
            registered_rows=[r for r in (ROOT/'docs/validation/ISAE_STATUS.md').read_text().splitlines() if r.startswith('| [')])
        plan_path.write_text(json.dumps(plan,indent=2)+'\n')
        for p in paths:
            target=base/'frozen-code'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    else:
        plan=json.loads(plan_path.read_text());assert plan['source_sha256']==pins and plan['new_cases']==cases
        assert plan['reused_case']['sha256']==reused_hashes
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    for case in cases:
        folder=base/case['id'];folder.mkdir(exist_ok=True)
        for panels in (20,40):
            execute(base,case['id']+f'-reference-n{panels}',[sys.executable,str(ROOT/'scripts/verify-isae-ua2-nonlinear-reference.py'),
                '--panels',str(panels),'--amplitude-ratio',str(case['amplitude_ratio']),'--k',str(case['k']),
                '--output',str(folder/f'reference-n{panels}.json')],env)
        command=[sys.executable,str(ROOT/'scripts/run-isae-ua2-nonlinear.py'),'--output-dir',str(folder)]
        if (folder/'batch-plan.json').exists():command.append('--resume')
        execute(base,case['id']+'-production',command,env,cap=False,live=True)
        for panels in (20,40):
            execute(base,case['id']+f'-audit-n{panels}',[sys.executable,str(ROOT/'scripts/audit-isae-ua2-nonlinear.py'),
                '--panels',str(panels),'--base-dir',str(folder)],env)
        audits=[json.loads((folder/f'audit-n{n}.json').read_text()) for n in (20,40)]
        assert all(a['refinement_check_passed'] for a in audits)
        print(json.dumps(dict(case_complete=case['id'],checks_passed=2)),flush=True)
    (base/'batch-complete.json').write_text(json.dumps(dict(new_cases_completed=7,new_production_segments=154,
        reused_cases=1,all_terminal=True,goal_complete=False),indent=2)+'\n')
    print(json.dumps(dict(status='all_cases_terminal',new_cases=7,reused_cases=1)),flush=True)


if __name__=='__main__':main()
