"""Independently verify the SA-13 load identity against original MAT arrays.

Decimal arithmetic uses original binary64 radius/position values. No producer
helper, OpenSwing module, equation fit or physical solver is used.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import hashlib
import json
import math
import os
from pathlib import Path
import re
import resource
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analysis', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        assert os.environ.get(name) == '1', name
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    signal.alarm(25)
    start = time.perf_counter()
    import numpy as np
    from scipy.io import loadmat
    analysis = json.loads(args.analysis.read_text())
    for name, expected in analysis['sources'].items():
        assert sha(ROOT/name) == expected, name
    decoded = json.loads((ROOT/'docs/validation/isae-sa13-sources.json').read_text())
    results, maximum, coordinate_pairs = [], Decimal(0), 0
    with localcontext() as context:
        context.prec = 50
        for case in decoded['cases']:
            path = ROOT/'reference/isae-validation'/decoded['revision']/case['path']
            original = loadmat(path, simplify_cells=True)
            roots = [v for k, v in original.items() if k.startswith('hgS_')]
            assert len(roots) == 1
            original['root'] = roots[0]  # decoded location alias, not a MAT key
            arrays = []
            for saved in case['series']:
                node = original
                for key, index in re.findall(r'([A-Za-z_][A-Za-z_0-9]*)|\[(\d+)\]', saved['location']):
                    node = node[key] if key else node[int(index)]
                props = node['properties']
                assert str(props.get('DisplayName', '')) == saved['label']
                x, y = (np.asarray(props[k], dtype=float).ravel() for k in ('XData', 'YData'))
                assert len(x) == len(y) == len(saved['xy'])
                for xy, observed in zip(zip(x, y), saved['xy']):
                    for value, expected in zip(xy, observed):
                        assert (not np.isfinite(value)) if expected is None else value == expected
                arrays.append((x, y)); coordinate_pairs += len(x)
            if case['name'] == 'pressure':
                continue
            audit = next(r for r in analysis['rows'] if r['case'] == case['name'])
            x, values = arrays[2]; upper_x, upper_y = arrays[3]; lower_x, lower_y = arrays[4]
            valid = np.isfinite(upper_x) & np.isfinite(upper_y)
            coordinates = [Decimal.from_float(float(v)) for v in upper_x[valid]]
            radii = [(Decimal.from_float(float(a))-Decimal.from_float(float(b)))/2
                     for a, b in zip(upper_y[valid], lower_y[valid])]
            diameter = 2*max(radii)
            assert float(diameter) == audit['diameter_in_figure_units']
            # pi and the angle are constants, never inferred from a load value.
            factor = 2*Decimal.from_float(math.pi)*Decimal.from_float(math.sin(math.radians(2*audit['alpha_deg'])))/diameter
            differences = []
            for i, value in enumerate(values):
                if not np.isfinite(value):
                    assert audit['rows'][i]['status'] == 'unavailable'
                    continue
                if i+1 == len(radii):
                    assert value == 0. and audit['rows'][i]['status'] == 'terminal_zero_without_successor'
                    prediction = Decimal(0)
                else:
                    assert x[i] == upper_x[i] == lower_x[i]
                    prediction = factor*radii[i]*(radii[i+1]-radii[i])/(coordinates[i+1]-coordinates[i])
                error = abs(prediction-Decimal.from_float(float(value)))
                assert error < Decimal('2e-14'), (case['name'], i, error)
                differences.append(error); maximum = max(maximum, error)
            results.append(dict(case=case['name'], finite=len(differences),
                                maximum_decimal_error=str(max(differences))))
    assert coordinate_pairs == 1530 and sum(r['finite'] for r in results) == 183
    assert not any(n == 'openswing' or n.startswith('openswing.') for n in sys.modules)
    receipt = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
                   status='VERIFIED_ORIGINAL_MAT_AND_INDEPENDENT_DECIMAL_IDENTITY',
                   results=results, original_coordinate_pairs=coordinate_pairs,
                   maximum_decimal_error=str(maximum), source_pins=len(analysis['sources']),
                   analysis_sha256=sha(args.analysis), verifier_sha256=sha(Path(__file__)),
                   seconds=time.perf_counter()-start, peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                   production_imports=0, solver_calls=0, native_passes_added=0,
                   limits=dict(address_space_mib=512, cpu_seconds=15, wall_seconds=25, blas_threads=1))
    with args.output.open('x') as handle:
        json.dump(receipt, handle, indent=2); handle.write('\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
