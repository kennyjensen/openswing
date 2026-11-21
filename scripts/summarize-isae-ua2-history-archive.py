"""Reconcile the bounded UA-2 storage evidence without changing scientific counts."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / 'artifacts/isae/ua2-history-archive-20261102'
DOC = ROOT / 'docs/validation/isae-ua2-history-archive-20261102.md'


def read(name):
    return json.loads((BASE / name).read_text())


archive, browser, tests = read('archive.json'), read('browser.json'), read('focused-tests-execution.json')
assert archive['passed'] and browser['passed']
assert archive['snapshots'] == browser['snapshots'] == 5281
assert archive['exact_checkpoints'] == 660 and tests['passed_tests'] == 36 and tests['exit_code'] == 0
assert browser['persisted_bytes_verified'] == archive['archive']['bytes']
assert read('producer-execution.json')['exit_code'] == 1
assert read('assessment-execution.json')['exit_code'] == read('browser-execution.json')['exit_code'] == 0

size = archive['archive']['bytes']
summary = dict(updated_utc=datetime.now(timezone.utc).isoformat(), passed=True,
               scope='Storage-layer validation; not workbench/project integration or a new scientific comparison.',
               archive=archive, browser=browser, focused_tests=tests,
               assessment_execution=read('assessment-execution.json'), browser_execution=read('browser-execution.json'),
               interrupted_initial_attempt=read('attempt01/execution.json'),
               generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               full_history_UI_validation=False, native_ASWING_comparison=False, full_goal_complete=False)
DOC.with_suffix('.json').write_text(json.dumps(summary, indent=2) + '\n')
DOC.write_text(f'''# UA-2 chunked history archive

Updated 2026-11-02. The new storage layer preserves the complete retained UA-2
physical history in **{size:,} bytes ({size / 1048576:.1f} MiB)**, compared with
4,221,782,122 bytes for the ordinary snapshot JSON alone. No scientific result,
acceptance tolerance or solver equation changes. **Workbench integration remains
unfinished**: the existing save/load, playback, branching and project undo still
use their previous history representation and JSON limits.

| Storage check | Result |
|---|---:|
| Physical states compared field by field | **5,281/5,281** |
| Selected standalone checkpoints compared exactly | **660/660** |
| Focused storage / project tests | **36/36** |
| Source segments read serially | 330 |
| Independent physical chunks in the archive | {archive['archive']['chunks']} |
| Archive size relative to snapshot JSON | {100 * archive['size_ratio']:.2f}% |
| Scientific modules matching source, public and dist | 136/136 |
| Persisted browser bytes compared after reload | {browser['persisted_bytes_verified']:,}/{size:,} |
| Browser physical states read with chunk checksums | 5,281/5,281 |
| Browser full-state and checkpoint hash samples | {browser['full_state_and_checkpoint_hash_samples']}/12 |
| States written and reopened by the browser writer | 3/3 |

The archive stores all fields, including internal BDF predecessors, accepted
method inputs, endpoint records, unknown historical metadata and distinct
same-time states. The codec preserves signed zero and exact numeric values.
Repeated metadata is shared only by exact equality within a chunk. Integrity
checks cover the index and every accessed physical record. No simulation is
rerun, and nothing is thinned or reconstructed from neighboring public states.

The physical state array follows the actual continuation retention rule:
repeated joins are omitted and earlier snapshots retain their original context.
**This is a storage-layer fixture:** its root metadata deliberately remains the
unmodified final segment. It is not a complete joined workbench solution or
project envelope. Correct aggregate metadata, provenance, transactional project
references and undo retention remain part of integration.

The writer/reader run with a 192 MiB V8 heap cap. The largest recorded serial
write/read comparison batch is {archive['max_segment_seconds']:.3f} seconds;
the sampled maximum heap is {archive['sampled_max_heap_bytes'] / 1048576:.1f} MiB.
This is not total process RSS or a peak-heap measurement. The original producer's
final reporting error means its process RSS was not retained.

Standalone Chromium {browser['browser_version']} copies the archive into its
origin-private filesystem, reloads the page, verifies every copied byte in
bounded slices, and then reads every physical chunk. The largest serial read
batch is {browser['max_batch_seconds']:.3f} seconds. Sampled JavaScript heap during
these reads reaches {browser['sampled_max_JS_heap_bytes'] / 1048576:.1f} MiB; browser
process RSS and copy-phase peak memory are not measured. Opening reads only
{browser['opened']['statistics']['bytesRead']:,} bytes for the header, index and
metadata, with no physical chunks loaded. This is a storage browser test, **not
the full workbench UI or a new WASM solver validation**. Other browsers remain
untested for this archive path.

The tests include independently constructed files, corruption and truncation,
oversized decompression, invalid reference targets, prototype keys, internal
method states, same-time transitions, signed zero, independent checkpoint
copies, failed writes and an expanded-depth regression. One initial measurement
was interrupted to fix that depth boundary; it is not counted as a pass.

The complete producer compared all 5,281 states and 660 checkpoints successfully,
then exited **1** because its final check used the wrong packaged Python path.
That receipt and original script remain intact. The corrected assessment verifies
the completed serial comparison log, rechecks 12 selected states/checkpoints,
all 330 input file hashes, complete time index and root metadata, and the actual
136 source/public/dist module paths. No numerical output is regenerated and the
producer is not relabeled as exit 0.

Next: integrate the archive provider with result metadata/provenance, plots,
selection, playback, continuation/branching, save/export and project undo, then
measure a complete physical history in the actual app. Broader UA conditions,
stall and native-ASWING provenance remain unfinished. Neither UA family nor the
full project is complete.

Evidence: [machine summary](isae-ua2-history-archive-20261102.json),
[format and API](../time-history-archive.md),
[exact comparison assessment](../../artifacts/isae/ua2-history-archive-20261102/archive.json),
[browser persistence](../../artifacts/isae/ua2-history-archive-20261102/browser.json),
[original producer receipt](../../artifacts/isae/ua2-history-archive-20261102/producer-execution.json),
[assessment receipt](../../artifacts/isae/ua2-history-archive-20261102/assessment-execution.json),
[focused tests](../../artifacts/isae/ua2-history-archive-20261102/focused-tests-execution.json),
[serial comparison script](../../scripts/verify-isae-ua2-history-archive.mjs),
[assessment script](../../scripts/assess-isae-ua2-history-archive.mjs), and
[browser check](../../scripts/test-isae-ua2-history-archive-browser.mjs).
''')

paragraph = (f'The [chunked archive proof](docs/validation/{DOC.name}) now preserves all **5,281 states** '
             f'and **660 selected checkpoints** exactly in **{size / 1e6:.1f} MB**; all 36 focused tests pass. '
             'Standalone Chromium storage/reload verifies every persisted byte and reads every physical chunk. '
             'The archive code is not yet connected to workbench plots, save/load, playback or project undo. '
             'All 136 scientific modules and scientific/native counts remain unchanged.')
status = ROOT / 'docs/validation/ISAE_STATUS.md'
text = status.read_text()
if 'chunked archive proof' not in text:
    lines = text.splitlines()
    at = next(i for i, line in enumerate(lines) if line.startswith('The [full-history storage audit]'))
    lines[at+1:at+1] = ['', paragraph]
    text = '\n'.join(lines) + '\n'
old = 'Full snapshot JSON is 4.22 GB and exceeds the archive limit at 84 states; chunked persistence, broader conditions and native provenance remain unfinished.'
new = (f'The snapshot array alone is 4.22 GB and crosses the JSON limit by 84 states. The chunked archive preserves all 5,281 states / 660 checkpoints exactly in {size / 1e6:.1f} MB, with complete standalone Chromium file persistence and chunk reads; 36 focused tests pass. Workbench integration, broader conditions and native provenance remain unfinished.')
assert old in text or new in text
text = text.replace(old, new)
row = lambda line: re.match(r'\| \[?[A-Z]+-\d+', line) and not line.startswith('| [UA-2]')
before = (BASE / 'isae-status-before.md').read_text()
assert [line for line in before.splitlines() if row(line)] == [line for line in text.splitlines() if row(line)]
assert len([line for line in text.splitlines() if row(line)]) == 41
status.write_text(text)

status = ROOT / 'docs/STATUS.md'
text = status.read_text()
if 'chunked archive proof' not in text:
    text = text.replace('# Current implementation record\n', '# Current implementation record\n\n' +
                        paragraph.replace('docs/validation/', 'validation/') + '\n', 1)
text = text.replace('Updated 2026-11-01.', 'Updated 2026-11-02.', 1)
text = text.replace('Full-history persistence now requires a chunked store/archive;',
                    'Full-history project persistence requires integrating the chunked store/archive; ', 1)
status.write_text(text)

backlog = ROOT / 'docs/validation/isae-suite-backlog.md'
text = backlog.read_text()
old = 'Next implement a versioned chunked store/archive with bounded-memory loading, checksums, save/export and project undo, then exercise the complete physical history in the browser.'
new = (f'The [chunked archive proof]({DOC.name}) preserves all 5,281 states / 660 checkpoints exactly in {size / 1e6:.1f} MB; standalone Chromium verifies the entire persisted file after reload and reads every physical chunk. All 36 focused tests pass. Next integrate joined-result metadata/provenance, plots, selection, playback, branching, save/export and project undo, then exercise the complete physical history in the actual workbench.')
assert old in text or new in text
backlog.write_text(text.replace(old, new))
print(json.dumps(dict(passed=True,archive_bytes=size,exact_states=5281,other_ISAE_rows_preserved=41)))
