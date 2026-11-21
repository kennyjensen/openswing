"""Recompute historical SA-2 physical values after adding airflow diagnostics.

The historical evidence retains its original sources. This separate record
checks unchanged physics and the extended rejection messages on current sources.
"""
import hashlib
import json
from pathlib import Path
import runpy
import time

ROOT = Path(__file__).resolve().parents[1]
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
baseline_path = ROOT/'docs/validation/sa2.json'
baseline = json.loads(baseline_path.read_text())
changed = []
for name, expected in baseline['source_sha256'].items():
    if digest(ROOT/name) != expected:
        changed.append(name)
assert changed == ['openswing/aero.py'], changed
helpers = runpy.run_path(str(ROOT/'scripts/verify-sa2.py'))
source_path = ROOT/'.reference/isae-sa2/SA_2.asw'
assert digest(source_path) == baseline['provenance']['files']['SA_2.asw']['sha256']
source = source_path.read_text()
cases = []
for index, old in enumerate(baseline['cases']):
    start = time.monotonic()
    current = helpers['outcome'](source, old['specification'])
    assert current['status'] == old['status'], (index, current)
    if current['status'] == 'computed':
        import numpy as np
        a, b = helpers['physical'](current['result']), helpers['physical'](old['result'])
        error = float(np.max(abs(a-b)/np.maximum(1., abs(b))))
        assert error < 1e-12, (index, error)
        record = dict(index=index, status='computed', physical_values_compared=a.size, maximum_scaled_difference=error)
    else:
        assert current['error'].startswith(old['error'])
        assert 'Maximum M_perp=' in current['error'] and 'body force point' in current['error']
        record = dict(index=index, status='rejected', error=current['error'])
    cases.append(record)
    print(index, current['status'], f'{time.monotonic()-start:.2f}s', flush=True)
files = [Path(__file__), ROOT/'scripts/verify-sa2.py', ROOT/'docs/validation/sa2-sources.json', *sorted((ROOT/'openswing').glob('*.py'))]
out = dict(baseline_sha256=digest(baseline_path), changed_baseline_sources=changed,
           source_sha256={str(p.relative_to(ROOT)): digest(p) for p in files}, cases=cases,
           scope='Historical SA-2 numerical outputs are recomputed on current sources. Rejections remain rejections; their messages now identify the local sample. This does not validate physical or ASWING accuracy.')
(ROOT/'docs/validation/section-airflow-regression.json').write_text(json.dumps(out,indent=2)+'\n')
