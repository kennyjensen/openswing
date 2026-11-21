"""Pack the frozen AE-1 sweep and its saved-output audit; no physics calls."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    assert not args.output.exists(), 'Inspect an existing archive before replacing it.'
    plan = json.loads((args.stage/'native/plan.json').read_text())
    run = json.loads((args.stage/'native/manifest.json').read_text())
    assert run['status'] != 'running'
    audit = json.loads((args.stage/'audit.json').read_text())
    assert audit['status'] == 'PASS'
    contents = {}

    def add(path, name=None, expected=None):
        path = Path(path)
        name = name or path.relative_to(ROOT).as_posix()
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
        raw = path.read_bytes()
        if expected is not None:
            assert digest(raw) == expected, 'Frozen dependency changed: '+str(path)
        if name in contents:
            assert contents[name] == raw
        contents[name] = raw

    for name, expected in plan['source_sha256'].items():
        add(ROOT/name, name, expected)
    scope = json.loads((args.stage/'source-scope.json').read_text())
    for item in scope['direct_input_pins']:
        add(Path(item['path']), expected=item['sha256'])
    for pattern in ('scripts/*isae-ae1*.py', 'scripts/test-isae-ae1-browser.mjs',
                    'scripts/isae_ae1.py', 'tests/test_isae_ae1.py',
                    'docs/validation/isae-ae1-sweep.*',
                    'docs/validation/isae-ae1-sweep-mesh.*',
                    'docs/validation/isae-ae1-source-scope.*',
                    'docs/validation/isae-ae1-sweep-audit.json',
                    'docs/validation/isae-ae1-sweep-execution.json',
                    'docs/validation/isae-ae1-browser*.json',
                    'docs/validation/isae-ae1-browser*.md',
                    'examples/pazy-isae-ae1-project.json', 'web/plot-colors.js'):
        for path in ROOT.glob(pattern):
            add(path)
    # Capture exact numerical rows, output, preparation failures and browser
    # attempts. The archive/replay itself is deliberately not recursive.
    for path in sorted(args.stage.rglob('*')):
        relative = path.relative_to(args.stage)
        if (path.is_file() and relative.parts[0] not in ('archive-replay', 'archive')
                and not relative.name.startswith('archive-')
                and path.suffix not in ('.zip', '.pyc') and '__pycache__' not in relative.parts):
            add(path, 'evidence/'+relative.as_posix())
    contents['REPLAY.txt'] = (
        'AE-1 full sweep evidence. Extract into a fresh directory.\n'
        'Use Python 3; the independent saved-output audit needs only stdlib.\n'
        'From the extracted directory run:\n\n'
        'python3 -I -B scripts/check-isae-ae1-sweep.py '
        '--run evidence/native --source-scope evidence/source-scope.json '
        '--report docs/validation/isae-ae1-sweep.json '
        '--report-csv docs/validation/isae-ae1-sweep.csv --output replay-audit.json\n\n'
        'Historical absolute paths remain provenance; the checker resolves '
        'frozen dependencies within this extracted root. No new solves run.\n'
        'Passing this audit checks saved numerical evidence, not experimental '
        'agreement or stability. See the included report for limitations.\n'
    ).encode()
    manifest = {name:dict(bytes=len(raw), sha256=digest(raw))
                for name, raw in sorted(contents.items())}
    contents['CONTENTS.json'] = (json.dumps(manifest, indent=2)+'\n').encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, raw in sorted(contents.items()):
            item = zipfile.ZipInfo(name, date_time=(2026, 10, 25, 0, 0, 0))
            item.compress_type = zipfile.ZIP_STORED if name.endswith(('.gz', '.png')) else zipfile.ZIP_DEFLATED
            archive.writestr(item, raw)
    with zipfile.ZipFile(args.output) as archive:
        assert set(archive.namelist()) == set(contents)
        for name, raw in contents.items():
            assert archive.read(name) == raw
    print(json.dumps(dict(path=str(args.output), bytes=args.output.stat().st_size,
                          sha256=digest(args.output.read_bytes()), members=len(contents),
                          all_member_hashes_pass=True), indent=2))


if __name__ == '__main__':
    main()
