"""Inventory every upstream case and audit literal .asw parsing, without solves.

Parsing or lossless export is not a claim of physical validation. Each case
retains a separate comparison status, including folders with no model files.
"""
from pathlib import Path, PurePosixPath
from collections import Counter
import argparse
import hashlib
import json
import os
import re
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('OPENSWING_KERNEL', ROOT))
sys.path.insert(0, str(KERNEL))
from openswing.asw import parse_asw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=str(ROOT/'docs/validation/isae-suite-inventory.json'))
    args = parser.parse_args()
    source = runpy.run_path(str(ROOT / 'scripts/fetch-isae-validation.py'))
    cache = source['CACHE']
    manifest = json.loads((cache.parent / 'manifest.json').read_text())
    tree = json.loads((cache.parent / 'upstream-tree.json').read_text())
    cases = []
    for row in tree['tree']:
        parts = PurePosixPath(row['path']).parts
        family = re.match(r'(SA - \d|UA - \d|AP-\d|P-\d|AE-\d|FFWT-\d)', parts[-1])
        if row['type'] == 'tree' and ((len(parts) == 3 and family) or
                (len(parts) == 2 and parts[-1].startswith('CASE - ST'))):
            files = {name: spec for name, spec in manifest['files'].items()
                     if name.startswith(row['path'] + '/')}
            counts = Counter(PurePosixPath(name).suffix.lower() for name in files)
            match = re.search(r'(SA|UA|AP|P|ST|AE|FFWT)[ -]*(\d+)', parts[-1])
            case_id = match[1] + '-' + match[2]
            history = {'SA-1': 'sa1.json', 'SA-2': 'sa2.json'}.get(case_id)
            current = {'SA-1':'isae-sa1-current.json','SA-2':'isae-sa2-current.json',
                       'SA-3':'isae-sa34.json','SA-4':'isae-sa34.json','SA-5':'isae-sa5.json',
                       'SA-7':'isae-tandem.json','SA-8':'isae-tandem.json','P-1':'isae-p1.json','ST-5':'isae-st5.json','ST-3':'isae-st3.json'}.get(case_id)
            if current and not (ROOT/'docs/validation'/current).exists():
                current = None
            cases.append(dict(id=case_id, name=parts[-1], path=row['path'],
                file_counts=dict(counts), model_paths=[n for n in files if n.endswith('.asw')],
                numerical_comparison='scoped_comparison_recorded' if current else ('historical_partial' if history else 'not_yet_assessed'),
                current_evidence=current, prior_evidence=history,
                limitation=None if counts['.asw'] else 'No .asw model in this case folder; report/source reconstruction needs review.'))
    parsed = []
    for name, record in manifest['files'].items():
        if not name.endswith('.asw'):
            continue
        data = (cache / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == record['sha256'], name
        entry = dict(path=name, sha256=record['sha256'])
        try:
            literal = data.decode('utf-8-sig')
            model = parse_asw(literal)
            unchanged = model.dumps() == literal
            entry.update(status='parsed' if unchanged else 'roundtrip_mismatch',
                         diagnostics=model.diagnostics, beams=len(model.beams),
                         unchanged_text_roundtrip=unchanged)
        except Exception as exc:
            entry.update(status='rejected', error=type(exc).__name__ + ': ' + str(exc))
        parsed.append(entry)
    result = dict(repository=manifest['repository'], revision=manifest['revision'],
        scope='All 41 case folders and every .asw input in the pinned repository. Parsing only; physical validation is tracked separately.',
        kernel_modules={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((KERNEL / 'openswing').glob('*.py'))},
        total_files=len(manifest['files']), case_families=len(cases), model_files=len(parsed),
        parse_counts=dict(Counter(row['status'] for row in parsed)),
        missing_case='SA-9 is absent; the upstream README reports it lost.',
        cases=cases, models=parsed, full_suite_validated=False)
    path = Path(args.output)
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['case_families', 'model_files', 'parse_counts', 'full_suite_validated']}, indent=2))
    for entry in parsed:
        if entry['status'] != 'parsed':
            print(entry['path'], entry.get('error', entry['status']))


if __name__ == '__main__':
    main()
