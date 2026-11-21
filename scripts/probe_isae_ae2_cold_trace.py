"""Observe unchanged AE-2 cold solves in bounded, individually reaped children.

Only the existing progress argument is added to dispatch. Original helper input,
solver defaults and all final physical checks remain intact. These fresh attempts
are diagnostic and never replace the original suite outcomes.
"""
import argparse
import faulthandler
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
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
THREADS = {k: '1' for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS',
                           'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')}


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def pin(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def checked(out):
    plan = read(out/'plan.json')
    assert all(pin(p['path']) == p for p in plan['pins']), 'Pinned input changed.'
    return plan


def prepare(out):
    from scripts import isae_suite_aeroelastic as adapter
    assert not out.exists()
    parent = ROOT/'artifacts/isae/ae2-beta5-sweeps-current-20261110'
    source_plan = read(parent/'plan.json')
    prior = {j['id']: j for j in read(parent/'report.json')['jobs']}
    choices = [('control19-m80', 19, 80), ('cold18-m160', 18, 160), ('cold20-m80', 20, 80)]
    cases = []
    paths = [Path(__file__), parent/'plan.json', parent/'report.json',
             ROOT/'docs/validation/aswing-authoritative-sources.json']
    paths += [ROOT/k for k in source_plan['code_sha256']]
    for name, speed, mesh in choices:
        jid = f'AE-2-m15_02-b05-ias{speed:03d}-m{mesh}'
        record = prior[jid]
        job = next(j for j in source_plan['jobs'] if j['id'] == jid)
        assert record['result']['process_reaped']
        assert record['result']['status'] == ('computed' if name.startswith('control') else 'process_error')
        stage = out/'cases'/name
        adapter._prepare_worker(ROOT, job, stage)
        paths += [Path(p['path']) for p in job['source_pins']]
        paths += [stage/'plan.json', stage/'authorization.json', stage/'adapter-job.json',
                  stage/'cases'/job['mesh']/'request.json']
        cases.append(dict(name=name, job=jid, mesh=job['mesh'],
                          prior_status=record['result']['status'],
                          prior_values=record['result'].get('worker_report', {}).get('values'),
                          prior_result=record['result'].get('artifact_directory')))
    catalog = read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    for item in catalog['files']:
        if item['id'] not in ('drela-steady', 'isae-part-4'):
            continue
        for key, digest in [('local_pdf', 'sha256'), ('local_text', 'text_sha256')]:
            p = ROOT/item[key]
            assert pin(p)['sha256'] == item[digest]
            paths.append(p)
    write(out/'plan.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        cases=cases, pins=[pin(p) for p in sorted(set(paths))], primary_votes_added=0,
        limits=dict(address_space_bytes=512*1024**2, soft_cpu_seconds=14,
                    hard_cpu_seconds=15, alarm_seconds=25, supervisor_seconds=30),
        method=__doc__, previous_goal_turn='progress: 134 new original fixed-speed attempts, full beta5 sweeps audited',
        current_goal_turn='progress: capture live load/iteration evidence from unchanged bounded solves',
        qualifications=['New diagnostic attempts; old outcomes remain intact.',
            'SIGXCPU at 14 CPU seconds writes the Python stack; hard CPU limit remains 15.',
            'Progress observation can add overhead; no timing speedup is claimed.',
            'No source, setting, branch guess or acceptance threshold changes.']))
    print('Prepared one parity control and two failed-case diagnostics.')


def worker(out, name):
    limits = read(out/'plan.json')['limits']
    resource.setrlimit(resource.RLIMIT_AS, (limits['address_space_bytes'],)*2)
    resource.setrlimit(resource.RLIMIT_CPU, (limits['soft_cpu_seconds'], limits['hard_cpu_seconds']))
    plan = checked(out)
    assert all(os.environ.get(k) == '1' for k in THREADS)
    case = next(c for c in plan['cases'] if c['name'] == name)
    stage = out/'cases'/name
    stack = (stage/'signal-stack.log').open('x')
    faulthandler.register(signal.SIGXCPU, file=stack, all_threads=False, chain=False)
    faulthandler.register(signal.SIGALRM, file=stack, all_threads=False, chain=True)
    signal.alarm(limits['alarm_seconds'])
    events = (stage/'progress.jsonl').open('x')
    start = time.monotonic()
    last = [0., None]
    from openswing import bridge
    from openswing.steady_continuation import plain
    original = bridge.dispatch

    def observe(stage_name, current, total):
        now = time.monotonic()
        if stage_name != 'static_load' and now-last[0] < .2:
            return
        frame = sys._getframe().f_back
        net, stack_names = None, []
        while frame is not None:
            stack_names.append(frame.f_code.co_name)
            for key in ('net', 'network'):
                obj = frame.f_locals.get(key)
                if type(obj).__name__ == 'SourceCoupledNetwork':
                    net = obj
                    break
            if net is not None:
                break
            frame = frame.f_back
        del frame
        record = dict(wall_seconds=now-start, cpu_seconds=time.process_time(),
            stage=stage_name, current=current, total=total, stack=stack_names)
        if net is not None:
            record.update(nfev=net.nfev,
                iterations=getattr(net, 'structured_iterations', [])[-2:],
                loads=getattr(net, 'continuation_diagnostics', [])[-2:])
            last[1] = net
        events.write(json.dumps(plain(record), allow_nan=False)+'\n')
        events.flush()
        last[0] = now

    def dispatch(request, progress=None):
        assert progress is None
        return original(request, progress=observe)

    bridge.dispatch = dispatch
    spec = importlib.util.spec_from_file_location('unchanged_ae2_worker', ROOT/'scripts/verify-source-coupled-integration.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    try:
        helper.worker(stage, case['mesh'])
    finally:
        bridge.dispatch = original
        if last[1] is not None:
            net = last[1]
            write(stage/'iteration-summary.json', plain(dict(nfev=net.nfev,
                iterations=getattr(net, 'structured_iterations', []),
                loads=getattr(net, 'continuation_diagnostics', []))))
        events.close()
    report = read(stage/'cases'/case['mesh']/'report.json')
    assert all(c['passed'] for c in report['checks'])
    parity = None
    if name.startswith('control'):
        before, after = case['prior_values'], report['values']
        parity = {k: abs(after[k]-v) for k, v in before.items()}
        assert all(v <= 1e-12 for v in parity.values()), parity
    checked(out)
    write(stage/'diagnostic.json', dict(status='computed', physical_checks=len(report['checks']),
        prior_status=case['prior_status'], primary_votes_added=0, parity=parity,
        wall_seconds=time.monotonic()-start, cpu_seconds=time.process_time(),
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
    print(json.dumps(read(stage/'diagnostic.json')), flush=True)


def launch(out, name):
    plan = checked(out)
    assert name in [c['name'] for c in plan['cases']]
    if not name.startswith('control'):
        assert read(out/'cases/control19-m80/diagnostic.json')['status'] == 'computed'
    stage = out/'cases'/name
    # A started receipt prevents retry even if a child dies before writing output.
    with (stage/'started.json').open('x') as f:
        json.dump(dict(started_utc=datetime.now(timezone.utc).isoformat()), f)
    begin = time.monotonic()
    timeout = False
    with (stage/'stdout.log').open('x') as stdout, (stage/'stderr.log').open('x') as stderr:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'worker',
            '--output', str(out), '--case', name], cwd=ROOT, env={**os.environ, **THREADS},
            stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            while True:
                pid, status, usage = os.wait4(child.pid, os.WNOHANG)
                if pid:
                    break
                if time.monotonic()-begin > plan['limits']['supervisor_seconds']:
                    timeout = True
                    os.killpg(child.pid, signal.SIGKILL)
                    pid, status, usage = os.wait4(child.pid, 0)
                    break
                time.sleep(.05)
        finally:
            if not locals().get('pid'):
                os.killpg(child.pid, signal.SIGKILL)
                pid, status, usage = os.wait4(child.pid, 0)
            child.returncode = os.waitstatus_to_exitcode(status)
    receipt = dict(case=name, returncode=child.returncode, process_reaped=True,
        supervisor_timeout=timeout, wall_seconds=time.monotonic()-begin,
        cpu_seconds=usage.ru_utime+usage.ru_stime, peak_rss_kib=usage.ru_maxrss,
        finished_utc=datetime.now(timezone.utc).isoformat(), primary_votes_added=0)
    write(stage/'terminal.json', receipt)
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'launch', 'worker'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.output.resolve())
    elif args.action == 'launch':
        launch(args.output.resolve(), args.case)
    else:
        worker(args.output.resolve(), args.case)
