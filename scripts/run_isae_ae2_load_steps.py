"""Run unchanged AE-2 cold continuations as small, serial load-step jobs.

The existing diagnostic worker supplies the solver and physical checks. This
driver pairs a successful same-mesh control with a failed original condition,
keeps their exact requests, and uses the current 25-second supervisor limit.
Controls and partial states never add native comparison votes.
"""
import argparse
from datetime import datetime, timezone
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
from scripts.recover_isae_ae2_saved import expected_request

LIMITS = dict(address_space_bytes=512*1024**2, soft_cpu_seconds=14,
              hard_cpu_seconds=15, alarm_seconds=25, supervisor_seconds=25)
WORKER = ROOT/'scripts/probe_isae_ae2_cold_stages.py'


def checked(out):
    plan = read(out/'plan.json')
    assert plan['limits'] == LIMITS
    assert all(pin(p['path']) == p for p in plan['pins'])
    return plan


def prepare(out, base, assessment, control_id, candidate_id):
    assert not out.exists()
    prior = read(assessment)
    assert prior['status'] == 'CURRENT_SAVED_DATA_AUDIT_PASS'
    report_pin = pin(base/'report.json')
    assert any(p['path'] == report_pin['path'] and p['sha256'] == report_pin['sha256']
               for p in prior['source_inputs'])
    source_plan = read(base/'plan.json'); report = read(base/'report.json')
    jobs = {j['id']:j for j in report['jobs']}
    control, candidate = jobs[control_id], jobs[candidate_id]
    assert control['result']['status'] == 'computed'
    assert candidate['result']['status'] in ('timeout','process_error')
    assert control['case_id'] == candidate['case_id'] == 'AE-2'
    for key in ('source','mesh','panels','settings','expected_elements'):
        assert control[key] == candidate[key], key
    assert {k:v for k,v in control['condition'].items() if k != 'speed'} == {
        k:v for k,v in candidate['condition'].items() if k != 'speed'}
    assert control['condition']['speed'] != candidate['condition']['speed']
    paths = [Path(__file__), WORKER, assessment, base/'plan.json', base/'report.json',
        ROOT/'scripts/probe_isae_ae2_cold_trace.py',
        ROOT/'scripts/probe_isae_ae2_staged_inverse.py',
        ROOT/'scripts/probe_isae_ae2_inverse_speed.py',
        ROOT/'scripts/recover_isae_ae2_saved.py',
        ROOT/'docs/validation/aswing-authoritative-sources.json']
    for name, digest in source_plan['code_sha256'].items():
        path = ROOT/name
        assert pin(path)['sha256'] == digest
        paths.append(path)
    for item in read(ROOT/'docs/validation/aswing-authoritative-sources.json')['files']:
        if item['id'] in ('isae-part-4','drela-steady'):
            for key, digest in [('local_pdf','sha256'),('local_text','text_sha256')]:
                path = ROOT/item[key]
                assert pin(path)['sha256'] == item[digest]
                paths.append(path)
    cases = []
    for entry in (control, candidate):
        result = entry['result']; job = {k:v for k,v in entry.items() if k != 'result'}
        assert job == next(j for j in source_plan['jobs'] if j['id'] == job['id'])
        assert result['process_reaped'] is True and result['execution_completed'] is True
        if entry is candidate:
            assert result['process_exit_code'] != 0
        requests = list(Path(result['artifact_root']).glob('*/cases/'+job['mesh']+'/request.json'))
        assert len(requests) == 1
        request = requests[0]
        assert read(request) == expected_request(job)
        paths += [request] + [Path(p['path']) for p in job['source_pins']+job['kernel_pins']]
        case = dict(name=job['id'], job=job['id'], mesh=job['mesh'],
                    original_process_result=result, request=str(request),
                    expected_elements=job['expected_elements'], control_case=control_id)
        if entry is control:
            saved = request.with_name('result.json')
            assert read(saved)['converged'] is True and read(saved)['residual'] <= 1e-12
            case['control_result'] = str(saved); paths.append(saved)
        cases.append(case)
    write(out/'plan.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        previous_goal_turn='Progress: accepted original 5-degree/18 m/s fine-grid chain; primary 2069/2200.',
        original_report=str(base/'report.json'), prior_assessment=str(assessment),
        cases=cases, pins=[pin(p) for p in sorted(set(paths))], limits=LIMITS,
        method=__doc__, production_changes=False, primary_votes_added=0,
        acceptance='A complete source-checked chain, exact control parity and independent final verification are required before collector acceptance. No alternate settings or seed are used.'))
    print('Prepared control '+control_id+' and candidate '+candidate_id, flush=True)


def launch(out, name, index):
    assert type(index) is int and index >= 0
    plan = checked(out); case = next(c for c in plan['cases'] if c['name'] == name)
    prior_pins = []
    if 'control_result' not in case:
        controls = [p for p in (out/'cases'/case['control_case']).glob('*/report.json')
                    if read(p)['status'] == 'computed']
        assert len(controls) == 1, 'Same-mesh control must complete first.'
        control = controls[0].parent
        assert read(control/'terminal.json')['returncode'] == 0
        assert read(control/'sources-verified.json')['all_pins_checked_before_and_after']
        assert read(controls[0])['parity']['maximum_coordinate_difference'] == 0
        prior_pins += [pin(control/p) for p in ['result.json','report.json','terminal.json','sources-verified.json']]
    if index:
        previous = out/'cases'/name/f'{index-1:02d}'
        assert read(previous/'terminal.json')['returncode'] == 0
        assert read(previous/'result.json')['continuation_status'] == 'pending'
        assert read(previous/'sources-verified.json')['all_pins_checked_before_and_after']
        prior_pins += [pin(previous/p) for p in ['result.json','terminal.json','sources-verified.json']]
    folder = out/'cases'/name/f'{index:02d}'
    folder.mkdir(parents=True, exist_ok=False)
    write(folder/'started.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        plan=pin(out/'plan.json'), previous_boundary=prior_pins, limits=LIMITS))
    def caps():
        resource.setrlimit(resource.RLIMIT_AS, (LIMITS['address_space_bytes'],)*2)
        resource.setrlimit(resource.RLIMIT_CPU, (LIMITS['hard_cpu_seconds'],)*2)
    command = [sys.executable,str(WORKER),'worker','--output',str(out),
               '--case',name,'--index',str(index)]
    start = time.monotonic(); timeout = False; pid = 0
    with (folder/'stdout.log').open('x') as stdout, (folder/'stderr.log').open('x') as stderr:
        child = subprocess.Popen(command, cwd=ROOT, env={**os.environ,**THREADS},
            preexec_fn=caps, stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            while not pid:
                pid,status,usage = os.wait4(child.pid,os.WNOHANG)
                if pid: break
                if time.monotonic()-start > LIMITS['supervisor_seconds']:
                    timeout=True; os.killpg(child.pid,signal.SIGKILL)
                    pid,status,usage=os.wait4(child.pid,0); break
                time.sleep(.05)
        finally:
            if not pid:
                os.killpg(child.pid,signal.SIGKILL);pid,status,usage=os.wait4(child.pid,0)
            child.returncode=os.waitstatus_to_exitcode(status)
    terminal=dict(case=name,index=index,returncode=child.returncode,process_reaped=True,
        supervisor_timeout=timeout,wall_seconds=time.monotonic()-start,
        cpu_seconds=usage.ru_utime+usage.ru_stime,peak_rss_kib=usage.ru_maxrss,
        finished_utc=datetime.now(timezone.utc).isoformat(),command=command,limits=LIMITS)
    write(folder/'terminal.json',terminal)
    checked(out); assert all(pin(p['path']) == p for p in prior_pins)
    if child.returncode == 0:
        report=read(folder/'report.json')
        if report['status'] == 'computed':
            assert report['fresh_residual'] <= 1e-12
            assert read(folder/'result.json')['residual'] <= 1e-12
    write(folder/'sources-verified.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        plan=pin(out/'plan.json'),terminal=pin(folder/'terminal.json'),
        all_pins_checked_before_and_after=True,previous_boundary=prior_pins))
    print(json.dumps(terminal),flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','launch'])
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--base',type=Path);parser.add_argument('--assessment',type=Path)
    parser.add_argument('--control');parser.add_argument('--candidate')
    parser.add_argument('--case');parser.add_argument('--index',type=int)
    args=parser.parse_args();out=args.output.resolve()
    if args.action=='prepare':
        prepare(out,args.base.resolve(),args.assessment.resolve(),args.control,args.candidate)
    else:launch(out,args.case,args.index)
