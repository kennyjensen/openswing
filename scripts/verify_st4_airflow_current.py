"""One current-source ST4 airflow probe with strict small-job resource limits."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def read(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path, value):
    with path.open('x') as stream:
        stream.write(json.dumps(value, allow_nan=False, separators=(',', ':'))+'\n')


def prepare(out):
    model = 'reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7a/7a_b17.asw'
    folder = (ROOT/model).parent
    template = read(ROOT/'artifacts/isae/st4-modal-output-20261104/request.json')
    assert template['source'] == (ROOT/model).read_text()
    template['condition'].update(freeze_influences=False, circulation_modes={'1':0}, wake_core_ratio=.25,
                                 stall_factor=40., stall_width=.05)
    template['modes']['matrices'] = False
    files = [*sorted((ROOT/'openswing').glob('*.py')), Path(__file__),
             folder/'7a_b17.asw', folder/'Flutter_analysis.sh', folder/'eig.txt',
             ROOT/'docs/validation/aswing-authoritative-sources.json']
    for entry in read(ROOT/'docs/validation/aswing-authoritative-sources.json')['files']:
        if entry['id'] in ('isae-part-3', 'drela-steady', 'drela-unsteady'):
            for field, key in [('local_pdf','sha256'), ('local_text','text_sha256')]:
                path = ROOT/entry[field]; assert sha(path) == entry[key]; files.append(path)
    old = read(ROOT/'artifacts/isae/st4-pg-mach-20261104/plan.json')
    changes = [p for p,h in old['pins'].items() if p.startswith('openswing/') and sha(ROOT/p) != h]
    out.mkdir(parents=True)
    write(out/'plan.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(), model=model,
        request_template=template, jobs=[dict(speed=120.5, panels=16, spacing='cosine')],
        pins={str(p.relative_to(ROOT)):sha(p) for p in files}, changed_since_old_airflow=changes,
        limits=dict(address_space_MiB=512, cpu_seconds=15, wall_seconds=25, blas_threads=1),
        qualification='Current-code coarse probe only. Retain original inputs and declared airflow settings; no mesh convergence or recovered native startup claim. Paper40-node protocol requires a separate setup check. No added comparison votes.'))
    print('Prepared one16-interval current-source airflow probe; previous production changes:', len(changes))


def run(out, index):
    assert all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'))
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU, (15,)*2); signal.alarm(25)
    plan = read(out/'plan.json'); job = plan['jobs'][index]
    for p,h in plan['pins'].items(): assert sha(ROOT/p) == h, p
    folder = out/f'job-{index:02d}'; folder.mkdir()
    request = deepcopy(plan['request_template'])
    request['condition']['speed'] = job['speed']
    request['panels'] = dict(default=job['panels'], beams={'1':dict(count=job['panels'], spacing=job['spacing'])})
    write(folder/'request.json', request)
    tick, cpu = time.monotonic(), time.process_time()
    events = []
    def record(stage):
        event = dict(stage=stage, wall_seconds=time.monotonic()-tick, cpu_seconds=time.process_time()-cpu,
                     peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        events.append(event)
        with (folder/'events.jsonl').open('a') as stream: stream.write(json.dumps(event)+'\n')
        print(json.dumps(event), flush=True)
    import numpy as np
    from scipy.sparse import save_npz
    from openswing.bridge import dispatch
    import openswing.linear_dynamics as dynamics
    record('imports_done')
    saved = dynamics.linearize; held = []
    def capture(system, *args, **kwargs):
        record('assembly_start')
        a,m = saved(system, *args, **kwargs)
        record('assembly_done')
        save_npz(folder/'A.npz', a); save_npz(folder/'M.npz', m)
        held.append((system,a,m)); return a,m
    dynamics.linearize = capture
    try: result = dispatch(request)
    finally: dynamics.linearize = saved
    record('dispatch_done')
    write(folder/'result.json', result); record('output_saved')
    assert len(held) == 1
    system,a,m = held[0]; base = result['base']
    assert result['converged'] and base['converged'] and len(result['modes']) == 16
    zero = np.zeros(system.size); fresh = float(np.max(abs(system.residual(zero,zero))))
    assert fresh < 1e-8
    checks = []
    for mode in result['modes']:
        lam = complex(*mode['eigenvalue']); row = dict(index=mode['index'])
        vectors = {}
        for side in ('left','right'):
            v = np.asarray(mode[side]['real'])+1j*np.asarray(mode[side]['imag']); vectors[side] = v
            av,mv = (a@v,m@v) if side == 'right' else (v.conjugate()@a,v.conjugate()@m)
            error = float(np.linalg.norm(av-lam*mv)/(np.linalg.norm(av)+abs(lam)*np.linalg.norm(mv)))
            assert error < 1e-8; row[side] = error
        row['mass_pairing'] = float(abs(np.vdot(vectors['left'],m@vectors['right'])-1))
        assert row['mass_pairing'] < 1e-8; checks.append(row)
    for p,h in plan['pins'].items(): assert sha(ROOT/p) == h, p
    record('verification_done')
    write(folder/'report.json', dict(job=job, matrix_checks=checks, fresh_residual=fresh, events=events,
        roots=[mode['eigenvalue'] for mode in result['modes']],
        actual_nodes=base['structural_nodes'], actual_elements=base['structural_elements'],
        plan_sha256=sha(out/'plan.json'), artifacts={p.name:sha(p) for p in folder.iterdir()},
        primary_votes_added=0, historical_settings_authenticated=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare','run'])
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--index', type=int, default=0)
    args = parser.parse_args()
    (prepare(args.output) if args.action == 'prepare' else run(args.output.resolve(),args.index))
