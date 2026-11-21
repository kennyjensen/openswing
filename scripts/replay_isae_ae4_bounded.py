"""Run one registered AE-4 comparison per invocation under fixed resource caps.

The complete historical and declared scopes remain separate in summary.json.
An existing attempt is never overwritten. Run invocations serially; an advisory
lock also prevents simultaneous numerical workers started by this runner.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from scripts import isae_suite_ae4 as adapter
from scripts.isae_acceptance import apply_reference_acceptance

LIMITS=dict(address_space_bytes=512*1024**2,cpu_seconds=15,wall_seconds=25)
THREADS={key:'1' for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}


def read(path):return json.loads(Path(path).read_text())
def write(path,value):
    path=Path(path);temporary=path.with_suffix('.tmp')
    with temporary.open('w') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
    temporary.replace(path)
def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()


@contextmanager
def serial_lock():
    """Use a live OS lock, not a stale PID file, to serialize this runner."""
    lock=ROOT/'artifacts/isae/ae4-bounded.lock';lock.parent.mkdir(parents=True,exist_ok=True)
    with lock.open('a') as stream:
        try:fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Another AE-4 bounded invocation holds the serial lock.') from None
        try:yield
        finally:fcntl.flock(stream,fcntl.LOCK_UN)


def suite_runner():
    spec=importlib.util.spec_from_file_location('_ae4_shared_runner',ROOT/'scripts/run-isae-suite.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def prepare(directory):
    suite=suite_runner()
    code=suite.code_pins(ROOT,['ae4'])
    code['scripts/replay_isae_ae4_bounded.py']=digest(__file__)
    jobs=adapter.plan(ROOT,comparison_scopes=[adapter.SCOPE])
    path=directory/'plan.json'
    contents=dict(jobs=jobs,code_sha256=code,limits=LIMITS,relative_reference_tolerance=.05)
    if path.exists():
        plan=read(path)
        if any(plan.get(k)!=v for k,v in contents.items()):
            raise ValueError('Sources, scope or limits changed; preserve this run and use a fresh output directory.')
    else:
        plan=dict(observed_utc=utc(),**contents)
        write(path,plan)
    return plan,suite


def choose_job(plan,directory,*,speed=None,nominal=None):
    candidates=[j for j in plan['jobs'] if j['execution_route']=='worker'
                and (speed is None or j['IAS']==speed) and (nominal is None or j['nominal']==nominal)]
    if not candidates:raise ValueError('No executable job matches the requested speed and mesh.')
    for job in candidates:
        folder=directory/'jobs'/job['id']
        if folder.exists():
            if not (folder/'terminal.json').exists():
                raise ValueError('An unterminated attempt exists; inspect its process and preserve its directory before continuing.')
            continue
        return job
    return None


def summarize(directory,plan):
    """Count finite paired values separately from completed numerical jobs."""
    rows=[];scopes={};results={}
    for job in plan['jobs']:
        folder=directory/'jobs'/job['id'];checks=[]
        status='unsupported' if job['execution_route']=='unsupported' else 'unrun'
        if (folder/'terminal.json').exists():
            terminal=read(folder/'terminal.json');status=terminal['status']
            if status=='computed':
                if not (terminal.get('process_reaped') and terminal.get('returncode')==0 and terminal.get('sources_unchanged')):
                    raise ValueError('Computed result lacks a successful, source-verified terminal receipt.')
                strict=read(folder/'strict-result.json')
                if digest(folder/'strict-result.json')!=terminal['strict_result_sha256']:
                    raise ValueError('Retained result changed after acceptance.')
                adapter.validate_result_contract(job,strict)
                accepted=apply_reference_acceptance(strict,relative_tolerance=.05)
                if accepted!=read(folder/'result.json'):
                    raise ValueError('Saved acceptance view differs from its strict result.')
                checks=accepted['reference_checks'];results[job['id']]=strict
        required=job['expected_outputs']
        computed=sum(c.get('predicted') is not None for c in checks)
        passed=sum(c['passed'] for c in checks)
        row=dict(id=job['id'],scope=job['comparison_scope'],status=status,required=required,
                 computed=computed,passed=passed,mismatches=computed-passed,
                 unavailable=required-computed,blocker_code=job.get('blocker_code'))
        rows.append(row)
        total=scopes.setdefault(row['scope'],dict(required=0,computed=0,passed=0,mismatches=0,
            unavailable=0,unrun=0,blocked=0,failed=0,unmatched=0,computed_jobs=0))
        for key in ('required','computed','passed','mismatches','unavailable'):total[key]+=row[key]
        total['computed_jobs']+=status=='computed'
        if status=='unrun':total['unrun']+=required
        elif status=='unsupported':total['blocked']+=required
        elif status=='computed':total['unmatched']+=required-computed
        else:total['failed']+=required
    report=dict(observed_utc=utc(),scopes=scopes,jobs=rows,limits=LIMITS,
        relative_reference_tolerance=.05,mesh_diagnostics=adapter.mesh_diagnostics(plan['jobs'],results),
        complete_family_reproduction=False,qualifications=adapter.QUALIFICATIONS,
        artifact_policy='Raw artifacts are authenticated in each worker. Summary revalidates compact strict contracts and terminal-bound hashes; use the adapter artifact verifier for a fresh raw-file audit.')
    write(directory/'summary.json',report)
    return report


def preload(folder):
    os.environ.update(THREADS)
    resource.setrlimit(resource.RLIMIT_AS,(LIMITS['address_space_bytes'],)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(LIMITS['cpu_seconds'],)*2)
    started=time.monotonic();cpu=time.process_time()
    def expired(signum,frame):raise TimeoutError('Library preload exceeded its wall limit.')
    previous=signal.signal(signal.SIGALRM,expired)
    signal.setitimer(signal.ITIMER_REAL,LIMITS['wall_seconds'])
    try:
        import numpy
        import scipy.linalg
        import scipy.sparse.linalg
        import openswing.source_airflow
        import openswing.source_discrete
        import openswing.equilibrium_state
        import openswing.seeded_corrector
        import openswing.geometry_tangent
        import openswing.time_integration
        import openswing.sparse_rank
        import openswing.sparse_newton
        assert len(os.listdir('/proc/self/task'))==1,'Preload must leave exactly one thread before fork.'
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
        write(folder/'preload.json',dict(observed_utc=utc(),numerical_work=False,limits=LIMITS,
            wall_seconds=time.monotonic()-started,cpu_seconds=time.process_time()-cpu))


def worker(job,folder):
    stage=folder/'artifacts';stage.mkdir()
    os.environ['TMPDIR']=str(stage)
    strict=adapter.run(ROOT,job)
    adapter.validate_result_contract(job,strict)
    adapter.verify_artifacts(ROOT,strict)
    write(folder/'strict-result.json',strict)
    write(folder/'result.json',apply_reference_acceptance(strict,relative_tolerance=.05))


def launch(directory,plan,job,suite):
    folder=directory/'jobs'/job['id'];folder.mkdir(parents=True,exist_ok=False)
    write(folder/'job.json',job)
    try:preload(folder)
    except BaseException as exc:
        write(folder/'terminal.json',dict(status='preload_error',subprocess_started=False,
            physical_solver_calls=0,observed_utc=utc(),error=repr(exc),limits=LIMITS))
        raise
    sys.stdout.flush();sys.stderr.flush();start=time.monotonic();pid=os.fork()
    if pid==0:
        code=0
        try:
            os.setsid()
            # The parent retains the complete ledger and source pins. The
            # isolated child only needs its selected job, so release inherited
            # inventories before allocating the physical result. Fork keeps
            # the parent's plan intact.
            plan.clear()
            resource.setrlimit(resource.RLIMIT_AS,(LIMITS['address_space_bytes'],)*2)
            resource.setrlimit(resource.RLIMIT_CPU,(LIMITS['cpu_seconds'],)*2)
            with (folder/'stdout.log').open('x') as out,(folder/'stderr.log').open('x') as err:
                os.dup2(out.fileno(),1);os.dup2(err.fileno(),2)
                try:worker(job,folder)
                except BaseException:traceback.print_exc();code=1
                sys.stdout.flush();sys.stderr.flush()
        except BaseException:traceback.print_exc();sys.stderr.flush();code=1
        finally:os._exit(code)
    reaped=0;timed_out=False
    try:
        while not reaped:
            reaped,status,usage=os.wait4(pid,os.WNOHANG)
            if reaped:break
            if time.monotonic()-start>LIMITS['wall_seconds']:
                timed_out=True;os.kill(pid,signal.SIGKILL)
                reaped,status,usage=os.wait4(pid,0);break
            time.sleep(.05)
    finally:
        if not reaped:
            os.kill(pid,signal.SIGKILL);reaped,status,usage=os.wait4(pid,0)
    code=os.waitstatus_to_exitcode(status)
    terminal=dict(observed_utc=utc(),status='timeout' if timed_out else 'process_error' if code else 'computed',
        returncode=code,process_reaped=True,subprocess_started=True,timed_out=timed_out,
        wall_seconds=time.monotonic()-start,cpu_seconds=usage.ru_utime+usage.ru_stime,
        peak_rss_kib=usage.ru_maxrss,limits=LIMITS,sources_unchanged=False)
    # Record the reaped process before any postflight source/result checks.
    write(folder/'terminal.json',terminal)
    terminal['sources_unchanged']=suite.stable_code(ROOT,plan['code_sha256'])
    if not terminal['sources_unchanged']:terminal['status']='source_changed'
    if terminal['status']=='computed':terminal['strict_result_sha256']=digest(folder/'strict-result.json')
    write(folder/'terminal.json',terminal)
    print(json.dumps(dict(job=job['id'],**terminal)),flush=True)
    return terminal


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--speed',type=int,choices=range(1,109))
    parser.add_argument('--nominal',type=int,choices=adapter.GRIDS)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--plan-only',action='store_true')
    group.add_argument('--summary-only',action='store_true')
    args=parser.parse_args()
    directory=args.output_dir.absolute();directory.mkdir(parents=True,exist_ok=True)
    with serial_lock():
        plan,suite=prepare(directory)
        terminal=None
        if not (args.plan_only or args.summary_only):
            job=choose_job(plan,directory,speed=args.speed,nominal=args.nominal)
            if job is not None:terminal=launch(directory,plan,job,suite)
            else:print('All selected jobs already have terminal receipts; no solve repeated.',flush=True)
        report=summarize(directory,plan)
        print(json.dumps(dict(scopes=report['scopes'],new_jobs=terminal is not None)),flush=True)
        if terminal is not None and terminal['status']!='computed':sys.exit(1)


if __name__=='__main__':main()
