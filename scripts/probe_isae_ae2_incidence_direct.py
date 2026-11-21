"""AE-2 incidence diagnostic with the existing complete geometry tangent.

Only the Jacobian assembly option changes, in this child process. Production
Newton, line search, residual, final rank check and result recovery are reused.
Every state still needs a separate unmodified physical verification. This adds
no primary reference votes and does not change any production source/default.
"""
import argparse
from contextlib import contextmanager
from copy import deepcopy
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
from scripts import probe_isae_ae2_incidence as original
from scripts.probe_isae_ae2_cold_trace import read, write, pin, THREADS

LIMITS = original.LIMITS
checked = original.checked


def prepare(out):
    assert not out.exists()
    parent = ROOT/'artifacts/isae/ae2-incidence-trace-20261110'
    tangent = ROOT/'artifacts/isae/ae2-incidence-tangent-20261110'
    from scripts.probe_isae_ae2_incidence_tangent import checked as tangent_checked
    old = checked(parent); comparison = tangent_checked(tangent)
    assessment = read(tangent/'assessment.json')
    assert assessment['status'] == 'PASS'
    assert assessment['maximum_scaled_column_difference'] <= comparison['maximum_scaled_column_difference']
    assert assessment['relative_direction_difference'] <= comparison['maximum_relative_direction_difference']
    for report in assessment['reports'].values():
        assert all(pin(report[k]['path']) == report[k] for k in ('matrix', 'state'))
    plan = deepcopy(old)
    paths = [Path(p['path']) for p in old['pins']+comparison['pins']]
    paths += [Path(__file__), parent/'plan.json', tangent/'plan.json', tangent/'assessment.json']
    catalog = read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    for ref in catalog['files']:
        if ref['id'] == 'drela-steady':
            for kind, checksum in (('pdf', 'sha256'), ('text', 'text_sha256')):
                path = ROOT/ref['local_'+kind]
                assert pin(path)['sha256'] == ref[checksum]
                paths.append(path)
    plan.update(observed_utc=datetime.now(timezone.utc).isoformat(), method=__doc__,
        pins=[pin(p) for p in sorted(set(paths))],
        tangent_comparison=pin(tangent/'assessment.json'),
        original_beta2_failure=pin(parent/'beta02/solve/terminal.json'))
    plan['qualifications'] += [
        'Existing complete geometry chain rule is explicitly enabled for every tangent; physical residuals are unchanged.',
        'Assembly choice is isolated to the diagnostic child; original cold and failed warm executions are retained.',
        'Final acceptance uses a fresh complete tangent and the unchanged rank gate.',
        'The first step repeats the original verified beta1 state as a control.']
    write(out/'plan.json', plan)
    print('Prepared complete-tangent diagnostic; no solver started.', flush=True)


@contextmanager
def complete_geometry(events):
    from openswing.source_coupled import SourceCoupledNetwork
    cls = SourceCoupledNetwork
    owned = 'jacobian' in cls.__dict__
    native = cls.jacobian

    def jacobian(n, x, factor, **kwargs):
        record = dict(index=len(events)+1, requested_direct_geometry=kwargs.get('_direct_geometry'),
            effective_direct_geometry=True, sparse=kwargs.get('_sparse', False), status='STARTED')
        events.append(record)
        kwargs['_direct_geometry'] = True
        before = time.monotonic(); cpu = time.process_time(); calls = n.nfev
        try:
            matrix = native(n, x, factor, **kwargs)
            record.update(status='COMPLETE', geometry=getattr(n, 'geometry_derivative_diagnostics', None))
            return matrix
        finally:
            record.update(wall_seconds=time.monotonic()-before, cpu_seconds=time.process_time()-cpu,
                residual_calls=n.nfev-calls)

    cls.jacobian = jacobian
    try:
        yield
    finally:
        if owned:
            cls.jacobian = native
        else:
            del cls.jacobian
        assert cls.jacobian is native


def solve(out, case):
    from openswing.bridge import dispatch
    folder = out/case['name']; request = read(folder/'request.json')
    assert request['initial_state'] and request['tolerance'] == 1e-12
    before = time.monotonic(); events = []; last = [None, 0.]
    with (folder/'solve/progress.jsonl').open('x') as log:
        def progress(stage, current, total):
            now = time.monotonic()
            if stage == last[0] and now-last[1] < .5 and current != total:
                return
            log.write(json.dumps(dict(stage=stage, current=current, total=total,
                wall_seconds=now-before, cpu_seconds=time.process_time()), default=float)+'\n')
            log.flush(); last[:] = [stage, now]
        try:
            with complete_geometry(events):
                result = dispatch(request, progress=progress)
        finally:
            write(folder/'tangent-calls.json', events)
    assert events and all(e['status'] == 'COMPLETE' for e in events)
    initialization = result['equilibrium_initialization']
    seeded = initialization['seeded_corrector']
    assert seeded['enabled'] and seeded['builder_detached']
    seeded['original_iteration_matrix_declaration'] = seeded['iteration_matrix']
    seeded['iteration_matrix'] = 'network.jacobian(x, 1., _sparse=True, _direct_geometry=True); diagnostic override'
    result['diagnostic_tangent_assembly'] = dict(method=__doc__, calls=events, primary_votes_added=0)
    write(folder/'result.json', result)
    write(folder/'solve-report.json', dict(result=pin(folder/'result.json'), request=pin(folder/'request.json'),
        solve_seconds=time.monotonic()-before, operations=dict(warm_solves=1, cold_solves=0),
        initialization=initialization, tangent_calls=pin(folder/'tangent-calls.json'), primary_votes_added=0))
    print(json.dumps(dict(beta=case['beta'], residual=result['residual'],
        iterations=initialization['newton_iterations'], tangent_builds=initialization['tangent_builds'])), flush=True)


def launch(out, name, phase):
    resource.setrlimit(resource.RLIMIT_AS, (LIMITS['address_space_bytes'],)*2)
    plan = checked(out); case = next(c for c in plan['cases'] if c['name'] == name)
    folder = out/name; phase_folder = folder/phase
    if phase == 'solve':
        assert not folder.exists()
        request, seed = original.request_for(out, plan, case)
        folder.mkdir(); write(folder/'request.json', request)
    else:
        assert read(folder/'solve/terminal.json')['process_reaped'] is True
        assert read(folder/'solve/sources-verified.json')['all_pins_checked_before_and_after'] is True
        assert (folder/'result.json').exists(), 'No complete result is available for verification.'
    phase_folder.mkdir(exist_ok=False)
    write(phase_folder/'started.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(), phase=phase))
    def caps():
        resource.setrlimit(resource.RLIMIT_AS, (LIMITS['address_space_bytes'],)*2)
        resource.setrlimit(resource.RLIMIT_CPU, (LIMITS['cpu_seconds'],)*2)
    start = time.monotonic(); pid = 0; timeout = False
    with (phase_folder/'stdout.log').open('x') as stdout, (phase_folder/'stderr.log').open('x') as stderr:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'worker', '--output', str(out),
            '--case', name, '--phase', phase], cwd=ROOT, env={**os.environ, **THREADS}, preexec_fn=caps,
            stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            while not pid:
                pid, status, usage = os.wait4(child.pid, os.WNOHANG)
                if pid:
                    break
                if time.monotonic()-start > LIMITS['wall_seconds']:
                    timeout = True; os.killpg(child.pid, signal.SIGKILL)
                    pid, status, usage = os.wait4(child.pid, 0); break
                time.sleep(.05)
        finally:
            if not pid:
                os.killpg(child.pid, signal.SIGKILL); pid, status, usage = os.wait4(child.pid, 0)
            child.returncode = os.waitstatus_to_exitcode(status)
    terminal = dict(returncode=child.returncode, supervisor_timeout=timeout, process_reaped=True,
        wall_seconds=time.monotonic()-start, cpu_seconds=usage.ru_utime+usage.ru_stime,
        peak_rss_kib=usage.ru_maxrss, finished_utc=datetime.now(timezone.utc).isoformat())
    write(phase_folder/'terminal.json', terminal); checked(out)
    write(phase_folder/'sources-verified.json', dict(all_pins_checked_before_and_after=True,
        plan=pin(out/'plan.json'), terminal=pin(phase_folder/'terminal.json')))
    print(json.dumps(dict(case=name, phase=phase, **terminal)), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare', 'launch', 'worker']); p.add_argument('--output', type=Path, required=True)
    p.add_argument('--case'); p.add_argument('--phase', choices=['solve', 'verify'])
    a = p.parse_args(); out = a.output.resolve()
    if a.action == 'prepare':
        prepare(out)
    elif a.action == 'launch':
        launch(out, a.case, a.phase)
    else:
        assert all(os.environ.get(k) == v for k, v in THREADS.items())
        plan = read(out/'plan.json'); case = next(c for c in plan['cases'] if c['name'] == a.case)
        if a.phase == 'solve':
            solve(out, case)
        else:
            original.verify(out, plan, case)
