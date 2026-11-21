"""Bounded AE-2 incidence continuation: convergence, tangent, verification.

Reuse production warm Newton with the independently checked complete geometry
iteration option. Final tangent/rank and all physical gates are unchanged.
Pending states never qualify as seeds. Each phase is a serial supervised child;
single-thread library imports precede fork and the numerical deadline.
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
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import probe_isae_ae2_incidence as original
from scripts.probe_isae_ae2_cold_trace import read, write, pin, THREADS
from scripts.probe_isae_ae2_incidence_iteration import iteration_geometry

LIMITS = original.LIMITS
checked = original.checked


def prepare(out):
    assert not out.exists()
    parent = ROOT/'artifacts/isae/ae2-incidence-iteration-20261110'
    old = checked(parent)
    assessment = read(parent/'assessment.json')
    assert assessment['status'] == 'VERIFIED_DIAGNOSTIC_BRANCH_TRACE_INCOMPLETE'
    assert assessment['all_processes_reaped']
    plan = deepcopy(old)
    paths = [Path(p['path']) for p in old['pins']]
    paths += [Path(__file__), ROOT/'scripts/probe_isae_ae2_incidence_iteration.py',
        parent/'plan.json', parent/'assessment.json', parent/'beta01/solve/terminal.json',
        parent/'beta01/solve/sources-verified.json']
    plan.update(observed_utc=datetime.now(timezone.utc).isoformat(), method=__doc__,
        pins=[pin(p) for p in sorted(set(paths))], phases=['solve', 'tangent', 'verify'])
    plan['qualifications'] += [
        'A checkpoint interrupts correction before its final tangent; this is pending, never an accepted solve.',
        'All original final tangent columns and the unchanged rank check are required in subsequent phases.',
        'Numerical libraries load in a single-thread parent before fork; numerical children retain all original limits.',
        'Each phase is terminal and source-verified before the next phase may start.']
    write(out/'plan.json', plan)
    print('Prepared staged incidence diagnostic; no numerical job started.', flush=True)


def stage_receipt(out, name, phase):
    folder = out/name/phase
    receipt = read(folder/'terminal.json')
    verified = read(folder/'sources-verified.json')
    assert receipt['returncode'] == 0 and receipt['process_reaped']
    assert not receipt['supervisor_timeout']
    assert verified['all_pins_checked_before_and_after']
    assert verified['plan'] == pin(out/'plan.json')
    assert verified['terminal'] == pin(folder/'terminal.json')
    return receipt


def preload():
    # No model is constructed and no physical residual or solve runs here.
    import numpy
    import scipy.linalg
    import scipy.sparse.linalg
    import openswing.bridge
    import openswing.time_integration
    import openswing.geometry_tangent
    import openswing.sparse_rank
    import openswing.source_coupled
    import openswing.source_discrete
    import openswing.equilibrium_state
    import openswing.seeded_corrector
    import openswing.steady_continuation
    import scripts.probe_isae_ae2_staged_inverse
    assert len(os.listdir('/proc/self/task')) == 1, 'Fork requires a single-thread numerical parent.'


def solve(out, plan, case):
    import numpy as np
    from scripts.probe_isae_ae2_staged_inverse import network
    from openswing.equilibrium_state import correct, capture
    from openswing import time_integration, seeded_corrector
    from openswing.steady_continuation import plain
    folder = out/case['name']; request = read(folder/'request.json'); n = network(request)
    assert not n.hinges and not n.operating.count and n.size == 2105
    native_newton = time_integration.newton; native_phase = seeded_corrector.phase
    observed = {}; events = []; before = time.monotonic()

    class PendingVerification(Exception):
        pass

    def observe_newton(*args, **kwargs):
        x, factor, iterations, builds = native_newton(*args, **kwargs)
        assert not observed
        observed.update(x=x.copy(), iterations=iterations, builds=builds)
        return x, factor, iterations, builds

    @contextmanager
    def checkpoint(net, report, phase):
        if phase != 'final_tangent':
            with native_phase(net, report, phase):
                yield
            return
        assert net is n and observed and report['builder_detached']
        assert report['factor_wrappers_alive_before_final_tangent'] == 0
        x = observed.pop('x'); residual = n.residual(x)
        error = float(np.max(abs(residual))); assert error <= 1e-12
        np.savez_compressed(folder/'candidate.npz', x=x, residual=residual)
        write(folder/'state.json', capture(n, x, residual=error, include_launch=False))
        write(folder/'candidate.json', plain(dict(status='PENDING_VERIFICATION', accepted=False,
            newton=observed, full_residual=error, seeded_corrector=report, tangent_calls=events,
            pins=[pin(folder/f) for f in ('request.json', 'candidate.npz', 'state.json')],
            seconds=time.monotonic()-before, primary_votes_added=0)))
        raise PendingVerification()

    with (folder/'solve/progress.jsonl').open('x') as log:
        def progress(stage, current, total):
            log.write(json.dumps(dict(stage=stage, current=current, total=total,
                wall_seconds=time.monotonic()-before, cpu_seconds=time.process_time()), default=float)+'\n')
            log.flush()
        time_integration.newton = observe_newton; seeded_corrector.phase = checkpoint
        try:
            with iteration_geometry(events):
                try:
                    correct(n, request['initial_state'], request['tolerance'], {}, progress=progress)
                except PendingVerification:
                    pass
                else:
                    raise AssertionError('Checkpoint must not return an accepted equilibrium.')
        finally:
            time_integration.newton = native_newton; seeded_corrector.phase = native_phase
    assert (folder/'candidate.json').exists() and not (folder/'result.json').exists()
    print(json.dumps(dict(beta=case['beta'], status='PENDING_VERIFICATION', **observed)), flush=True)


def candidate(out, case):
    import numpy as np
    from scripts.probe_isae_ae2_staged_inverse import network
    from openswing.equilibrium_state import restore
    folder = out/case['name']; stage_receipt(out, case['name'], 'solve')
    pending = read(folder/'candidate.json')
    assert pending['status'] == 'PENDING_VERIFICATION' and pending['accepted'] is False
    assert all(pin(p['path']) == p for p in pending['pins'])
    n = network(read(folder/'request.json'))
    restored = restore(n, read(folder/'state.json'))
    with np.load(folder/'candidate.npz') as values:
        x = values['x'].copy(); residual = values['residual'].copy()
    np.testing.assert_allclose(restored, x, rtol=1e-14, atol=2e-15)
    fresh = n.residual(x)
    np.testing.assert_allclose(fresh, residual, rtol=1e-8, atol=1e-12)
    assert np.max(abs(fresh)) <= 1e-12
    return n, x, folder, pending


def tangent(out, plan, case):
    from scipy.sparse import save_npz
    n, x, folder, pending = candidate(out, case)
    before = time.monotonic(); cpu = time.process_time(); calls = n.nfev
    jac = n.jacobian(x, 1., _sparse=True, _direct_geometry=False)
    save_npz(folder/'tangent.npz', jac)
    write(folder/'tangent.json', dict(status='COMPLETE_ORIGINAL_FINAL_TANGENT',
        candidate=pin(folder/'candidate.json'), matrix=pin(folder/'tangent.npz'),
        shape=list(jac.shape), nonzeros=int(jac.nnz), residual_calls=n.nfev-calls,
        cpu_seconds=time.process_time()-cpu, wall_seconds=time.monotonic()-before,
        primary_votes_added=0))
    print(json.dumps(dict(beta=case['beta'], shape=list(jac.shape), residual_calls=n.nfev-calls)), flush=True)


def verify(out, plan, case):
    from scipy.sparse import load_npz
    from openswing.equilibrium_state import check_tangent_rank, capture
    from openswing.source_discrete import source_network_result
    from openswing.steady_continuation import plain
    stage_receipt(out, case['name'], 'tangent')
    n, x, folder, pending = candidate(out, case)
    t = read(folder/'tangent.json')
    assert t['status'] == 'COMPLETE_ORIGINAL_FINAL_TANGENT'
    assert t['candidate'] == pin(folder/'candidate.json') and t['matrix'] == pin(folder/'tangent.npz')
    jac = load_npz(folder/'tangent.npz'); assert jac.shape == (n.size, n.size)
    rank = check_tangent_rank(jac); del jac
    result = source_network_result(n, x)
    assert result['converged'] and result['residual'] <= 1e-12
    result.update(numerics=read(folder/'request.json')['numerics'], continuation_steps=1,
        equilibrium_state=capture(n, x, residual=result['residual'], include_launch=False),
        equilibrium_initialization=dict(initialization='saved physical equilibrium',
            newton_iterations=pending['newton']['iterations'], tangent_builds=pending['newton']['builds'],
            residual=result['residual'], **rank), diagnostic_stages=dict(method=__doc__,
            pending=pin(folder/'candidate.json'), final_tangent=pin(folder/'tangent.json'), primary_votes_added=0))
    result['equilibrium_state']['limitations'].append('Static source-discrete policy only; cannot initialize physical dynamics or a different structural operator.')
    write(folder/'result.json', plain(result))
    original.verify(out, plan, case)


def launch(out, name, phase):
    assert all(os.environ.get(k) == v for k, v in THREADS.items())
    resource.setrlimit(resource.RLIMIT_AS, (LIMITS['address_space_bytes'],)*2)
    plan = checked(out); case = next(c for c in plan['cases'] if c['name'] == name)
    assert phase in plan['phases']
    folder = out/name; phase_folder = folder/phase
    if phase == 'solve':
        assert not folder.exists()
        request, _ = original.request_for(out, plan, case)
        folder.mkdir(); write(folder/'request.json', request)
    else:
        stage_receipt(out, name, 'solve' if phase == 'tangent' else 'tangent')
    phase_folder.mkdir(exist_ok=False)
    before = time.monotonic(); preload(); loading = time.monotonic()-before
    write(phase_folder/'started.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        phase=phase, library_preload_seconds=loading, numerical_limits=LIMITS))
    sys.stdout.flush(); sys.stderr.flush(); began = time.monotonic()
    pid = os.fork()
    if pid == 0:
        code = 0
        try:
            os.setsid()
            resource.setrlimit(resource.RLIMIT_CPU, (LIMITS['cpu_seconds'],)*2)
            signal.alarm(LIMITS['wall_seconds']+2)
            with (phase_folder/'stdout.log').open('x') as stdout, (phase_folder/'stderr.log').open('x') as stderr:
                os.dup2(stdout.fileno(), 1); os.dup2(stderr.fileno(), 2)
                try:
                    globals()[phase](out, plan, case)
                except BaseException:
                    traceback.print_exc(); code = 1
                sys.stdout.flush(); sys.stderr.flush()
        except BaseException:
            traceback.print_exc(); sys.stderr.flush(); code = 1
        finally:
            os._exit(code)
    reaped = 0; timeout = False
    try:
        while not reaped:
            reaped, status, usage = os.wait4(pid, os.WNOHANG)
            if reaped:
                break
            if time.monotonic()-began > LIMITS['wall_seconds']:
                timeout = True; os.kill(pid, signal.SIGKILL)
                reaped, status, usage = os.wait4(pid, 0); break
            time.sleep(.05)
    finally:
        if not reaped:
            os.kill(pid, signal.SIGKILL); reaped, status, usage = os.wait4(pid, 0)
    terminal = dict(returncode=os.waitstatus_to_exitcode(status), supervisor_timeout=timeout,
        process_reaped=True, wall_seconds=time.monotonic()-began,
        cpu_seconds=usage.ru_utime+usage.ru_stime, peak_rss_kib=usage.ru_maxrss,
        finished_utc=datetime.now(timezone.utc).isoformat())
    write(phase_folder/'terminal.json', terminal); checked(out)
    write(phase_folder/'sources-verified.json', dict(all_pins_checked_before_and_after=True,
        plan=pin(out/'plan.json'), terminal=pin(phase_folder/'terminal.json')))
    print(json.dumps(dict(case=name, phase=phase, **terminal)), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare', 'launch']); p.add_argument('--output', type=Path, required=True)
    p.add_argument('--case'); p.add_argument('--phase', choices=['solve', 'tangent', 'verify'])
    a = p.parse_args(); out = a.output.resolve()
    if a.action == 'prepare':
        prepare(out)
    else:
        launch(out, a.case, a.phase)
