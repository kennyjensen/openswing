"""Resolve AE-2 Newton-step curvature by section, without changing the model."""
import argparse
import faulthandler
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
from scripts.probe_isae_ae2_cold_trace import read, write, pin, THREADS


def checked(out):
    p = read(out/'plan.json')
    assert all(pin(x['path']) == x for x in p['pins'])
    return p


def prepare(out):
    assert not out.exists()
    parent = ROOT/'artifacts/isae/ae2-newton-directions-20261110'
    plan = checked(parent)
    paths = [Path(__file__), parent/'plan.json']+[Path(p['path']) for p in plan['pins']]
    for method in ('lagged', 'full'):
        assert read(parent/method/'terminal.json')['returncode'] == 0
        paths += [parent/method/name for name in ('report.json', 'terminal.json', 'directions.npz')]
    write(out/'plan.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        parent=str(parent), pins=[pin(p) for p in sorted(set(paths))], limits=plan['limits'],
        alphas=[0., .03125, .0625, .125, .25, .5, 1.], primary_votes_added=0,
        method=__doc__, qualifications=['All original physical equations retained.',
            'Correction-norm merit is diagnostic; production line search remains unchanged.',
            'No nonlinear solve or native comparison added.']))


def worker(out):
    limits = read(out/'plan.json')['limits']
    resource.setrlimit(resource.RLIMIT_AS, (limits['address_space_bytes'],)*2)
    resource.setrlimit(resource.RLIMIT_CPU, (limits['soft_cpu_seconds'], limits['hard_cpu_seconds']))
    plan = checked(out); parent = Path(plan['parent']); original = checked(parent)
    assert all(os.environ.get(k) == '1' for k in THREADS)
    stack = (out/'signal-stack.log').open('x')
    faulthandler.register(signal.SIGXCPU, file=stack, all_threads=False, chain=False)
    faulthandler.register(signal.SIGALRM, file=stack, all_threads=False, chain=True)
    signal.alarm(limits['alarm_seconds'])
    import numpy as np
    from scripts.probe_isae_ae2_staged_inverse import network
    from openswing.steady_continuation import context, restore, plain
    from openswing.structured_static import jacobian, BlockFactorization, linearization
    from openswing.aero import _stall_leakage

    n = network(read(original['request'])); packet = read(original['boundary'])['checkpoint']
    s = packet['context']['solver']
    x, reached, *_ = restore(n, packet, context(n, s['tolerance'], s['continuation_steps'], s['reuse_matrices'], s['full_structure']))
    with np.load(parent/'lagged/directions.npz') as z:
        np.testing.assert_array_equal(x, z['state']); delta = z['delta'].copy(); base = z['baseline'].copy()
    with np.load(parent/'full/directions.npz') as z:
        np.testing.assert_array_equal(x, z['state']); full_delta = z['delta'].copy()
    matrix, counts = jacobian(n, x, 1.); factor = BlockFactorization(matrix)
    fresh_delta = factor.solve(-n.residual(x, 1.))
    np.testing.assert_allclose(fresh_delta, delta, rtol=1e-11, atol=1e-13)
    correction_merit = float(delta@delta); residual_merit = float(base@base)
    samples = []
    for alpha in plan['alphas']:
        state = x+alpha*delta
        with linearization(n, state, 1., capture_circulation=True) as (fields, residual):
            d = fields.circulation_aero; p = d['p']; c = d['condition']
            assert not d['basis'].modes and not np.any(d['lag_rate'])
            v = d['velocity']; vp = v-np.sum(v*p['s'], axis=-1)[:, None]*p['s']
            speed = np.maximum(np.linalg.norm(vp, axis=1), c.speed*1e-12)
            cl = 2*d['gamma']/(p['chord']*speed)
            # Independent literal Eq. 204; no fitted limit or stall setting.
            f = c.stall_width*(np.logaddexp(0, (cl-p['clmax'])/c.stall_width)
                              -np.logaddexp(0, (p['clmin']-cl)/c.stall_width))
            stable, _ = _stall_leakage(cl, p['clmin'], p['clmax'], c.stall_width)
            np.testing.assert_allclose(f, stable, atol=2e-15, rtol=1e-12)
            tangency = np.sum(d['cp_velocity']*p['normal'], axis=1)/c.speed
            leakage = speed/p['slope']*c.stall_factor*f/c.speed if c.stall else np.zeros_like(cl)
            section = tangency-leakage
            np.testing.assert_allclose(section, residual[n.gamma_start:], atol=1e-12, rtol=1e-10)
            points = [dict(index=i, t=float(p['t'][i]), cl=float(cl[i]),
                clmin=float(p['clmin'][i]), clmax=float(p['clmax'][i]), speed=float(speed[i]),
                tangency=float(tangency[i]), leakage=float(leakage[i]), residual=float(section[i]))
                for i in range(len(cl))]
        correction = factor.solve(-residual)
        value = float(residual@residual); corrected = float(correction@correction)
        samples.append(dict(alpha=alpha, residual_merit=value, residual_ratio=value/residual_merit,
            correction_merit=corrected, correction_ratio=corrected/correction_merit,
            correction_armijo=bool(corrected<correction_merit*(1-1e-4*alpha)),
            circulation_fraction=float(section@section/value), sections=points,
            stalled_sections=int(np.count_nonzero((cl<p['clmin'])|(cl>p['clmax'])))))
    checked(out)
    write(out/'report.json', plain(dict(status='SECTION_DIAGNOSTIC_COMPLETE', primary_votes_added=0,
        independent_stall_formula_checked=True, physical_circulation_reconstructed=True,
        direction_relative_difference=float(np.linalg.norm(delta-full_delta)/np.linalg.norm(full_delta)),
        direction_max_difference=float(np.max(abs(delta-full_delta))), samples=samples,
        matrix_counts=counts, cpu_seconds=time.process_time(), evaluations=n.nfev)))


def launch(out):
    plan = checked(out)
    with (out/'started.json').open('x') as f:
        json.dump(dict(observed_utc=datetime.now(timezone.utc).isoformat()), f)
    start = time.monotonic(); timeout = False; pid = 0
    with (out/'stdout.log').open('x') as stdout, (out/'stderr.log').open('x') as stderr:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'worker', '--output', str(out)],
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
    receipt = dict(returncode=child.returncode, process_reaped=True, supervisor_timeout=timeout,
        wall_seconds=time.monotonic()-start, cpu_seconds=usage.ru_utime+usage.ru_stime,
        peak_rss_kib=usage.ru_maxrss, finished_utc=datetime.now(timezone.utc).isoformat())
    write(out/'terminal.json', receipt); print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare', 'worker', 'launch'])
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); globals()[a.action](a.output.resolve())
