"""Serial, capped 32-step jobs for eight continuous UA-2 heave cycles."""
import argparse
from hashlib import sha256
import json
import math
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
    args=parser.parse_args();base=args.output_dir.resolve();plan_path=base/'batch-plan.json'
    if plan_path.exists() and not args.resume:parser.error('Use explicit --resume only for an inspected interrupted batch')
    jobs=[];settings=None
    for panels in (20,40):
        reference=json.loads((base/f'reference-n{panels}.json').read_text());assert reference['numerical_passed']
        current={n:reference['plan'][n] for n in ('span','chord','speed','k','amplitude_ratio','cycles')}
        if settings is None:settings=current
        else:assert settings==current
        for steps in (80,160):
            for segment in range(math.ceil((len(reference['grids'][str(steps)])-1)/32)):
                jobs.append(dict(id=f'n{panels}-t{steps}-part{segment:02}',panels=panels,steps=steps,segment=segment,
                    parent=None if segment==0 else f'n{panels}-t{steps}-part{segment-1:02}'))
    paths=[*sorted((ROOT/'openswing').glob('*.py')),Path(__file__).resolve(),
        *[ROOT/'scripts'/n for n in ('verify-isae-ua2-periodic-segment.py','verify-isae-ua2-periodic-reference.py',
            'verify-isae-ua-time.py','isae_suite_unsteady.py','isae_ua_artifacts.py','isae_ua_startup.py','isae_ua_wing_nonlinear.py','isae_ua_wing_periodic.py',
            'isae_ua_periodic.py','isae_ua_section_reference.py','audit-isae-ua2-periodic.py')],
        ROOT/'tests/test_isae_ua_wing_periodic.py',ROOT/'.reference/asw_theory.txt',ROOT/'.reference/asw_uns_theory.txt',
        base/'reference-n20.json',base/'reference-n40.json']
    pins={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in paths}
    if not plan_path.exists():
        plan=dict(scope=f'UA-2 A/c={settings["amplitude_ratio"]}, k={settings["k"]}: eight-cycle independent nonlinear periodic response, 20/40 strips',
            settings=settings,
            source_sha256=pins,jobs=jobs,numerical_jobs_serial=True,threads=1,job_timeout_seconds=45,
            gates=dict(fine_lift_waveform_error_fraction=.001,fine_per_strip_rate_waveform_error_fraction=.001,
                fine_first_step_relative_rate_error_fraction=.01,successive_lift_error_ratio_maximum=.35,
                fine_mesh_lift_change_fraction=.002,
                final_cycle_waveform_error_fraction=.001,final_cycle_amplitude_error_fraction=.001,
                final_cycle_phase_error_deg=.1,final_cycle_mean_error_peak_fraction=.001,
                final_cycle_change_fraction=.0001),
            native_ASWING_comparison=False,independent_spatial_reference=True,
            source_grid=dict(nominal_steps=[80,160],cycles=8,startup_first_step_maximum_fraction=1/256,maximum_growth=1.125,aligned_to_uniform_cycle_lattice=True),
            production_changed=False,app_defaults_changed=False,
            registered_rows=[r for r in (ROOT/'docs/validation/ISAE_STATUS.md').read_text().splitlines() if r.startswith('| [')],
            remaining='Other amplitudes/frequencies/incidences and native reference provenance remain unverified.')
        plan_path.write_text(json.dumps(plan,indent=2)+'\n')
        for p in paths:
            target=base/'frozen-code'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    else:
        plan=json.loads(plan_path.read_text());assert plan['source_sha256']==pins and plan['jobs']==jobs
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    for job in jobs:
        folder=base/job['id'];receipt_path=base/(job['id']+'-execution.json')
        if folder.exists():
            if not receipt_path.exists():raise RuntimeError('Inspect live process state: existing job has no terminal receipt '+job['id'])
            receipt=json.loads(receipt_path.read_text())
            if receipt['exit_code']!=0:raise RuntimeError('No automatic retry of retained failed job '+job['id'])
            assert receipt['report_sha256']==sha256((folder/'report.json').read_bytes()).hexdigest()
            continue
        command=['timeout','45s',sys.executable,str(ROOT/'scripts/verify-isae-ua2-periodic-segment.py'),
            '--panels',str(job['panels']),'--steps',str(job['steps']),'--segment',str(job['segment']),
            '--reference',str(base/f'reference-n{job["panels"]}.json'),'--output-dir',str(folder)]
        if job['parent']:command+=['--parent',str(base/job['parent'])]
        started=time.monotonic();print(json.dumps(dict(starting=job['id'])),flush=True)
        with (base/(job['id']+'.log')).open('x') as stream:
            result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
        receipt=dict(id=job['id'],exit_code=result.returncode,wall_seconds=time.monotonic()-started,command=command)
        if result.returncode==0:
            receipt['report_sha256']=sha256((folder/'report.json').read_bytes()).hexdigest()
            report=json.loads((folder/'report.json').read_text())
            print(json.dumps(dict(completed=job['id'],seconds=report['seconds'],
                segment_lift_error_percent=100*report['segment_lift_error_fraction_of_full_history_peak'])),flush=True)
        receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
        if result.returncode!=0:
            print(json.dumps(dict(stopped=job['id'],exit_code=result.returncode)),flush=True)
            raise SystemExit(result.returncode if result.returncode>0 else 1)
    (base/'batch-complete.json').write_text(json.dumps(dict(computed_segments=len(jobs),serial=True,
        verification='Pending full-trajectory audit',goal_complete=False),indent=2)+'\n')
    print(json.dumps(dict(computed_segments=len(jobs),status='all_terminal')),flush=True)


if __name__=='__main__':main()
