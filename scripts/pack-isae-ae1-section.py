"""Pack bounded section-slope and saved-load evidence without physics imports."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--section', type=Path, required=True)
    parser.add_argument('--loads', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'Archive already exists; inspect it before any replacement.'
    plan = json.loads((args.section/'native/plan.json').read_bytes())
    execution = json.loads((args.section/'native/manifest.json').read_bytes())
    audit = json.loads((args.section/'audit.json').read_bytes())
    assert execution['status'] == 'completed' and execution['final_provenance_verified']
    assert audit['passed'] and audit['complete'] and audit['numerical_gates_passed']
    baseline = json.loads((ROOT/'docs/validation/isae-ae1-sweep.json').read_bytes())
    loads = json.loads((ROOT/'docs/validation/isae-ae1-loads.json').read_bytes())
    assert loads['status'] == 'PASS'
    contents, sources = {}, {}

    def add(path, name=None, expected=None):
        path = Path(path).resolve()
        name = name or path.relative_to(ROOT).as_posix()
        relative = Path(name)
        assert not relative.is_absolute() and '..' not in relative.parts
        raw = path.read_bytes()
        if expected is not None:
            assert sha(raw) == expected, 'Frozen source changed: '+str(path)
        if name in contents:
            assert contents[name] == raw, 'Archive name collision: '+name
        contents[name] = raw
        sources[str(path)] = dict(bytes=len(raw), sha256=sha(raw))

    for name, expected in plan['source_sha256'].items():
        add(ROOT/name, name, expected)
    for item in loads['input_pins']:
        path = Path(item['path'])
        if path.is_relative_to(ROOT):
            add(path, expected=item['sha256'])
        else:
            relative = path.relative_to(args.baseline.resolve())
            add(path, 'evidence/baseline/'+relative.as_posix(), item['sha256'])
    required = [
        'scripts/check-isae-ae1-section.py', 'scripts/check-isae-ae1-sweep.py',
        'scripts/summarize-isae-ae1-section.py', 'scripts/analyze-isae-ae1-loads.py',
        'scripts/pack-isae-ae1-section.py', 'scripts/replay-isae-ae1-section.py',
        'scripts/plot-isae-ae1-section.py',
        'docs/validation/isae-ae1-section.json', 'docs/validation/isae-ae1-section.csv',
        'docs/validation/isae-ae1-section.md', 'docs/validation/isae-ae1-section.svg',
        'docs/validation/isae-ae1-section.png', 'docs/validation/isae-ae1-section-source.json',
        'docs/validation/isae-ae1-section-audit.json', 'docs/validation/isae-ae1-section-audit-selfcheck.json',
        'docs/validation/isae-ae1-section-execution.json',
        'docs/validation/isae-ae1-loads.json', 'docs/validation/isae-ae1-loads.md',
        'docs/validation/isae-ae1-loads-execution.json', 'docs/validation/isae-ae1-load-strips.csv',
        'docs/validation/isae-ae1-load-sections.csv',
        'docs/validation/isae-ae1-sweep.csv', 'docs/validation/isae-ae1-sweep-audit.json',
        'docs/validation/isae-ae1-sweep-execution.json',
        'docs/validation/isae-ae1-source-scope.json', 'docs/validation/isae-ae1-source-scope.md',
        'docs/validation/isae-ae1-mirror-source.json', 'docs/validation/isae-ae1-pilot-source-review.json',
    ]
    for name in required:
        add(ROOT/name)
    # Keep exact original preparations, rejected saved-data attempts and receipts.
    # Exclude packaging/replay products to avoid recursive archives.
    for stage, prefix in ((args.section, 'section'), (args.loads, 'loads')):
        for path in sorted(stage.rglob('*')):
            relative = path.relative_to(stage)
            if (path.is_file() and not relative.parts[0].startswith('archive')
                    and '__pycache__' not in relative.parts and path.suffix not in ('.zip', '.pyc')):
                add(path, 'evidence/'+prefix+'/'+relative.as_posix())
    wanted = {(s['refinement'], s['alpha_deg'], s['speed_m_s']) for s in plan['specifications']}
    wanted |= {(2, 0., 0.), (4, 0., 0.), (4, 5., 56.), (4, 7., 38.), (4, 7., 41.)}
    selected = [e for e in baseline['states'] if
                (e['specification']['refinement'], e['specification']['alpha_deg'],
                 e['specification']['speed_m_s']) in wanted]
    assert len(selected) == len(wanted) == 11
    for entry in selected:
        assert entry['status'] == 'computed'
        path = args.baseline/'cases'/entry['raw']['file']
        raw = path.read_bytes()
        assert len(raw) == entry['raw']['bytes'] and sha(raw) == entry['raw']['sha256']
        unpacked = gzip.decompress(raw)
        assert len(unpacked) == entry['raw']['uncompressed_bytes']
        assert sha(unpacked) == entry['raw']['uncompressed_sha256']
        add(path, 'evidence/baseline/cases/'+path.name, entry['raw']['sha256'])
    for name in ('plan.json', 'manifest.json'):
        add(args.baseline/name, 'evidence/baseline/'+name)
    selection = dict(scope='Eleven retained baseline states: eight section-diagnostic comparisons/zero states '
                          'plus three additional fine-mesh saved-load states. The full historical baseline '
                          'manifest is retained unchanged, but the other 175 baseline raw states are not in this bounded archive.',
                     selected_states=selected)
    contents['evidence/baseline/selection.json'] = (json.dumps(selection, indent=2)+'\n').encode()
    locations = dict(historical_roots=dict(repository=str(ROOT), section=str(args.section.resolve()),
                      loads=str(args.loads.resolve()), baseline_stage=str(args.baseline.resolve().parent)),
                     archive_roots=dict(repository='.', section='evidence/section', loads='evidence/loads',
                                        baseline_native='evidence/baseline'))
    contents['ARCHIVE-PATHS.json'] = (json.dumps(locations, indent=2)+'\n').encode()
    contents['README.txt'] = (
        'AE-1 section-slope sensitivity and saved-load evidence, 2026-10-25\n\n'
        'Extract into a fresh directory outside the historical source directories.\n'
        'Repository files retain their root-relative paths. External evidence is\n'
        'under evidence/section, evidence/loads and evidence/baseline. Historical\n'
        'absolute paths remain unchanged inside the original scientific records.\n\n'
        'Included numerical evidence: six new section-slope states, eight reused\n'
        'baseline states, and three additional 60-interval-per-half load states\n'
        '(5 deg at 56 m/s; 7 deg at 38 and 41 m/s). These are 17 unique raw files.\n'
        'The baseline manifest describes its original 186-state run; only the\n'
        'eleven baseline raw files in evidence/baseline/selection.json are included.\n\n'
        'From the extracted root, run the portable section audit with Python 3:\n\n'
        'python3 -I -B scripts/replay-isae-ae1-section.py\n\n'
        'This first verifies every member listed in CONTENTS.json, blocks reads\n'
        'from the historical repository/evidence directories and blocks NumPy or\n'
        'OpenSwing imports, then runs the saved-only section audit once. It writes\n'
        'replay-audit.json and replay-receipt.json and refuses existing outputs.\n'
        'CONTENTS.json lists all original members except itself. Subsequent replay\n'
        'outputs are not archive members. No aircraft equations or solves run.\n\n'
        'The equivalent saved-only audit command is:\n\n'
        'python3 -I -B scripts/check-isae-ae1-section.py '
        '--run evidence/section/native --baseline-run evidence/baseline '
        '--source-review evidence/section/source-review.json '
        '--report docs/validation/isae-ae1-section.json '
        '--report-csv docs/validation/isae-ae1-section.csv '
        '--output replay-audit.json\n\n'
        'Optional separate saved-load reconstruction (not part of the one section\n'
        'replay used to establish portability):\n\n'
        'python3 -I -B scripts/analyze-isae-ae1-loads.py '
        '--sweep docs/validation/isae-ae1-sweep.json '
        '--raw evidence/baseline/cases --output replay-loads\n\n'
        'Load replay output pins contain the new absolute paths; compare scientific\n'
        'values and CSVs rather than demanding byte-identical whole JSON reports.\n'
        'Historical failed load attempts and failed section preparation are retained\n'
        'with their exact source copies and receipts, not silently repaired.\n\n'
        'Passing numerical evidence checks does not establish experimental agreement,\n'
        'VLM reproduction, dynamic stability or broader validation coverage. See the\n'
        'included section, source and load reports for those limits.\n'
    ).encode()
    member_pins = {name:dict(bytes=len(raw), sha256=sha(raw)) for name, raw in sorted(contents.items())}
    contents['CONTENTS.json'] = (json.dumps(member_pins, indent=2)+'\n').encode()
    for path, expected in sources.items():
        raw = Path(path).read_bytes()
        assert len(raw) == expected['bytes'] and sha(raw) == expected['sha256'], 'Snapshot changed: '+path
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, raw in sorted(contents.items()):
            item = zipfile.ZipInfo(name, date_time=(2026, 10, 25, 0, 0, 0))
            item.compress_type = zipfile.ZIP_STORED if name.endswith(('.gz', '.png')) else zipfile.ZIP_DEFLATED
            archive.writestr(item, raw)
    with zipfile.ZipFile(args.output) as archive:
        assert len(archive.namelist()) == len(contents) and set(archive.namelist()) == set(contents)
        for name, raw in contents.items():
            assert archive.read(name) == raw
    print(json.dumps(dict(path=str(args.output), bytes=args.output.stat().st_size,
        sha256=sha(args.output.read_bytes()), members=len(contents), hashed_members=len(member_pins),
        all_member_hashes_pass=True, candidate_raw_states=6, baseline_raw_states=11,
        snapshots=len(sources)), indent=2))


if __name__ == '__main__':
    main()
