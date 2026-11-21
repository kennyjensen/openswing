"""Split AE-2 diagnostics after completed load attempts, preserving the path.

The progress hook saves only the last converged state after the production
solver has rejected an attempt and selected its next increment. It never saves
the rejected trial. Production equations, steps, rank and residual gates stay
unchanged. This experiment does not authorize primary comparison counts.
"""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.trace_isae_ae2_cold_boundaries import checked as parent_checked, LIMITS
from scripts.probe_isae_ae2_cold_trace import read, write, pin, THREADS


def checked(out):
    plan = read(out/'plan.json')
    assert all(pin(p['path']) == p for p in plan['pins'])
    return plan


def prepare(out):
    assert not out.exists()
    parent = ROOT/'artifacts/isae/ae2-beta1-cold-stages-20261110'
    old = parent_checked(parent)
    paths = [Path(p['path']) for p in old['pins']] + [Path(__file__), parent/'plan.json']
    cases = []
    for mesh in ('m80', 'm160'):
        original = next(c for c in old['cases'] if c['name'] == f'AE-2-m15_02-b01-ias016-{mesh}')
        for control in (True, False):
            folder = parent/'cases'/original['name']/('02' if control else '03')
            case = dict(original, name=f'{"control16" if control else "cold16"}-{mesh}',
                        boundary=str(folder/'result.json'))
            if control:
                case['expected_boundary'] = str(folder.parent/'03/result.json')
                paths.append(Path(case['expected_boundary']))
            for name in ('result.json', 'terminal.json', 'sources-verified.json'):
                paths.append(folder/name)
            assert read(folder/'terminal.json')['returncode'] == 0
            assert read(folder/'sources-verified.json')['all_pins_checked_before_and_after']
            cases.append(case)
    original = next(c for c in old['cases'] if c['name'] == 'AE-2-m15_02-b01-ias018-m160')
    folder = parent/'cases'/original['name']/'02'
    assert read(folder/'terminal.json')['returncode'] == 0
    cases.append(dict(original, name='cold18-m160', boundary=str(folder/'result.json')))
    paths += [folder/name for name in ('result.json','terminal.json','sources-verified.json')]
    write(out/'plan.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        cases=cases, pins=[pin(p) for p in sorted(set(paths))], limits=LIMITS,
        method=__doc__, primary_votes_added=0, production_changes=False))


def worker(out, name, index):
    import numpy as np
    from openswing.bridge import dispatch
    from openswing.steady_continuation import capture, ContinuationPending, plain
    from scripts.trace_isae_ae2_cold_boundaries import staged_request
    from scripts.probe_isae_ae2_cold_stages import verify
    plan = read(out/'plan.json'); case = next(c for c in plan['cases'] if c['name'] == name)
    assert all(os.environ.get(k) == '1' for k in THREADS)
    folder = out/'cases'/name/f'{index:02d}'
    previous = read(folder.parent/f'{index-1:02d}/result.json' if index else case['boundary'])
    original = read(case['request']); request = staged_request(original, previous)
    write(folder/'request.json', request)
    start = time.monotonic(); first_rejections = previous['checkpoint']['rejected_load_attempts']
    events = []; yielded = []

    def progress(stage, current, total):
        if stage != 'static_load' or current == 0:
            return
        frame = sys._getframe().f_back
        while frame and not (frame.f_code.co_name == 'equilibrate' and
                             frame.f_code.co_filename == str(ROOT/'openswing/structured_static.py')):
            frame = frame.f_back
        assert frame is not None
        local = frame.f_locals.copy(); del frame
        net = local['net']; records = net.continuation_diagnostics
        events.append(dict(target=current, reached=local['reached'],
                           rejected_attempts=local['rejected_attempts']))
        if local['rejected_attempts'] == first_rejections:
            return
        assert local['rejected_attempts'] == first_rejections+1 and len(records) == 2
        assert not records[0]['accepted'] and 'residual' in records[0]
        assert not records[1]['accepted'] and 'residual' not in records[1]
        assert local['reached'] == previous['checkpoint']['load_fraction']
        # The failed trial has already been discarded by the original solver.
        assert np.array_equal(local['x'], previous['checkpoint']['coordinates'])
        packet = capture(net, local['x'], local['ctx'], local['reached'], local['increment'],
                         local['steps'], local['rejected_attempts'])
        yielded.append(dict(next_target=current, next_increment=local['increment'],
                            previous_attempt=plain(records[0])))
        records.pop()  # Do not report a new attempt that has not begun.
        raise ContinuationPending(packet)

    result = dispatch(request, progress=progress)
    write(folder/'result.json', result)
    if result['continuation_status'] == 'complete':
        report = verify(original, result, case)
        assert result['residual'] <= 1e-12 and report['fresh_residual'] <= 1e-12
    else:
        p = result['checkpoint']; assert p['physical_residual'] <= 1e-12
        report = dict(status='pending', load_fraction=p['load_fraction'],
            boundary_residual=p['physical_residual'], primary_votes_added=0)
        if 'expected_boundary' in case and not yielded:
            expected = read(case['expected_boundary'])['checkpoint']
            difference = float(np.max(abs(np.asarray(p['coordinates'])-expected['coordinates'])))
            assert difference <= 1e-11
            for key in ('context','load_fraction','next_increment','accepted_load_steps','rejected_load_attempts','hinge_charts'):
                assert p[key] == expected[key], key
            report.update(status='control_pass', maximum_coordinate_difference=difference)
    report.update(events=events, rejected_boundary=yielded, result=pin(folder/'result.json'),
        original_request=pin(case['request']), production_changes=False,
        wall_seconds=time.monotonic()-start, cpu_seconds=time.process_time())
    write(folder/'report.json', report)


def launch(out, name, index):
    plan = checked(out); case = next(c for c in plan['cases'] if c['name'] == name)
    if 'expected_boundary' not in case:
        control = out/'cases'/('control16-'+name.rsplit('-',1)[1])
        assert any(read(p)['status'] == 'control_pass' and
                   read(p.parent/'terminal.json')['returncode'] == 0 and
                   read(p.parent/'sources-verified.json')['all_pins_checked_before_and_after']
                   for p in control.glob('*/report.json'))
    previous_pins = []
    if index:
        prior = out/'cases'/name/f'{index-1:02d}'
        assert read(prior/'terminal.json')['returncode'] == 0
        assert read(prior/'sources-verified.json')['all_pins_checked_before_and_after']
        assert read(prior/'report.json')['status'] == 'pending'
        assert read(prior/'result.json')['continuation_status'] == 'pending'
        previous_pins = [pin(prior/n) for n in ('result.json','terminal.json','sources-verified.json')]
    folder = out/'cases'/name/f'{index:02d}'; folder.mkdir(parents=True, exist_ok=False)
    write(folder/'started.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        plan=pin(out/'plan.json'), previous_boundary=previous_pins, limits=LIMITS))
    def caps():
        resource.setrlimit(resource.RLIMIT_AS, (LIMITS['address_space_bytes'],)*2)
        resource.setrlimit(resource.RLIMIT_CPU, (LIMITS['cpu_seconds'],)*2)
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
        finished_utc=datetime.now(timezone.utc).isoformat(),command=command,limits=LIMITS)
    write(folder/'terminal.json', terminal)
    checked(out); assert all(pin(p['path']) == p for p in previous_pins)
    write(folder/'sources-verified.json', dict(all_pins_checked_before_and_after=True,
        plan=pin(out/'plan.json'),terminal=pin(folder/'terminal.json'),previous_boundary=previous_pins))
    report = read(folder/'report.json') if (folder/'report.json').exists() else {}
    print(dict(**terminal,status=report.get('status'),load_fraction=report.get('load_fraction'),
               maximum_coordinate_difference=report.get('maximum_coordinate_difference')),flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','worker','launch']); p.add_argument('--output',type=Path,required=True)
    p.add_argument('--case'); p.add_argument('--index',type=int)
    a=p.parse_args(); out=a.output.resolve()
    if a.action == 'prepare': prepare(out)
    else: globals()[a.action](out,a.case,a.index)
