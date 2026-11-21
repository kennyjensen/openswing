"""Trace unchanged AE-2 beta=1 cold solves at accepted load boundaries.

One serial child advances one production continuation boundary. Two completed
15 m/s controls must reproduce the original full coordinates before candidates
on their respective meshes can start. No warm guesses, altered equations or
relaxed gates are introduced. Partial results never earn native comparisons.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import faulthandler
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
from scripts.recover_isae_ae2_saved import expected_request
from scripts.probe_isae_ae2_cold_trace import read, write, pin, THREADS

LIMITS = dict(address_space_bytes=512*1024**2, cpu_seconds=15, wall_seconds=25)
CONTROLS = ['AE-2-m15_02-b01-ias015-m80', 'AE-2-m15_02-b01-ias015-m160']
CANDIDATES = ['AE-2-m15_02-b01-ias016-m80', 'AE-2-m15_02-b01-ias016-m160',
              'AE-2-m15_02-b01-ias018-m160']


def checked(out):
    plan = read(out/'plan.json')
    assert all(pin(p['path']) == p for p in plan['pins']), 'Trace input changed.'
    return plan


def prepare(out, base, assessment):
    assert not out.exists()
    prior = read(assessment)
    assert prior['status'] == 'CURRENT_SAVED_DATA_AUDIT_PASS'
    assert any(p['path'] == str(base/'report.json') and
               p['sha256'] == pin(base/'report.json')['sha256'] for p in prior['source_inputs'])
    report = read(base/'report.json'); source_plan = read(base/'plan.json')
    paths = [Path(__file__), assessment, base/'report.json', base/'plan.json',
        ROOT/'scripts/probe_isae_ae2_cold_stages.py',
        ROOT/'scripts/probe_isae_ae2_cold_trace.py',
        ROOT/'scripts/probe_isae_ae2_staged_inverse.py',
        ROOT/'scripts/probe_isae_ae2_inverse_speed.py',
        ROOT/'scripts/recover_isae_ae2_saved.py',
        ROOT/'docs/validation/aswing-authoritative-sources.json']
    for path, digest in source_plan['code_sha256'].items():
        assert pin(ROOT/path)['sha256'] == digest
        paths.append(ROOT/path)
    references = read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    for item in references['files']:
        if item['id'] in ('isae-part-4', 'drela-steady'):
            for path, digest in [(item['local_pdf'], item['sha256']),
                                 (item['local_text'], item['text_sha256'])]:
                assert pin(ROOT/path)['sha256'] == digest
                paths.append(ROOT/path)
    cases = []
    for name in CONTROLS+CANDIDATES:
        entry = next(j for j in report['jobs'] if j['id'] == name)
        result = entry['result']; job = {k:v for k,v in entry.items() if k != 'result'}
        assert job == next(j for j in source_plan['jobs'] if j['id'] == name)
        control = name in CONTROLS
        assert result['process_reaped']
        assert result['status'] == 'computed' if control else result['status'] in ('timeout','process_error')
        folder = Path(result['artifact_directory'])/'cases'/job['mesh']
        request = folder/'request.json'
        assert read(request) == expected_request(job)
        paths += [request] + [Path(p['path']) for p in job['source_pins']+job['kernel_pins']]
        case = dict(name=name, job=job, prior_status=result['status'],
            original_process_result=result, request=str(request),
            expected_elements=job['expected_elements'],
            control_case=next(c for c in CONTROLS if c.endswith('-'+job['mesh'])))
        if control:
            case['control_result'] = str(folder/'result.json')
            assert read(case['control_result'])['residual'] <= 1e-12
            paths.append(Path(case['control_result']))
        cases.append(case)
    write(out/'plan.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        previous_goal_turn='progress: primary 920/2200, all finite negative-coupling beta=1 rows attempted',
        cases=cases, pins=[pin(p) for p in sorted(set(paths))], limits=LIMITS,
        method=__doc__, production_changes=False,
        primary_acceptance='No count change without a separate audit of the complete cold chain and original comparison gates. Partial states and control repeats add no votes.'))
    print(json.dumps(dict(prepared=[c['name'] for c in cases])), flush=True)


def staged_request(original, previous=None):
    assert not original.get('initial_state') and 'continuation' not in original
    request = deepcopy(original)
    options = dict(max_load_steps=1)
    if previous is not None:
        assert previous['continuation_status'] == 'pending'
        options['checkpoint'] = previous['checkpoint']
    request['continuation'] = options
    assert {k:v for k,v in request.items() if k != 'continuation'} == original
    return request


def worker(out, name, index):
    plan = read(out/'plan.json'); case = next(c for c in plan['cases'] if c['name'] == name)
    assert all(os.environ.get(k) == '1' for k in THREADS)
    folder = out/'cases'/name/f'{index:02d}'
    original = read(case['request']); assert original == expected_request(case['job'])
    previous = None
    if index:
        prior = folder.parent/f'{index-1:02d}'
        assert read(prior/'terminal.json')['returncode'] == 0
        assert read(prior/'sources-verified.json')['all_pins_checked_before_and_after']
        previous = read(prior/'result.json')
    request = staged_request(original, previous); write(folder/'request.json', request)
    with (folder/'signal-stack.log').open('x') as stack:
        faulthandler.register(signal.SIGXCPU, file=stack, all_threads=False)
        signal.alarm(LIMITS['wall_seconds'])
        from openswing.bridge import dispatch
        from openswing.steady_continuation import plain
        start = time.monotonic(); last = 0.; seen = 0; captured = -1
        with (folder/'progress.jsonl').open('x') as events:
            def progress(stage, current, total):
                nonlocal last, seen, captured
                now = time.monotonic()
                if stage != 'static_load' and now-last < .2:
                    return
                frame = sys._getframe().f_back; net = None; state = None
                while frame:
                    if (frame.f_code.co_name == 'equilibrate' and
                        frame.f_code.co_filename == str(ROOT/'openswing/structured_static.py')):
                        net = frame.f_locals.get('net'); state = frame.f_locals.get('state'); break
                    frame = frame.f_back
                del frame
                event = dict(wall_seconds=now-start, cpu_seconds=time.process_time(),
                    stage=stage, current=current, total=total)
                if net is not None:
                    records = getattr(net, 'structured_iterations', [])
                    begin = max(0, seen-1)
                    event.update(nfev=net.nfev, iteration_start=begin,
                        iterations=records[begin:], loads=getattr(net,'continuation_diagnostics',[]))
                    seen = len(records)
                    if state is not None and records and captured != seen:
                        write(folder/'latest-iterate.json', plain(dict(
                            request=pin(case['request']), coordinates=state,
                            load_fraction=records[-1]['load_fraction'], iteration_index=seen-1,
                            observation_only=True, accepted_equilibrium=False)))
                        captured = seen
                events.write(json.dumps(plain(event), allow_nan=False)+'\n'); events.flush(); last = now
            result = dispatch(request, progress=progress)
        write(folder/'result.json', result)
        if result['continuation_status'] == 'complete':
            from scripts.probe_isae_ae2_cold_stages import verify
            report = verify(original, result, case)
            assert result['residual'] <= 1e-12 and report['fresh_residual'] <= 1e-12
        else:
            assert result['checkpoint']['physical_residual'] <= 1e-12
            report = dict(status='pending', accepted=False, load_fraction=result['load_fraction'],
                boundary_residual=result['checkpoint']['physical_residual'], primary_votes_added=0)
        report.update(wall_seconds=time.monotonic()-start, cpu_seconds=time.process_time(),
            original_request=pin(case['request']), result=pin(folder/'result.json'),
            canonical_inputs_unchanged=True, full_residual_gate=1e-12)
        write(folder/'report.json', report)
        print(json.dumps(dict(case=name,index=index,**report)), flush=True)


def launch(out, name, index):
    plan = checked(out); case = next(c for c in plan['cases'] if c['name'] == name)
    if 'control_result' not in case:
        controls = list((out/'cases'/case['control_case']).glob('*/report.json'))
        successful = [p for p in controls if read(p)['status'] == 'computed']
        assert len(successful) == 1, 'Same-mesh control must pass first.'
        control = successful[0].parent
        assert read(control/'terminal.json')['returncode'] == 0
        assert read(control/'sources-verified.json')['all_pins_checked_before_and_after']
    chain_pins = []
    if index:
        prior = out/'cases'/name/f'{index-1:02d}'
        assert read(prior/'terminal.json')['returncode'] == 0
        assert read(prior/'result.json')['continuation_status'] == 'pending'
        chain_pins = [pin(prior/n) for n in ['result.json','terminal.json','sources-verified.json']]
    folder = out/'cases'/name/f'{index:02d}'; folder.mkdir(parents=True, exist_ok=False)
    write(folder/'started.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        plan=pin(out/'plan.json'), previous_boundary=chain_pins, limits=LIMITS))
    def caps():
        resource.setrlimit(resource.RLIMIT_AS, (LIMITS['address_space_bytes'],)*2)
        resource.setrlimit(resource.RLIMIT_CPU, (12,LIMITS['cpu_seconds']))
    start = time.monotonic(); timeout = False; pid = 0
    command = [sys.executable,str(Path(__file__).resolve()),'worker','--output',str(out),
               '--case',name,'--index',str(index)]
    with (folder/'stdout.log').open('x') as stdout, (folder/'stderr.log').open('x') as stderr:
        child = subprocess.Popen(command, cwd=ROOT, env={**os.environ,**THREADS},
            preexec_fn=caps, stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            while not pid:
                pid,status,usage = os.wait4(child.pid, os.WNOHANG)
                if pid: break
                if time.monotonic()-start > LIMITS['wall_seconds']:
                    timeout = True; os.killpg(child.pid,signal.SIGKILL)
                    pid,status,usage = os.wait4(child.pid,0); break
                time.sleep(.05)
        finally:
            if not pid:
                os.killpg(child.pid,signal.SIGKILL); pid,status,usage=os.wait4(child.pid,0)
            child.returncode = os.waitstatus_to_exitcode(status)
    terminal = dict(case=name,index=index,returncode=child.returncode,process_reaped=True,
        supervisor_timeout=timeout,wall_seconds=time.monotonic()-start,
        cpu_seconds=usage.ru_utime+usage.ru_stime,peak_rss_kib=usage.ru_maxrss,
        finished_utc=datetime.now(timezone.utc).isoformat(),command=command,limits=LIMITS,
        soft_cpu_trace_signal_seconds=12)
    write(folder/'terminal.json',terminal)
    checked(out); assert all(pin(p['path']) == p for p in chain_pins)
    write(folder/'sources-verified.json',dict(all_pins_checked_before_and_after=True,
        observed_utc=datetime.now(timezone.utc).isoformat(),plan=pin(out/'plan.json'),
        terminal=pin(folder/'terminal.json'),previous_boundary=chain_pins))
    print(json.dumps(terminal),flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','worker','launch']);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--base',type=Path);p.add_argument('--assessment',type=Path)
    p.add_argument('--case');p.add_argument('--index',type=int)
    a=p.parse_args();out=a.output.resolve()
    if a.action == 'prepare':prepare(out,a.base.resolve(),a.assessment.resolve())
    else:globals()[a.action](out,a.case,a.index)
