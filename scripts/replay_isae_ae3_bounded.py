"""Replay the full AE-3 adapter in small, serial, resumable jobs.

Default: one new job per invocation. Every reference remains in the summary,
including unrun jobs and embedded arrays whose original setup is unavailable.
No result is overwritten; use a new output directory after changing code.
"""
import argparse
from datetime import datetime, timezone
import fnmatch
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from scripts import isae_suite_ae3 as adapter
from scripts.isae_acceptance import apply_reference_acceptance

LIMITS=dict(address_space_bytes=512*1024**2,cpu_seconds=15,wall_seconds=25)
THREADS={key:'1' for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}


def write(path,value):
    path=Path(path);temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');temporary.replace(path)


def read(path):return json.loads(Path(path).read_text())


def runner():
    spec=importlib.util.spec_from_file_location('ae3_suite_runner',ROOT/'scripts/run-isae-suite.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def limits():
    resource.setrlimit(resource.RLIMIT_AS,(LIMITS['address_space_bytes'],)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(LIMITS['cpu_seconds'],)*2)


def summarize(directory,plan):
    rows=[]
    for job in plan['jobs']:
        path=directory/'jobs'/job['id']/'result.json'
        result=read(path) if path.exists() else {}
        checks=result.get('reference_checks',[]);computed=result.get('status')=='computed'
        rows.append(dict(id=job['id'],kind=job['target_kind'],status=result.get('status','unrun'),
            required=job['expected_outputs'],computed=len(checks) if computed else 0,
            passed=sum(c['passed'] for c in checks) if computed else 0,
            mismatches=sum(not c['passed'] for c in checks) if computed else 0))
    total={k:sum(row[k] for row in rows) for k in ('required','computed','passed','mismatches')}
    total['uncomputed']=total['required']-total['computed']
    report=dict(observed_utc=datetime.now(timezone.utc).isoformat(),totals=total,jobs=rows,
        relative_reference_tolerance=.05,limits=LIMITS,complete_family_reproduction=False,
        qualifications=adapter.QUALIFICATIONS)
    write(directory/'summary.json',report)
    return total


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--job-pattern',default='*')
    parser.add_argument('--max-new-jobs',type=int,default=1)
    parser.add_argument('--plan-only',action='store_true')
    args=parser.parse_args()
    if args.max_new_jobs<1:parser.error('--max-new-jobs must be positive')
    directory=args.output_dir.resolve();directory.mkdir(parents=True,exist_ok=True)
    suite=runner();pins=suite.code_pins(ROOT,['ae3'])
    pins['scripts/replay_isae_ae3_bounded.py']=suite.digest(__file__)
    jobs=adapter.plan(ROOT)
    if (directory/'plan.json').exists():
        plan=read(directory/'plan.json')
        if plan['jobs']!=jobs or plan['code_sha256']!=pins or plan['limits']!=LIMITS:
            raise ValueError('Planned sources/settings changed; preserve this run and use a new output directory.')
    else:
        plan=dict(observed_utc=datetime.now(timezone.utc).isoformat(),jobs=jobs,code_sha256=pins,limits=LIMITS)
        write(directory/'plan.json',plan)
    selected=[j for j in jobs if fnmatch.fnmatchcase(j['id'],args.job_pattern)]
    if not selected:raise ValueError('Job pattern matched no AE-3 jobs.')
    if args.plan_only:
        print(json.dumps(summarize(directory,plan)),flush=True);return
    pending=[j for j in selected if not (directory/'jobs'/j['id']/'terminal.json').exists()]
    for job in pending[:args.max_new_jobs]:
        folder=directory/'jobs'/job['id'];folder.mkdir(parents=True,exist_ok=False)
        request,output=folder/'request.json',folder/'strict-result.json'
        write(request,dict(job=job,code_sha256=pins))
        before=time.monotonic();started=datetime.now(timezone.utc).isoformat()
        if job['execution_route']=='unsupported':
            result=suite.checked_result(job,adapter.validate_blocked(ROOT,job));write(output,result)
            terminal=dict(status='inline',subprocess_started=False,physical_solver_calls=0)
        else:
            raw=folder/'raw';raw.mkdir()
            with (folder/'stdout.log').open('wb') as out,(folder/'stderr.log').open('wb') as err:
                child=subprocess.Popen([sys.executable,str(ROOT/'scripts/run-isae-suite.py'),'--worker',str(request),str(output)],
                    cwd=ROOT,env={**os.environ,**THREADS,'TMPDIR':str(raw)},stdout=out,stderr=err,
                    start_new_session=True,preexec_fn=limits)
                timed_out=False
                try:child.wait(timeout=LIMITS['wall_seconds'])
                except subprocess.TimeoutExpired:
                    timed_out=True;os.killpg(child.pid,signal.SIGKILL);child.wait()
                finally:
                    if child.poll() is None:os.killpg(child.pid,signal.SIGKILL);child.wait()
            result=read(output) if output.exists() and child.returncode==0 else dict(
                status='timeout' if timed_out else 'process_error',reference_match=False,numerical_pass=False,
                reference_checks=[],exit_code=child.returncode)
            terminal=dict(status=result['status'],subprocess_started=True,process_reaped=True,
                exit_code=child.returncode,timed_out=timed_out)
        if not suite.stable_code(ROOT,pins):raise ValueError('Source changed during bounded replay.')
        result=apply_reference_acceptance(result,relative_tolerance=.05)
        write(folder/'result.json',result)
        terminal.update(started_utc=started,ended_utc=datetime.now(timezone.utc).isoformat(),
            wall_seconds=time.monotonic()-before,limits=LIMITS)
        write(folder/'terminal.json',terminal)
        print(json.dumps(dict(job=job['id'],**terminal)),flush=True)
    print(json.dumps(summarize(directory,plan)),flush=True)


if __name__=='__main__':main()
