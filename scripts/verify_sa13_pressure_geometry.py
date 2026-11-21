"""Independent Decimal check of the pressure-figure identity from original MAT.

Resource limits precede numerical imports. No production solver is imported.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analysis', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        assert os.environ.get(name) == '1', name
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    signal.alarm(25)
    started = time.perf_counter()
    import numpy as np
    from scipy.io import loadmat
    audit = json.loads(args.analysis.read_text())
    for name, expected in audit['sources'].items():
        assert sha(ROOT/name) == expected, name
    decoded = json.loads((ROOT/'docs/validation/isae-sa13-sources.json').read_text())
    case = next(c for c in decoded['cases'] if c['name'] == 'pressure')
    figure = ROOT/'reference/isae-validation'/decoded['revision']/case['path']
    mat = loadmat(figure, simplify_cells=True)

    def properties(node):
        if isinstance(node, dict):
            props = node.get('properties', {})
            if 'XData' in props and 'YData' in props:
                yield props
            yield from properties(node.get('children', []))
        elif isinstance(node, (list, tuple, np.ndarray)):
            for item in node:
                yield from properties(item)

    series = [p for key, root in mat.items() if key.startswith('hgS_') for p in properties(root)]
    assert len(series) == 5
    assert [p.get('DisplayName', '') for p in series] == [r['label'] for r in case['series']]
    arrays = []
    for props, saved in zip(series, case['series']):
        xy = np.c_[np.asarray(props['XData']).ravel(), np.asarray(props['YData']).ravel()]
        assert len(xy) == len(saved['xy']) == 103
        for values, expected in zip(xy, saved['xy']):
            for value, target in zip(values, expected):
                assert (not np.isfinite(value)) if target is None else value == target
        arrays.append(xy)
    curve, upper, lower = arrays[2:]
    errors, offsets = [], []
    with localcontext() as context:
        context.prec = 60
        previous = None
        for i, ((x, y), hi, lo) in enumerate(zip(curve, upper, lower)):
            if not np.isfinite(y):
                assert audit['rows'][i]['status'] == 'unavailable'
                continue
            assert x == hi[0] == lo[0]
            xx = Decimal.from_float(float(x))
            rr = (Decimal.from_float(float(hi[1]))-Decimal.from_float(float(lo[1])))/2
            slope = (rr-previous[1])/(xx-previous[0]) if previous else Decimal(0)
            unshifted = 100*slope**2
            prediction = unshifted-5
            observed = Decimal.from_float(float(y))
            offsets.append(observed-unshifted)
            errors.append(abs(prediction-observed))
            assert errors[-1] < Decimal('2e-12'), (i+1, errors[-1])
            previous = xx, rr
    assert len(errors) == 56
    assert not any(n == 'openswing' or n.startswith('openswing.') for n in sys.modules)
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
                  status='VERIFIED_ORIGINAL_MAT_AND_DECIMAL_GEOMETRY_IDENTITY',
                  finite_values=56, retained_values=103, unavailable_values=47,
                  original_coordinate_pairs=515, maximum_decimal_error=str(max(errors)),
                  inferred_offset_range=list(map(str, [min(offsets), max(offsets)])),
                  source_pins=len(audit['sources']), figure_sha256=sha(figure),
                  analysis_sha256=sha(args.analysis), script_sha256=sha(Path(__file__)),
                  seconds=time.perf_counter()-started, peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  limits=dict(address_space_mib=512, cpu_seconds=15, wall_seconds=25, blas_threads=1),
                  production_imports=0, solver_calls=0, native_passes_added=0)
    with args.output.open('x') as handle:
        json.dump(result, handle, indent=2); handle.write('\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
