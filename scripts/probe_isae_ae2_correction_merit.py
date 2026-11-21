"""Test correction-norm globalization on AE-2 without editing production.

Only the merit evaluated during Newton backtracking is changed. All original
equations, derivatives, rank checks, geometry bounds, load stepping and final
physical acceptance remain. This is an explicitly separate numerical variant.
"""
import argparse
import ast
from copy import deepcopy
from datetime import datetime, timezone
import faulthandler
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


def checked(out):
    p = read(out/'plan.json')
    assert all(pin(x['path']) == x for x in p['pins'])
    return p


def prepare(out):
    assert not out.exists()
    parent = ROOT/'artifacts/isae/ae2-cold-stages-20261110'
    old = checked(parent)
    source = (ROOT/'openswing/structured_static.py').read_text()
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'equilibrate')
    variant = ast.get_source_segment(source, node)
    replacements = [
        ('                if net.hinges:\n                    merit = float(delta@delta)\n',
         '                merit = float(delta@delta)\n                if net.hinges:\n'),
        ('                        if net.hinges:\n                            if factorization is not None:\n',
         '                        if True:  # diagnostic correction-norm merit\n                            if factorization is not None:\n')]
    for before, after in replacements:
        assert variant.count(before) == 1
        variant = variant.replace(before, after)
    out.mkdir(parents=True); (out/'equilibrate_variant.py').write_text(variant+'\n')
    cases = []
    paths = [Path(__file__), ROOT/'scripts/probe_isae_ae2_cold_stages.py', parent/'plan.json',
             out/'equilibrate_variant.py', ROOT/'artifacts/isae/ae2-newton-sections-20261110/report.json']
    paths += [Path(p['path']) for p in old['pins']]
    for name, stage in [('control19-m80', '02'), ('cold20-m80', '03')]:
        c = next(c for c in old['cases'] if c['name'] == name)
        boundary = parent/'cases'/name/stage/'result.json'
        assert read(parent/'cases'/name/stage/'terminal.json')['returncode'] == 0
        assert read(boundary)['continuation_status'] == 'pending'
        cases.append(dict(c, boundary=str(boundary)))
        paths += [boundary, parent/'cases'/name/stage/'terminal.json']
    write(out/'plan.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        cases=cases, pins=[pin(p) for p in sorted(set(paths))], limits=old['limits'],
        replacements=[dict(before=b, after=a) for b,a in replacements],
        primary_votes_added=0, production_changed=False, method=__doc__,
        qualifications=['Variant exists only in the diagnostic child process.',
            'Final control must pass physical and prior-result checks before the difficult case starts.',
            'Original checkpoints are starting states, not complete solves or validation votes.',
            'Any new unfinished checkpoint belongs only to this disclosed variant.',
            'The merit rule is not claimed to be a documented ASWING default.']))


def worker(out, name):
    limits = read(out/'plan.json')['limits']
    resource.setrlimit(resource.RLIMIT_AS, (limits['address_space_bytes'],)*2)
    resource.setrlimit(resource.RLIMIT_CPU, (limits['soft_cpu_seconds'], limits['hard_cpu_seconds']))
    plan = checked(out); case = next(c for c in plan['cases'] if c['name'] == name)
    assert all(os.environ.get(k) == '1' for k in THREADS)
    folder = out/name
    stack = (folder/'signal-stack.log').open('x')
    faulthandler.register(signal.SIGXCPU, file=stack, all_threads=False, chain=False)
    faulthandler.register(signal.SIGALRM, file=stack, all_threads=False, chain=True)
    signal.alarm(limits['alarm_seconds'])
    from openswing import structured_static
    from openswing.bridge import dispatch
    from openswing.steady_continuation import plain
    from scripts.probe_isae_ae2_cold_stages import verify
    namespace = dict(vars(structured_static))
    exec(compile((out/'equilibrate_variant.py').read_text(), str(out/'equilibrate_variant.py'), 'exec'), namespace)
    structured_static.equilibrate = namespace['equilibrate']
    request = deepcopy(read(case['request'])); original = deepcopy(request)
    request['continuation'] = dict(checkpoint=read(case['boundary'])['checkpoint'], max_load_steps=1)
    write(folder/'request.json', request)
    start = time.monotonic(); last = [0.]
    with (folder/'progress.jsonl').open('x') as events:
        def progress(stage, current, total):
            now = time.monotonic()
            if stage != 'static_load' and now-last[0] < .2: return
            frame = sys._getframe().f_back; net = None
            while frame:
                for k in ('net','network'):
                    obj = frame.f_locals.get(k)
                    if type(obj).__name__ == 'SourceCoupledNetwork': net = obj; break
                if net is not None: break
                frame = frame.f_back
            del frame
            record = dict(wall_seconds=now-start, cpu_seconds=time.process_time(), stage=stage, current=current, total=total)
            if net is not None:
                record.update(nfev=net.nfev, iterations=getattr(net,'structured_iterations',[])[-2:], loads=getattr(net,'continuation_diagnostics',[])[-2:])
            events.write(json.dumps(plain(record), allow_nan=False)+'\n'); events.flush(); last[0] = now
        result = dispatch(request, progress=progress)
    result['diagnostic_numerics'] = 'correction-norm merit for nonhinged Newton backtracking'
    write(folder/'result.json', result)
    report = verify(original, result, case) if result['continuation_status'] == 'complete' else dict(status='pending', accepted=False, load_fraction=result['load_fraction'], primary_votes_added=0)
    checked(out)
    report.update(cpu_seconds=time.process_time(), wall_seconds=time.monotonic()-start,
        primary_votes_added=0, production_changed=False, diagnostic_numerics=result['diagnostic_numerics'])
    write(folder/'report.json', report)
    print(json.dumps(dict(case=name, status=report['status'], checks=len(report.get('checks',[])))), flush=True)


def launch(out, name):
    plan = checked(out); assert any(c['name'] == name for c in plan['cases'])
    if name != 'control19-m80':
        assert read(out/'control19-m80/terminal.json')['returncode'] == 0
        assert read(out/'control19-m80/report.json')['status'] == 'computed'
    folder = out/name; folder.mkdir(exist_ok=False)
    write(folder/'started.json', dict(observed_utc=datetime.now(timezone.utc).isoformat()))
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
    receipt = dict(case=name, returncode=child.returncode, process_reaped=True, supervisor_timeout=timeout,
        wall_seconds=time.monotonic()-start, cpu_seconds=usage.ru_utime+usage.ru_stime,
        peak_rss_kib=usage.ru_maxrss, finished_utc=datetime.now(timezone.utc).isoformat())
    write(folder/'terminal.json', receipt); print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare','worker','launch'])
    p.add_argument('--output', type=Path, required=True); p.add_argument('--case')
    a = p.parse_args()
    if a.action == 'prepare': prepare(a.output.resolve())
    else: globals()[a.action](a.output.resolve(), a.case)
