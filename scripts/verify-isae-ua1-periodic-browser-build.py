"""Verify the released evidence and unchanged app/kernel after UA-1 validation."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/isae/ua1-incidence-periodic-browser-20261102-r1'


def stream_hash(stream):
    h = sha256()
    while block := stream.read(1024 * 1024):
        h.update(block)
    return h.hexdigest()


def digest(path):
    with path.open('rb') as stream:
        return stream_hash(stream)


plan = json.loads((BASE / 'plan.json').read_text())
summary = json.loads((ROOT / 'docs/validation/isae-ua1-incidence-periodic-browser-20261102.json').read_text())
assert summary['passed'] and all(summary['checks'].values()) and len(summary['checks']) == 14
assert summary['snapshots'] == 2561 and summary['accepted_steps'] == 2560 and summary['rejected_steps'] == 0
for name, value in summary['source_sha256'].items():
    assert digest(ROOT / name) == value, name
receipts = {name: json.loads((BASE / (name + '-execution.json')).read_text())
            for name in ['production', 'audits', 'focused-tests', 'source-build', 'local-build']}
assert all(value['exit_code'] == 0 for value in receipts.values())
science = {name: value for name, value in plan['source_sha256'].items() if name.startswith('openswing/')}
assert len(science) == 136
source_file, local_file = ROOT / 'public/openswing-source.zip', ROOT / 'dist/openswing-local.zip'
source_hash = digest(source_file)
assert source_hash == digest(ROOT / 'dist/openswing-source.zip')
paths = [ROOT / 'docs/validation/ISAE_STATUS.md', ROOT / 'docs/STATUS.md', ROOT / 'docs/validation/isae-suite-backlog.md',
         ROOT / 'docs/validation/isae-ua1-incidence-periodic-browser-20261102.md',
         ROOT / 'docs/validation/isae-ua1-incidence-periodic-browser-20261102.json',
         *sorted((ROOT / 'scripts').glob('*isae-ua1*browser*'))]
current = {str(path.relative_to(ROOT)): digest(path) for path in paths}
assets = json.loads((ROOT / 'artifacts/isae/ua2-archive-ui-20261102/final-verification.json').read_text())['local_assets_match']
with zipfile.ZipFile(source_file) as source, zipfile.ZipFile(local_file) as local:
    for name, value in science.items():
        assert digest(ROOT / name) == value
        for folder in ['public/kernel', 'dist/kernel']:
            assert digest(ROOT / folder / Path(name).name) == value
        assert sha256(source.read('openswing/' + name)).hexdigest() == value
        assert sha256(local.read('kernel/' + Path(name).name)).hexdigest() == value
    for name, value in current.items():
        assert sha256(source.read('openswing/' + name)).hexdigest() == value
    for name, value in assets.items():
        assert digest(ROOT / 'dist' / name) == value
        assert sha256(local.read(name)).hexdigest() == value
    with local.open('openswing-source.zip') as stream:
        assert stream_hash(stream) == source_hash
other = lambda text: [line for line in text.splitlines() if re.match(r'\| \[?[A-Z]+-\d+', line) and not line.startswith('| [UA-1]')]
rows = other((ROOT / 'docs/validation/ISAE_STATUS.md').read_text())
assert rows == other((BASE / 'status-before.md').read_text()) and len(rows) == 41
result = dict(passed=True, verified_utc=datetime.now(timezone.utc).isoformat(),
              runtime_checks=1, gates=14, audited_unique_snapshots=2561,
              scientific_modules_matching_source_public_dist_and_both_archives=136,
              other_ISAE_rows_preserved=41, unchanged_app_assets=assets,
              current_source_files=current, terminal_executions=receipts,
              source_archive_bytes=source_file.stat().st_size, source_archive_sha256=source_hash,
              local_archive_bytes=local_file.stat().st_size, local_archive_sha256=digest(local_file),
              new_physical_conditions=0, native_ASWING_comparison=False, full_goal_complete=False)
with (BASE / 'final-verification.json').open('x') as stream:
    json.dump(result, stream, indent=2)
    stream.write('\n')
print(json.dumps(dict(passed=True, runtime_checks=1, gates=14, snapshots=2561,
                      scientific_modules=136, other_ISAE_rows=41)))
