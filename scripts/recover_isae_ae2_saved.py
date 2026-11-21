"""Independently verify completed AE-2 states left by timed-out suite wrappers.

Never reruns an equilibrium solve or overwrites the original failed receipt.
Only complete original cold results, with exact original requests and current
source pins, are eligible. Each recheck uses one fresh restored residual.
"""
import argparse
from datetime import datetime, timezone
import hashlib
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
from scripts.probe_isae_ae2_cold_trace import read, write, pin, THREADS

CHECK_NAMES = ('identity', 'restore_no_residual', 'one_fresh_residual',
    'fresh_full_residual', 'node_element_counts', 'cold_state',
    'source_identity_and_no_launch', 'inertia_unavailable', 'source_recovery',
    'force_balance', 'moment_balance', 'clamp_position', 'clamp_frame',
    'sensor_restored_parity', 'sensor_flow_speed', 'sensor_flow_beta',
    'aero_force_total', 'aero_moment_total')


def checked(out):
    p = read(out/'plan.json')
    assert all(pin(v['path']) == v for v in p['pins']), 'Recovery input changed.'
    return p


def expected_request(job):
    return dict(action='solve', mode='mounted', source=Path(job['source']).read_text(),
        panels=job['panels'], condition=job['condition'], numerics=job['settings'],
        operating_constraints=[], strut_mode='bilateral', controller=None)


def prepare(out, snapshot):
    assert not out.exists()
    original = read(snapshot/'report.json'); source_plan = read(snapshot/'plan.json')
    assert all(hashlib.sha256((ROOT/k).read_bytes()).hexdigest() == v
               for k,v in source_plan['code_sha256'].items())
    cases = []; paths = [Path(__file__), snapshot/'report.json', snapshot/'plan.json',
        ROOT/'scripts/probe_isae_ae2_cold_stages.py', ROOT/'scripts/probe_isae_ae2_cold_trace.py',
        ROOT/'scripts/probe_isae_ae2_staged_inverse.py', ROOT/'scripts/probe_isae_ae2_inverse_speed.py']
    paths += [ROOT/k for k in source_plan['code_sha256']]
    excluded = []
    for entry in original['jobs']:
        failed = entry.get('result') or {}
        if failed.get('status') not in ('timeout', 'process_error'): continue
        assert failed['process_reaped'] and failed['execution_completed'] and failed['process_exit_code'] != 0
        job = {k:v for k,v in entry.items() if k != 'result'}
        assert job['case_id'] == 'AE-2' and job['execution_route'] == 'worker'
        candidates = list(Path(failed['artifact_root']).glob('*/cases/'+job['mesh']+'/result.json'))
        if not candidates:
            excluded.append(dict(job=job['id'], reason='No completed cold result exists.')); continue
        assert len(candidates) == 1
        result_path = candidates[0]; request_path = result_path.with_name('request.json')
        saved = read(result_path); request = read(request_path)
        assert saved['converged'] is True and saved['residual'] <= 1e-12
        assert request == expected_request(job)
        started_path = result_path.with_name('started.json')
        assert read(started_path)['cold_solve_budget'] == 1
        stage = result_path.parents[2]
        assert read(stage/'adapter-job.json') == job
        auth = read(stage/'authorization.json')
        assert auth['authorized'] and auth['plan_sha256'] == pin(stage/'plan.json')['sha256']
        original_report = result_path.with_name('report.json')
        cases.append(dict(id=job['id'], job=job, original_failed_result=failed,
            request=str(request_path), result=str(result_path), original_report=str(original_report) if original_report.exists() else None))
        paths += [result_path, request_path, started_path, stage/'adapter-job.json', stage/'plan.json', stage/'authorization.json']
        paths += [Path(v['path']) for v in job['source_pins']+job['kernel_pins']]
        if original_report.exists(): paths.append(original_report)
    assert cases
    write(out/'plan.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        original_snapshot=str(snapshot), cases=cases, excluded=excluded,
        pins=[pin(p) for p in sorted(set(paths))], method=__doc__,
        limits=dict(address_space_bytes=512*1024**2, cpu_seconds=15, supervisor_seconds=25),
        new_cold_solves=0, fresh_residuals_per_case=1,
        qualifications=['Original timeout receipts remain failures.',
            'Successful independent verification may complete the original comparison once; no alternative settings or duplicate votes.',
            'An unverified saved result never earns a comparison pass.']))
    print(json.dumps(dict(prepared=[c['id'] for c in cases], excluded=excluded)), flush=True)


def worker(out, name):
    limits = read(out/'plan.json')['limits']
    resource.setrlimit(resource.RLIMIT_AS, (limits['address_space_bytes'],)*2)
    resource.setrlimit(resource.RLIMIT_CPU, (limits['cpu_seconds'],)*2)
    signal.alarm(limits['supervisor_seconds'])
    assert all(os.environ.get(k) == '1' for k in THREADS)
    # Complete source-file verification belongs to the surrounding transaction:
    # parent checks before spawn and after reap. Keep its filesystem overhead
    # outside the numerical deadline without skipping a single pinned file.
    plan = read(out/'plan.json'); case = next(c for c in plan['cases'] if c['id'] == name)
    for path in (case['request'], case['result']):
        assert pin(path) == next(p for p in plan['pins'] if p['path'] == path)
    request = read(case['request']); saved = read(case['result'])
    assert request == expected_request(case['job'])
    from scripts.probe_isae_ae2_cold_stages import verify
    report = verify(request, saved, dict(expected_elements=case['job']['expected_elements']))
    assert tuple(c['name'] for c in report['checks']) == CHECK_NAMES
    assert all(c['passed'] for c in report['checks']) and report['fresh_residual'] <= 1e-12
    # The checker restores and evaluates once; it never calls equilibrate/dispatch.
    report.update(status='VERIFIED_ORIGINAL_SAVED_EQUILIBRIUM', job_id=name,
        operations=dict(new_cold_solves=0, fresh_residuals=1),
        original_process_outcome=case['original_failed_result'],
        original_result=pin(case['result']), original_request=pin(case['request']),
        verifier=pin(__file__), verifier_helper=pin(ROOT/'scripts/probe_isae_ae2_cold_stages.py'),
        cpu_seconds=time.process_time())
    write(out/name/'report.json', report)
    print(json.dumps(dict(job=name, fresh_residual=report['fresh_residual'], checks=len(report['checks']))), flush=True)


def launch(out, name):
    plan = checked(out); assert any(c['id'] == name for c in plan['cases'])
    folder = out/name; folder.mkdir(exist_ok=False)
    write(folder/'started.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(), new_cold_solves=0))
    start = time.monotonic(); timeout = False; pid = 0
    with (folder/'stdout.log').open('x') as stdout, (folder/'stderr.log').open('x') as stderr:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'worker', '--output', str(out), '--case', name],
            cwd=ROOT, env={**os.environ, **THREADS}, stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            while not pid:
                pid, status, usage = os.wait4(child.pid, os.WNOHANG)
                if pid: break
                if time.monotonic()-start > plan['limits']['supervisor_seconds']:
                    timeout = True; os.killpg(child.pid, signal.SIGKILL)
                    pid, status, usage = os.wait4(child.pid, 0); break
                time.sleep(.05)
        finally:
            if not pid:
                os.killpg(child.pid, signal.SIGKILL); pid, status, usage = os.wait4(child.pid, 0)
            child.returncode = os.waitstatus_to_exitcode(status)
    receipt = dict(job_id=name, returncode=child.returncode, process_reaped=True, supervisor_timeout=timeout,
        wall_seconds=time.monotonic()-start, cpu_seconds=usage.ru_utime+usage.ru_stime,
        peak_rss_kib=usage.ru_maxrss, finished_utc=datetime.now(timezone.utc).isoformat())
    write(folder/'terminal.json', receipt)
    # A successful numerical exit is not accepted until this final source
    # check succeeds. The receipt remains visible if postprocessing fails.
    checked(out)
    write(folder/'sources-verified.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        plan=pin(out/'plan.json'), terminal=pin(folder/'terminal.json'),
        all_pins_checked_before_and_after=True, source_files=len(plan['pins'])))
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare','worker','launch'])
    p.add_argument('--output', type=Path, required=True); p.add_argument('--case')
    p.add_argument('--snapshot', type=Path)
    a = p.parse_args()
    if a.action == 'prepare': prepare(a.output.resolve(), a.snapshot.resolve())
    else: globals()[a.action](a.output.resolve(), a.case)
