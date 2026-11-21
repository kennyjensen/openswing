"""Small serial Eq.68 integration check on the unchanged RS1 outline.

This compares the current body kernel with exact endpoint-area integrals, not
with missing original ASWING inputs. Resource limits precede numerical imports.
"""
import argparse
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


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        if os.environ.get(name) != '1':
            raise ValueError(f'{name}=1 is required')
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    signal.alarm(25)
    started = time.perf_counter()
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.geometry import mesh_beam
    from openswing.volume import body_loads, body_quadrature
    from openswing.inertia import Motion
    baseline_path = ROOT/'artifacts/isae/sa13-quadrature-20261109/baseline.json'
    baseline = json.loads(baseline_path.read_text())
    model_path = ROOT/'docs/validation/isae-sa13-rs1-outline.asw'
    assert sha(model_path) == baseline['model_sha256']
    model = parse_asw(model_path.read_text()); beam = model.beams[0]
    velocity = np.array([np.cos(np.deg2rad(9.)), 0., np.sin(np.deg2rad(9.))])
    rows = []
    for old in baseline['rows']:
        mesh = mesh_beam(beam, old['intervals'])
        t, points, _, weights = body_quadrature(mesh)
        loads = body_loads(mesh, 1., np.broadcast_to(velocity, points.shape), Motion(), np.zeros(3))
        expected = velocity[0]*velocity[2]*np.pi*(
            beam.value('radius', mesh.t1, side='left')**2
            -beam.value('radius', mesh.t0, side='right')**2)
        delta = loads['lift'][:, 2]-expected
        assert max(abs(delta)) < 2e-15
        np.testing.assert_allclose(weights.sum(axis=1), mesh.length, rtol=2e-15)
        row = dict(intervals=len(mesh.t0), quadrature_shape=list(t.shape),
                   active_points=int(np.count_nonzero(weights)), padded_points=t.size,
                   max_force_error=float(max(abs(delta))),
                   relative_to_peak_force=float(max(abs(delta))/max(abs(expected))),
                   net_force_error=float(delta.sum()),
                   maximum_local_coefficient_error=float(max(abs(delta)/mesh.length/(.5*model.reference[0][2]))),
                   before=old)
        rows.append(row)
        print(json.dumps(row), flush=True)
    modules = {p.name: sha(p) for p in (ROOT/'openswing').glob('*.py')}
    changed = sorted(k for k in modules if modules[k] != baseline['modules'][k])
    assert changed == ['geometry_partials.py', 'volume.py', 'volume_state_tangent.py']
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(), rows=rows,
                  baseline_sha256=sha(baseline_path), model_sha256=sha(model_path),
                  script_sha256=sha(Path(__file__)), modules=modules, changed_modules=changed,
                  seconds=time.perf_counter()-started,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  physical_solves=0, native_passes_added=0,
                  scope='Exact steady force integral on the disclosed RS1 outline; no archived native target.',
                  limits=dict(address_space_mib=512, cpu_seconds=15, wall_seconds=25, blas_threads=1))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')


if __name__ == '__main__':
    main()
