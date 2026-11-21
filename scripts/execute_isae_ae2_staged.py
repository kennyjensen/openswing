"""Run one unstarted AE-2 job with metadata outside the numerical deadline.

Uses the original adapter's canonical request preparation and original physical
worker, unchanged. The 25-second child budget covers one cold solve, its fresh
restore and all physical checks. Source validation and final reporting remain
mandatory, but run in the parent. Existing job folders are never restarted.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'scripts'))
from scripts import isae_suite_aeroelastic as adapter
from scripts.recover_isae_ae2_saved import CHECK_NAMES

THREADS = dict(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
              MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
LIMITS = dict(address_space_bytes=512*1024**2, cpu_seconds=15, wall_seconds=25)


def read(path):
    return json.loads(Path(path).read_text())


def collect(job, report, terminal, stable):
    """Same comparison values/gates as the original adapter, with exact checks."""
    if terminal['returncode'] != 0 or terminal['supervisor_timeout']:
        return dict(status='timeout' if terminal['supervisor_timeout'] else 'process_error',
                    reference_match=False)
    assert terminal['process_reaped'] is True and stable is True
    assert tuple(c['name'] for c in report['checks']) == CHECK_NAMES
    assert all(c['passed'] is True for c in report['checks'])
    assert report['operations'] == dict(cold_solves=1, fresh_residuals=1)
    assert report['case'] == job['mesh']
    assert report['kernel_pins'] == {Path(p['path']).name:p['sha256'] for p in job['kernel_pins']}
    checks = adapter._checks(job, report['values'])
    assert all(c['predicted'] is not None for c in checks)
    return dict(id=job['id'], case_id='AE-2', adapter='aeroelastic', status='computed',
        numerical_pass=True, reference_match=all(c['passed'] for c in checks),
        reference_checks=checks, physical_checks=report['checks'], worker_report=report,
        error=None, source_pins_unchanged=True, expected_operations=job['expected_operations'],
        historical_settings_recovered=False, historical_unknowns=job['historical_unknowns'],
        qualifications=job['qualifications'], reference_scope=job['reference_scope'])


def worker(stage):
    assert all(os.environ.get(k) == v for k,v in THREADS.items())
    job = read(stage/'adapter-job.json')
    helper = adapter._load(job['helper'])
    assert helper.ROOT == ROOT
    helper.worker(stage, job['mesh'])


def launch(stage):
    def caps():
        resource.setrlimit(resource.RLIMIT_AS, (LIMITS['address_space_bytes'],)*2)
        resource.setrlimit(resource.RLIMIT_CPU, (LIMITS['cpu_seconds'],)*2)
    start=time.monotonic(); timed_out=False; pid=0
    command=[sys.executable, str(Path(__file__).resolve()), 'worker', '--stage', str(stage)]
    with (stage/'run.log').open('x') as log:
        child=subprocess.Popen(command, cwd=ROOT, env={**os.environ, **THREADS},
            preexec_fn=caps, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while not pid:
                pid,status,usage=os.wait4(child.pid,os.WNOHANG)
                if pid: break
                if time.monotonic()-start > LIMITS['wall_seconds']:
                    timed_out=True;os.killpg(child.pid,signal.SIGKILL)
                    pid,status,usage=os.wait4(child.pid,0);break
                time.sleep(.05)
        finally:
            if not pid:
                os.killpg(child.pid,signal.SIGKILL);pid,status,usage=os.wait4(child.pid,0)
            child.returncode=os.waitstatus_to_exitcode(status)
    terminal=dict(returncode=child.returncode, process_reaped=True,
        supervisor_timeout=timed_out, wall_seconds=time.monotonic()-start,
        cpu_seconds=usage.ru_utime+usage.ru_stime, peak_rss_kib=usage.ru_maxrss,
        command=command, limits=LIMITS, observed_utc=datetime.now(timezone.utc).isoformat())
    adapter._write(stage/'worker-terminal.json',terminal)
    return terminal


def run(directory, name):
    resource.setrlimit(resource.RLIMIT_AS,(LIMITS['address_space_bytes'],)*2)
    start=time.monotonic();script=adapter._pin(__file__)
    spec=importlib.util.spec_from_file_location('original_suite',ROOT/'scripts/run-isae-suite.py')
    suite=importlib.util.module_from_spec(spec);spec.loader.exec_module(suite)
    plan_path=directory/'plan.json';plan=read(plan_path);plan_pin=adapter._pin(plan_path)
    assert plan['execution_policy']['workers']==1
    assert plan['execution_policy']['timeout_seconds']==LIMITS['wall_seconds']
    assert suite.stable_code(ROOT,plan['code_sha256'])
    job=next(j for j in plan['jobs'] if j['id']==name)
    assert job['case_id']=='AE-2' and job['execution_route']=='worker'
    folder=directory/'jobs'/hashlib.sha256(name.encode()).hexdigest()[:20]
    assert not folder.exists(), 'An original job is never restarted.'
    canonical=adapter._canonical(ROOT,job)
    assert canonical==job
    folder.mkdir();stage=folder/'artifacts'/('openswing-isae-suite-aeroelastic-'+name+'-staged')
    stage.mkdir(parents=True)
    suite.write_json(folder/'request.json',dict(job=job,code_sha256=plan['code_sha256']))
    prepared=adapter._prepare_worker(ROOT,job,stage)
    prepared['pins'] += [script, adapter._pin(ROOT/'scripts/recover_isae_ae2_saved.py')]
    adapter._write(stage/'plan.json',prepared)
    adapter._write(stage/'authorization.json',dict(authorized=True,
        plan_sha256=adapter._pin(stage/'plan.json')['sha256'],
        origin='Current staged coordinator: exact original worker; metadata outside numerical deadline.'))
    (stage/'coordinator-source.py').write_bytes(Path(__file__).read_bytes())
    prep_seconds=time.monotonic()-start
    terminal=launch(stage)
    metadata_start=time.monotonic()
    assert adapter._pin(__file__)==script and adapter._pin(plan_path)==plan_pin
    assert suite.stable_code(ROOT,plan['code_sha256'])
    stable=all(adapter._pin(p['path'])==p for p in prepared['pins'])
    assert stable
    physical=stage/'cases'/job['mesh'];report_path=physical/'report.json'
    report=read(report_path) if report_path.exists() else None
    result=collect(job,report,terminal,stable)
    sources=dict(all_pins_checked_before_and_after=True,coordinator=script,
        plan=plan_pin,terminal=adapter._pin(stage/'worker-terminal.json'))
    adapter._write(stage/'sources-verified.json',sources)
    result.update(job_id=name, artifact_directory=str(stage), artifact_root=str(folder/'artifacts'),
        artifact_files=[adapter._pin(p) for p in sorted(stage.rglob('*')) if p.is_file()],
        execution_completed=True,execution_kind='staged_subprocess',subprocess_started=True,
        process_reaped=True,process_exit_code=terminal['returncode'],
        supervisor_seconds=terminal['wall_seconds'],seconds=time.monotonic()-start,
        staged_execution=dict(coordinator=script,terminal=terminal,sources=sources,
            metadata_prepare_seconds=prep_seconds,
            metadata_collect_seconds=time.monotonic()-metadata_start,
            deadline_scope='Unchanged original physical worker; parent metadata excluded.'))
    result=suite.checked_result(job,result)
    suite.write_json(folder/'result.json',result)
    results={}
    for j in plan['jobs']:
        base=directory/'jobs'/hashlib.sha256(j['id'].encode()).hexdigest()[:20]
        if not base.exists():continue
        packet=read(base/'request.json'); prior=read(base/'result.json')
        assert packet==dict(job=j,code_sha256=plan['code_sha256'])
        assert prior['execution_completed'] is True
        assert prior.get('process_reaped') is True or prior.get('subprocess_started') is False
        results[j['id']]=suite.checked_result(j,prior)
    assert not any(k=='openswing' or k.startswith('openswing.') for k in sys.modules)
    summary=suite.report(plan,results,ROOT,time.monotonic()-start)
    summary['execution_batch']=dict(method=__doc__,scheduled_job_ids=[name],
        coordinator=script,limits=LIMITS,parent_physics_imports=0)
    suite.write_json(directory/'report.json',summary)
    (directory/'report.md').write_text(suite.markdown(summary))
    suite.write_json(directory/'progress.json',dict(finished=len(results),planned=len(plan['jobs']),
        active=[],last_staged_job=name))
    print(json.dumps(dict(job=name,status=result['status'],terminal=terminal,
        metadata_prepare_seconds=prep_seconds,metadata_collect_seconds=result['staged_execution']['metadata_collect_seconds'],
        total_terminal_jobs=len(results))),flush=True)


def verify_saved(job, result):
    """Verify staged execution evidence without importing numerical code."""
    assert result['execution_kind']=='staged_subprocess'
    proof=result['staged_execution'];stage=Path(result['artifact_directory'])
    pins=[]
    for item in result['artifact_files']:
        assert adapter._pin(item['path'])==item
        pins.append(item)
    assert adapter._pin(__file__)==proof['coordinator']
    assert (stage/'coordinator-source.py').read_bytes()==Path(__file__).read_bytes()
    assert read(stage/'adapter-job.json')=={k:v for k,v in job.items()
        if k not in ('result','_summary_reference_contract')}
    terminal=read(stage/'worker-terminal.json');sources=read(stage/'sources-verified.json')
    assert terminal==proof['terminal'] and sources==proof['sources']
    assert terminal['limits']==LIMITS and terminal['process_reaped'] is True
    assert terminal['returncode']==result['process_exit_code']==0 and terminal['supervisor_timeout'] is False
    assert terminal['command']==[sys.executable,str(Path(__file__).resolve()),'worker','--stage',str(stage)]
    assert sources['all_pins_checked_before_and_after'] is True
    assert sources['coordinator']==proof['coordinator']
    assert sources['terminal']==adapter._pin(stage/'worker-terminal.json')
    prepared=read(stage/'plan.json')
    for item in prepared['pins']:
        assert adapter._pin(item['path'])==item
        pins.append(item)
    assert read(stage/'authorization.json')['plan_sha256']==adapter._pin(stage/'plan.json')['sha256']
    folder=stage/'cases'/job['mesh'];report=read(folder/'report.json')
    assert report==result['worker_report']
    assert report['request']==adapter._pin(folder/'request.json') and report['result']==adapter._pin(folder/'result.json')
    from scripts.recover_isae_ae2_saved import expected_request
    assert read(folder/'request.json')==expected_request(job)
    assert read(folder/'started.json')['cold_solve_budget']==1
    strict=collect(job,report,terminal,True)
    assert strict['physical_checks']==result['physical_checks']
    assert strict['status']==result['status']=='computed'
    pins.append(proof['coordinator'])
    return pins


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['run','worker'])
    p.add_argument('--directory',type=Path);p.add_argument('--case')
    p.add_argument('--stage',type=Path)
    a=p.parse_args()
    if a.action=='worker':worker(a.stage.resolve())
    else:run(a.directory.resolve(),a.case)
