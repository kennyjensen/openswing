"""Extract stored numeric series from upstream MATLAB FIG files without MATLAB.

The saved labels are provenance, not independently verified classifications of
measurements versus predictions. Figures are data files; no code is executed.
"""
from pathlib import Path
import hashlib
import json
import runpy
import numpy as np
from scipy.io import loadmat

ROOT = Path(__file__).resolve().parents[1]


def series(value, location='root'):
    rows = []
    if isinstance(value, dict):
        properties = value.get('properties', {})
        if 'XData' in properties and 'YData' in properties:
            x, y = [np.asarray(properties[k]) for k in ['XData', 'YData']]
            if np.issubdtype(x.dtype, np.number) and np.issubdtype(y.dtype, np.number) and x.size == y.size:
                if np.iscomplexobj(x) or np.iscomplexobj(y):
                    raise ValueError('Complex figure data requires a separate convention')
                pairs = [[float(a) if np.isfinite(a) else None, float(b) if np.isfinite(b) else None]
                         for a, b in zip(x.ravel(), y.ravel())]
                rows.append(dict(location=location, type=str(value.get('type')),
                    label=str(properties.get('DisplayName', '')), xy=pairs,
                    nonfinite_coordinates=sum(a is None or b is None for a, b in pairs)))
        if 'children' in value:
            rows.extend(series(value['children'], location + '.children'))
    elif isinstance(value, (list, tuple, np.ndarray)):
        for i, child in enumerate(value):
            rows.extend(series(child, f'{location}[{i}]'))
    return rows


def main():
    fetch = runpy.run_path(str(ROOT / 'scripts/fetch-isae-validation.py'))
    cache = fetch['CACHE']
    manifest = json.loads((cache.parent / 'manifest.json').read_text())
    output = cache.parent / 'figure-series'
    output.mkdir(exist_ok=True)
    records = []
    for name, record in manifest['files'].items():
        if not name.endswith('.fig'):
            continue
        path = cache / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256']
        entry = dict(path=name, sha256=record['sha256'])
        try:
            data = loadmat(path, simplify_cells=True)
            rows = [row for key, value in data.items() if key.startswith('hgS_') for row in series(value, key)]
            if not rows:
                raise ValueError('No recognized stored HG series')
            target = output / (record['sha256'] + '.json')
            target.write_text(json.dumps(dict(source=entry, series=rows), indent=2) + '\n')
            entry.update(status='extracted', series=[dict(label=r['label'], samples=len(r['xy']),
                nonfinite_coordinates=r['nonfinite_coordinates']) for r in rows],
                extracted_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
        except (ValueError, NotImplementedError, OSError) as exc:
            entry.update(status='unavailable', reason=str(exc))
        records.append(entry)
    summary = dict(repository=manifest['repository'], revision=manifest['revision'],
        scope='Stored numeric figure series only; labels and setup require source verification before physical comparison.',
        figures=records, full_suite_validated=False)
    (ROOT / 'docs/validation/isae-figure-inventory.json').write_text(json.dumps(summary, indent=2) + '\n')
    print('Figures:', len(records), 'extracted:', sum(r['status'] == 'extracted' for r in records))


if __name__ == '__main__':
    main()
