"""Verify the published study and unchanged solver in both download archives."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def stream_hash(stream):
    value = sha256()
    while block := stream.read(1024*1024):
        value.update(block)
    return value.hexdigest()


def digest(path):
    with path.open('rb') as stream:
        return stream_hash(stream)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--document', required=True)
    args = parser.parse_args()
    base = args.base.resolve()
    assert base.is_relative_to(ROOT/'artifacts/isae')
    assert re.fullmatch(r'isae-ua1-[a-z0-9-]+', args.document)
    document = ROOT/'docs/validation'/(args.document+'.json')
    report = json.loads(document.read_text())
    plan = json.loads((base/'plan.json').read_text())
    assert len(report['checks']) == 14 and report['passed'] == all(report['checks'].values())
    for name, value in report['report_source_sha256'].items():
        assert digest(ROOT/name) == value, name
    receipts = {name: json.loads((base/(name+'-execution.json')).read_text())
                for name in ['production', 'audits', 'combine', 'summary', 'source-build', 'local-build']}
    assert all(value['exit_code'] == 0 for name, value in receipts.items() if name != 'combine')
    assert receipts['combine']['exit_code'] == (0 if report['passed'] else 1)
    science = {name: value for name, value in plan['source_sha256'].items() if name.startswith('openswing/')}
    assert len(science) == 136
    paths = [ROOT/'docs/validation/ISAE_STATUS.md', ROOT/'docs/STATUS.md', ROOT/'docs/validation/isae-suite-backlog.md',
             document, document.with_suffix('.md'), ROOT/'scripts/isae_ua1_periodic_study.py',
             ROOT/'scripts/run-isae-ua1-periodic-study.py', ROOT/'scripts/summarize-isae-ua1-periodic-study.py',
             ROOT/'scripts/audit-isae-ua1-periodic-study.py', ROOT/'scripts/isae_ua1_periodic_boundary.py',
             Path(__file__).resolve(), ROOT/'tests/test_isae_ua1_periodic_study.py',
             ROOT/'tests/test_isae_ua1_periodic_boundary.py']
    current = {str(path.relative_to(ROOT)): digest(path) for path in paths}
    source_file, local_file = ROOT/'public/openswing-source.zip', ROOT/'dist/openswing-local.zip'
    source_hash = digest(source_file)
    assert source_hash == digest(ROOT/'dist/openswing-source.zip')
    previous = ROOT/'artifacts/isae/ua1-incidence-periodic-browser-20261102-r1/final-verification.json'
    assets = json.loads(previous.read_text())['unchanged_app_assets']
    with zipfile.ZipFile(source_file) as source, zipfile.ZipFile(local_file) as local:
        for name, value in science.items():
            assert digest(ROOT/name) == value
            for folder in ['public/kernel', 'dist/kernel']:
                assert digest(ROOT/folder/Path(name).name) == value
            assert sha256(source.read('openswing/'+name)).hexdigest() == value
            assert sha256(local.read('kernel/'+Path(name).name)).hexdigest() == value
        for name, value in current.items():
            assert sha256(source.read('openswing/'+name)).hexdigest() == value
        for name, value in assets.items():
            assert digest(ROOT/'dist'/name) == value
            assert sha256(local.read(name)).hexdigest() == value
        with local.open('openswing-source.zip') as stream:
            assert stream_hash(stream) == source_hash
    others = lambda text: [line for line in text.splitlines() if re.match(r'\| \[?[A-Z]+-\d+', line) and not line.startswith('| [UA-1]')]
    rows = others((ROOT/'docs/validation/ISAE_STATUS.md').read_text())
    assert rows == others((base/'status-before.md').read_text()) and len(rows) == 41
    result = dict(passed=True, study_passed=report['passed'], verified_utc=datetime.now(timezone.utc).isoformat(),
        audited_unique_snapshots=report['audited_unique_snapshots'], unchanged_scientific_modules=136,
        other_ISAE_rows_preserved=41, unchanged_app_assets=assets, current_source_files=current,
        terminal_executions=receipts, source_archive_bytes=source_file.stat().st_size,
        source_archive_sha256=source_hash, local_archive_bytes=local_file.stat().st_size,
        local_archive_sha256=digest(local_file), full_goal_complete=False)
    with (base/'final-verification.json').open('x') as stream:
        stream.write(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed=True, study_passed=report['passed'], scientific_modules=136,
                         other_ISAE_rows_preserved=41)), flush=True)


if __name__ == '__main__':
    main()
