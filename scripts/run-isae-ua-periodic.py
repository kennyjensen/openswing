"""Run the declared UA-1 periodic batch as serial, separately capped jobs.

Never retry a failed/interrupted job automatically. Completed evidence is
immutable; --resume skips only jobs with an intact successful execution receipt.
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


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args();base=args.output_dir.resolve()
    if base.exists() and not args.resume:
        parser.error('Use a new output directory, or explicit --resume for an interrupted batch')
    paths=[*sorted((ROOT/'openswing').glob('*.py')),Path(__file__).resolve(),
        *[ROOT/'scripts'/name for name in ('verify-isae-ua-periodic-cycle.py','verify-isae-ua-time.py',
            'isae_suite_unsteady.py','isae_ua_artifacts.py','isae_ua_periodic.py','isae_ua_section_reference.py')],
        ROOT/'.reference/asw_theory.txt',ROOT/'.reference/asw_uns_theory.txt',ROOT/'tests/test_isae_ua_periodic.py']
    pins={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in paths}
    jobs=[]
    for amplitude,tag in ((.05,'005'),(.1,'010'),(.3,'030'),(.5,'050')):
        for steps in (80,160):
            for cycle in range(1,9):
                jobs.append(dict(id=f'a{tag}-n{steps}-cycle{cycle:02}',amplitude_ratio=amplitude,
                    steps=steps,cycle=cycle,parent=None if cycle==1 else f'a{tag}-n{steps}-cycle{cycle-1:02}'))
    if not base.exists():
        base.mkdir(parents=True)
        plan=dict(scope='UA-1 eight-cycle finite-amplitude periodic attached-flow verification at k=.95',
            jobs=jobs,source_sha256=pins,production_changed=False,solver_tolerance=1e-10,
            gates=dict(final_cycle_waveform_error_fraction=.001,
                final_cycle_amplitude_error_fraction=.001,final_cycle_phase_error_deg=.1,
                final_cycle_mean_error_peak_fraction=.001,final_cycle_change_fraction=.0001,
                successive_waveform_error_ratio_maximum=.35),
            periodic_reference='Independent section-equation periodic boundary value, checked against a separate cold ODE integration.',
            native_ASWING_comparison=False,serial=True,threads=1,per_process_timeout_seconds=45,
            registered_rows=[r for r in (ROOT/'docs/validation/ISAE_STATUS.md').read_text().splitlines() if r.startswith('| [')])
        (base/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
        for path in paths:
            target=base/'frozen-code'/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(path,target)
    else:
        plan=json.loads((base/'plan.json').read_text())
        assert plan['source_sha256']==pins and plan['jobs']==jobs
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    for job in jobs:
        folder=base/job['id'];receipt=base/(job['id']+'-execution.json')
        if folder.exists():
            if not receipt.exists():raise RuntimeError('Existing job without terminal receipt; inspect authoritative process state: '+job['id'])
            saved=json.loads(receipt.read_text())
            if saved['exit_code']!=0:raise RuntimeError('Retained unsuccessful job; no automatic retry: '+job['id'])
            assert saved['report_sha256']==sha256((folder/'report.json').read_bytes()).hexdigest()
            continue
        command=['timeout','45s',sys.executable,str(ROOT/'scripts/verify-isae-ua-periodic-cycle.py'),
            '--steps',str(job['steps']),'--amplitude-ratio',str(job['amplitude_ratio']),
            '--cycle',str(job['cycle']),'--output-dir',str(folder)]
        if job['parent']:command+=['--parent',str(base/job['parent'])]
        started=time.monotonic()
        print(json.dumps(dict(starting=job['id'])),flush=True)
        with (base/(job['id']+'.log')).open('x') as stream:
            result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
        saved=dict(id=job['id'],exit_code=result.returncode,wall_seconds=time.monotonic()-started,command=command)
        if result.returncode==0:
            saved['report_sha256']=sha256((folder/'report.json').read_bytes()).hexdigest()
            report=json.loads((folder/'report.json').read_text())
            print(json.dumps(dict(completed=job['id'],seconds=report['seconds'],
                periodic_waveform_error_percent=100*report['periodic_waveform_error_fraction'],
                cycle_change_percent=None if report['previous_cycle_waveform_change_fraction'] is None
                    else 100*report['previous_cycle_waveform_change_fraction'])),flush=True)
        receipt.write_text(json.dumps(saved,indent=2)+'\n')
        if result.returncode!=0:
            print(json.dumps(dict(stopped=job['id'],exit_code=result.returncode,log=str(base/(job['id']+'.log')))),flush=True)
            raise SystemExit(result.returncode if result.returncode>0 else 1)
    (base/'batch-complete.json').write_text(json.dumps(dict(computed_jobs=len(jobs),serial=True,
        numerical_validation='Pending independent full-trajectory audit',goal_complete=False),indent=2)+'\n')
    print(json.dumps(dict(computed_jobs=len(jobs),status='all_jobs_terminal')),flush=True)


if __name__=='__main__':
    main()
