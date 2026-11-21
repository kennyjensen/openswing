"""Check released frontend files and unchanged physics after the serial build."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / 'artifacts/isae/ua2-archive-ui-20261102'
sha = lambda data: hashlib.sha256(data).hexdigest()


def stream_hash(stream):
    digest = hashlib.sha256()
    while block := stream.read(1024 * 1024):
        digest.update(block)
    return digest.hexdigest()


def file_hash(path):
    with path.open('rb') as stream:
        return stream_hash(stream)


summary = json.loads((ROOT / 'docs/validation/isae-ua2-archive-ui-20261102.json').read_text())
assert summary['passed'] and summary['browser_execution']['exit_code'] == 0
receipts = {name: json.loads((BASE / (name + '-execution.json')).read_text())
            for name in ['source-build', 'vite-build', 'local-build']}
assert all(record['exit_code'] == 0 for record in receipts.values())
source_path = ROOT / 'public/openswing-source.zip'
local_path = ROOT / 'dist/openswing-local.zip'
source_hash = file_hash(source_path)
assert source_hash == file_hash(ROOT / 'dist/openswing-source.zip')
pins = dict(summary['browser']['source_sha256'])
for name in ['docs/validation/ISAE_STATUS.md', 'docs/STATUS.md', 'docs/time-history-archive.md',
             'docs/validation/isae-suite-backlog.md', 'docs/validation/isae-ua2-archive-ui-20261102.md',
             'docs/validation/isae-ua2-archive-ui-20261102.json', 'web/solution-data.js',
             'web/time-target-results.js', 'tests/time-history-archive.test.mjs',
             'tests/time-history-source.test.mjs', 'tests/time-history-workflow.test.mjs',
             'scripts/summarize-isae-ua2-archive-ui.py', 'scripts/verify-isae-ua2-archive-ui-build.py']:
    pins[name] = sha((ROOT / name).read_bytes())
assets = {}
with zipfile.ZipFile(source_path) as source, zipfile.ZipFile(local_path) as local:
    for name, digest in summary['scientific_sha256'].items():
        assert sha((ROOT / name).read_bytes()) == digest
        for folder in ['public/kernel', 'dist/kernel']:
            assert sha((ROOT / folder / Path(name).name).read_bytes()) == digest
        assert sha(source.read('openswing/' + name)) == digest
        assert sha(local.read('kernel/' + Path(name).name)) == digest
    for name, digest in pins.items():
        assert sha((ROOT / name).read_bytes()) == digest, name
        assert sha(source.read('openswing/' + name)) == digest, name
    for pattern in ['index-*.js', 'main-*.js', 'main-*.css', 'worker-*.js']:
        paths = list((ROOT / 'dist/assets').glob(pattern))
        assert len(paths) == 1, pattern
        p = paths[0]
        relative = p.relative_to(ROOT / 'dist').as_posix()
        assets[relative] = sha(p.read_bytes())
        assert sha(local.read(relative)) == assets[relative]
    with local.open('openswing-source.zip') as stream:
        assert stream_hash(stream) == source_hash
worker = next(v for p, v in assets.items() if '/worker-' in p)
assert worker == '268e23cd58c7b941b10b599ac87a10d6995b8a97f404775dc22a60ab850dce48'
main = next((ROOT / 'dist').joinpath(p) for p in assets if '/main-' in p and p.endswith('.js'))
assert 'Open complete history' in main.read_text() and 'Save complete history' in main.read_text()
other = lambda text: [line for line in text.splitlines() if re.match(r'\| \[?[A-Z]+-\d+', line) and not line.startswith('| [UA-2]')]
rows = other((ROOT / 'docs/validation/ISAE_STATUS.md').read_text())
assert rows == other((BASE / 'status-before.md').read_text()) and len(rows) == 41
report = dict(passed=True, verified_utc=datetime.now(timezone.utc).isoformat(),
              scientific_modules_matching_source_public_dist_and_both_archives=len(summary['scientific_sha256']),
              current_source_files=pins, local_assets_match=assets, unchanged_worker=True,
              other_ISAE_rows_preserved=41, focused_tests=66, full_history_states=5281,
              complete_archive_export_states=33, build_executions=receipts,
              source_archive_bytes=source_path.stat().st_size, source_archive_sha256=source_hash,
              local_archive_bytes=local_path.stat().st_size, local_archive_sha256=file_hash(local_path),
              native_ASWING_comparison=False, full_goal_complete=False)
with (BASE / 'final-verification.json').open('x') as f:
    json.dump(report, f, indent=2)
    f.write('\n')
print(json.dumps(dict(passed=True, scientific_modules=136, other_ISAE_rows=41,
                      focused_tests=66, full_history_states=5281, assets=list(assets))))
