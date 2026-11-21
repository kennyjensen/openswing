"""Replay 22 pressure-field stations against the saved independent integral.

The archived experimental ordinates and ASWING curves are not acceptance
targets. Compare only the unchanged regularized source law and geometry.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert all(os.environ.get(k) == '1' for k in
               ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'))
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15)); signal.alarm(25)
    started = time.perf_counter()
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.geometry import mesh_beam
    from openswing.volume import VolumeField
    directory = ROOT/'artifacts/isae/sa13-quadrature-20261109'
    before = directory/'before/volume.py'
    baseline = json.loads((directory/'baseline.json').read_text())
    assert sha(before) == baseline['modules']['volume.py']
    spec = importlib.util.spec_from_file_location('openswing._sa13_before_volume', before)
    previous = importlib.util.module_from_spec(spec); spec.loader.exec_module(previous)
    oracle_path = ROOT/'docs/validation/isae-sa13-velocity.json'
    oracle = json.loads(oracle_path.read_text())
    assert oracle['script_sha256'] == sha(ROOT/'scripts/check-isae-sa13-velocity.py')
    assert oracle['native_sha256'] == sha(ROOT/'docs/validation/isae-sa13.json')
    assert oracle['source_sha256'] == sha(ROOT/'docs/validation/isae-sa13-sources.json')
    source = json.loads((ROOT/'docs/validation/isae-sa13-sources.json').read_text())
    case = next(c for c in source['cases'] if c['name'] == 'pressure')
    model_path = ROOT/case['derived_path']
    assert sha(model_path) == case['derived_sha256']
    reference, = [r for r in oracle['rows'] if r['specification'] == dict(
        case='pressure', panels=32, alpha=0., length=1., surface_offset=1e-6)]
    model = parse_asw(model_path.read_text()); mesh = mesh_beam(model.beams[0], 32)
    points = np.array([r['position'] for r in reference['checks']])
    np.testing.assert_array_equal(points[:, 2], model.beams[0].value('radius', points[:, 0])*(1+1e-6))
    independent = np.array([r['independent_velocity'] for r in reference['checks']])
    direction = np.array([1., 0., 0.]); results = {}
    for label, cls in [('before', previous.VolumeField), ('after', VolumeField)]:
        field = cls(model, [mesh], direction, np.eye(3))
        velocity = 10*(direction+field.velocity(points))
        cp = 100*(1-np.sum(velocity*velocity, axis=1)/100)
        results[label] = dict(source_points=len(field.sources), velocity=velocity.tolist(),
                             Cp_percent=cp.tolist(),
                             maximum_velocity_error=float(np.max(abs(velocity-independent))),
                             maximum_Cp_percent_error=float(max(abs(cp-np.array(
                                 [r['independent_Cp_percent'] for r in reference['checks']])))))
    np.testing.assert_allclose(results['before']['velocity'],
                               [r['native_velocity'] for r in reference['checks']], rtol=0, atol=2e-12)
    assert results['after']['maximum_velocity_error'] < results['before']['maximum_velocity_error']
    record = dict(observed_utc=datetime.now(timezone.utc).isoformat(), results=results,
                  specification=reference['specification'], points=points.tolist(),
                  independent_velocity=independent.tolist(),
                  oracle_sha256=sha(oracle_path), oracle_error_bound=reference['adaptive_error_bound'],
                  before_kernel_sha256=sha(before), model_sha256=sha(model_path),
                  script_sha256=sha(Path(__file__)),
                  modules={p.name: sha(p) for p in (ROOT/'openswing').glob('*.py')},
                  seconds=time.perf_counter()-started,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  physical_solves=0, native_passes_added=0,
                  limits=dict(address_space_mib=512, cpu_seconds=15, wall_seconds=25, blas_threads=1))
    with args.output.open('x') as handle:
        json.dump(record, handle, indent=2); handle.write('\n')
    print(json.dumps({k: {n: v for n, v in r.items() if n not in ('velocity', 'Cp_percent')}
                      for k, r in results.items()}))


if __name__ == '__main__':
    main()
