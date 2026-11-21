"""Bounded AE-2 Jacobian/direction audit at an existing continuation boundary.

This is a derivative diagnostic, not an equilibrium solve or a native pass.
Each matrix is constructed in its own one-thread, serial, reaped process.
"""
import argparse
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
    plan = read(out/'plan.json')
    assert all(pin(p['path']) == p for p in plan['pins'])
    return plan


def prepare(out):
    assert not out.exists()
    parent = ROOT/'artifacts/isae/ae2-cold-stages-20261110'
    old = read(parent/'plan.json')
    assert all(pin(p['path']) == p for p in old['pins'])
    case = next(c for c in old['cases'] if c['name'] == 'cold20-m80')
    boundary = parent/'cases/cold20-m80/03/result.json'
    assert read(parent/'cases/cold20-m80/03/terminal.json')['returncode'] == 0
    paths = [Path(__file__), parent/'plan.json', boundary,
             parent/'cases/cold20-m80/03/terminal.json']
    paths += [Path(p['path']) for p in old['pins']]
    write(out/'plan.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        request=case['request'], boundary=str(boundary), target_load=1.,
        methods=['lagged', 'full'], pins=[pin(p) for p in sorted(set(paths))],
        limits=old['limits'], primary_votes_added=0, method=__doc__,
        directional_steps=[1e-4, 1e-5, 1e-6], line_search_trials=12,
        qualifications=['Original request, source, normalized state and physical residual unchanged.',
            'No nonlinear solve, initial-rank certificate or full-load equilibrium claimed.',
            'Full Jacobian is diagnostic; the production approximate matrix stays default.',
            'Central directional differences and the original full-residual merit test are independent of matrix assembly.']))
    print('Prepared independent lagged/full direction diagnostics.')


def worker(out, method):
    limits = read(out/'plan.json')['limits']
    resource.setrlimit(resource.RLIMIT_AS, (limits['address_space_bytes'],)*2)
    resource.setrlimit(resource.RLIMIT_CPU, (limits['soft_cpu_seconds'], limits['hard_cpu_seconds']))
    plan = checked(out)
    assert method in plan['methods']
    assert all(os.environ.get(k) == '1' for k in THREADS)
    folder = out/method
    stack = (folder/'signal-stack.log').open('x')
    faulthandler.register(signal.SIGXCPU, file=stack, all_threads=False, chain=False)
    faulthandler.register(signal.SIGALRM, file=stack, all_threads=False, chain=True)
    signal.alarm(limits['alarm_seconds'])
    import numpy as np
    from scripts.probe_isae_ae2_staged_inverse import network
    from openswing.steady_continuation import context, restore, plain
    from openswing.structured_static import jacobian, BlockFactorization
    from openswing.newton_structure import NewtonBeamFactor
    from openswing.aero import AnalysisError
    from openswing.ground import GroundIntersectionError

    request = read(plan['request']); packet = read(plan['boundary'])['checkpoint']
    n = network(request); s = packet['context']['solver']
    ctx = context(n, s['tolerance'], s['continuation_steps'], s['reuse_matrices'], s['full_structure'])
    x, reached, *_ = restore(n, packet, ctx)
    assert reached == .875 and not n.hinges and n.operating.count == 0
    original = x.copy(); target = plan['target_load']
    baseline = n.residual(x, target); merit = float(baseline@baseline)
    ranges = dict(compatibility=(0, 6*n.ne), balance=(6*n.ne, 6*(n.ne+n.nn)),
                  constraints=(6*(n.ne+n.nn), n.gamma_start), circulation=(n.gamma_start, n.size))
    def blocks(v):
        return {k: dict(norm2=float(v[a:b]@v[a:b]), max_abs=float(np.max(abs(v[a:b]), initial=0.)))
                for k, (a, b) in ranges.items()}
    started = time.process_time(); before = n.nfev
    if method == 'lagged':
        matrix, detail = jacobian(n, x, target)
        factor = BlockFactorization(matrix)
        def product(v):
            split = n.gamma_start
            return np.r_[matrix.mechanical@v[:split]+matrix.force_circulation@v[split:],
                         matrix.flow_geometry@v[:split]+matrix.circulation@v[split:]]
    else:
        matrix = n.jacobian(x, target, _sparse=True, _direct_geometry=True)
        factor = NewtonBeamFactor(n, matrix)
        detail = dict(geometry=n.geometry_derivative_diagnostics,
                      circulation=n.circulation_derivative_diagnostics,
                      factor=factor.report)
        product = lambda v: matrix@v
    delta = factor.solve(-baseline)
    matrix_seconds = time.process_time()-started
    matrix_evaluations = n.nfev-before
    jd = product(delta)
    linear_error = float(np.max(abs(jd+baseline)))
    assert linear_error <= 1e-8*max(1., np.max(abs(baseline)))
    scale = max(1., float(np.max(abs(delta))))
    derivatives = []
    arrays = dict(state=x, baseline=baseline, delta=delta, matrix_product=jd)
    for step in plan['directional_steps']:
        h = step/scale
        fd = (n.residual(x+h*delta, target)-n.residual(x-h*delta, target))/(2*h)
        error = fd-jd
        derivatives.append(dict(coordinate_step=step, parameter_step=h,
            relative_norm_error=float(np.linalg.norm(error)/max(np.linalg.norm(fd), 1e-30)),
            max_abs_error=float(np.max(abs(error))), error_blocks=blocks(error),
            merit_slope=float(2*baseline@fd), newton_merit_slope=float(-2*merit)))
        arrays['directional_'+str(step)] = fd
    change = max(float(np.max(abs(delta[:6*n.nn]))), float(np.max(abs(delta[n.gamma_start:n.operating_start]))))
    initial_alpha = 1/max(1., change)
    trials = []; accepted = None
    for i in range(plan['line_search_trials']):
        alpha = initial_alpha/2**i
        try:
            value = n.residual(x+alpha*delta, target)
            trial_merit = float(value@value)
            good = bool(np.isfinite(trial_merit) and trial_merit < merit*(1-1e-4*alpha))
            trial = dict(alpha=alpha, merit=trial_merit, ratio=trial_merit/merit,
                         armijo=good, blocks=blocks(value))
            if good and accepted is None: accepted = i
        except (AnalysisError, GroundIntersectionError) as exc:
            trial = dict(alpha=alpha, armijo=False, error=type(exc).__name__+': '+str(exc))
        trials.append(trial)
    fresh = n.residual(x, target)
    np.testing.assert_array_equal(x, original)
    np.testing.assert_allclose(fresh, baseline, rtol=1e-12, atol=1e-14)
    checked(out)
    np.savez(folder/'directions.npz', **arrays)
    write(folder/'report.json', plain(dict(status='DERIVATIVE_DIAGNOSTIC_COMPLETE', method=method,
        primary_votes_added=0, load_boundary=reached, evaluation_load=target, size=n.size,
        boundary_residual=packet['physical_residual'], baseline_merit=merit, baseline_blocks=blocks(baseline),
        matrix_detail=detail, matrix_cpu_seconds=matrix_seconds, matrix_residual_evaluations=matrix_evaluations,
        linear_solve_max_error=linear_error, direction_max_abs=float(np.max(abs(delta))),
        geometry_circulation_max_change=change, directional_checks=derivatives,
        trials=trials, first_accepted_trial=accepted, evaluations=n.nfev,
        cpu_seconds=time.process_time(), restored_state_unchanged=True)))
    print(json.dumps(dict(method=method, accepted=accepted, matrix_cpu_seconds=matrix_seconds,
        fd_relative_error=derivatives[-1]['relative_norm_error'], evaluations=n.nfev)), flush=True)


def launch(out, method):
    plan = checked(out); assert method in plan['methods']
    folder = out/method; folder.mkdir(exist_ok=False)
    write(folder/'started.json', dict(observed_utc=datetime.now(timezone.utc).isoformat()))
    start = time.monotonic(); timeout = False; pid = 0
    with (folder/'stdout.log').open('x') as stdout, (folder/'stderr.log').open('x') as stderr:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'worker',
            '--output', str(out), '--method', method], cwd=ROOT, env={**os.environ, **THREADS},
            stdout=stdout, stderr=stderr, start_new_session=True)
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
    receipt = dict(method=method, returncode=child.returncode, process_reaped=True,
        supervisor_timeout=timeout, wall_seconds=time.monotonic()-start,
        cpu_seconds=usage.ru_utime+usage.ru_stime, peak_rss_kib=usage.ru_maxrss,
        finished_utc=datetime.now(timezone.utc).isoformat())
    write(folder/'terminal.json', receipt); print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare', 'worker', 'launch'])
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--method', choices=['lagged', 'full'])
    a = p.parse_args()
    if a.action == 'prepare': prepare(a.output.resolve())
    else: globals()[a.action](a.output.resolve(), a.method)
