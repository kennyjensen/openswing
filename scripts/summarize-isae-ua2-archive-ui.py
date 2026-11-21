"""Publish the bounded workbench replay, without adding scientific passes."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / 'artifacts/isae/ua2-archive-ui-20261102'
DOC = ROOT / 'docs/validation/isae-ua2-archive-ui-20261102.md'
read = lambda name: json.loads((BASE / name).read_text())
sha = lambda data: hashlib.sha256(data).hexdigest()
browser, index, reference, tests = [read(n) for n in
    ['browser-03.json', 'index.json', 'reference.json', 'focused-tests-execution.json']]
assert browser['passed'] and browser['full_history'] and index['passed'] and reference['passed']
assert browser['opened']['count'] == index['snapshots'] == reference['snapshots'] == 5281
assert browser['opened']['statistics']['recordsRead'] == 2
assert browser['complete_exported_states'] == browser['undo']['count'] == 33
assert browser['undo']['archived'] and browser['undo']['index'] == 7
assert tests['passed_tests'] == 66 and tests['exit_code'] == 0
assert read('browser-03-execution.json')['exit_code'] == read('index-execution.json')['exit_code'] == 0
assert read('browser-01-execution.json')['exit_code'] == read('browser-02-execution.json')['exit_code'] == 1
for name, digest in browser['source_sha256'].items():
    assert sha((ROOT / name).read_bytes()) == digest, name
for name, digest in index['source_sha256'].items():
    assert sha((ROOT / name).read_bytes()) == digest, name
assert reference['script_sha256'] == sha((ROOT / 'scripts/collect-isae-ua2-ui-reference.py').read_bytes())
assert reference['input_sha256'] == index['input_sha256']
for column, name in enumerate(reference['columns']):
    assert sha(b''.join(struct.pack('<d', row[column]) for row in reference['rows'])) == reference['float64_little_endian_sha256'][name]
old = json.loads((ROOT / 'artifacts/isae/ua2-history-archive-20261102/archive.json').read_text())
for name, digest in old['scientific_sha256'].items():
    for p in [ROOT / name, ROOT / 'public/kernel' / Path(name).name, ROOT / 'dist/kernel' / Path(name).name]:
        assert sha(p.read_bytes()) == digest, p
assert len(old['scientific_sha256']) == 136
summary = dict(passed=True, updated_utc=datetime.now(timezone.utc).isoformat(), browser=browser,
               index=index, focused_tests=tests, browser_execution=read('browser-03-execution.json'),
               original_incomplete_attempts=[read('browser-01-execution.json'), read('browser-02-execution.json')],
               independent_scalar_reference=dict(path=str((BASE / 'reference.json').relative_to(ROOT)),
                    sha256=sha((BASE / 'reference.json').read_bytes()), snapshots=5281,
                    float64_little_endian_sha256=reference['float64_little_endian_sha256'],
                    note='Completed collector artifact checked against the index input pins, current collector source and recalculated column digests. Its original terminal receipt was not observed; this summary does not invent one.'),
               scientific_sha256=old['scientific_sha256'], numerical_reexecution=False,
               native_ASWING_comparison=False, large_project_attachments=False, full_goal_complete=False)
DOC.with_suffix('.json').write_text(json.dumps(summary, indent=2) + '\n')
DOC.write_text(f'''# UA-2 complete histories in the workbench

Updated 2026-11-02. Complete-history archives are connected to the workbench.
The retained **5,281-state** UA-2 case opens and plots lift in
**{browser['opened']['open_ms']/1000:.2f} seconds** in this Chromium replay,
reading only the display index, root metadata and first physical chunk
({browser['opened']['statistics']['bytesRead']:,} bytes). Every state is retained.
This is a frontend/storage change: all **136 scientific modules**, numerical
tolerances, UA scientific results and native-ASWING comparison counts are unchanged.

| Check | Result |
|---|---:|
| Indexed lift samples, exact binary64 comparison | 5,281/5,281 |
| Earth-Z samples from all physical chunks, exact binary64 comparison | 5,281/5,281 |
| Rendered point labels checked for both quantities | 10,562/10,562 |
| Selected full-state and checkpoint hash pairs | 12/12 |
| Rapid six-selection burst | {browser['rapid']['reads']} physical chunk reads; latest selection wins |
| Checkpoint continuation and complete archive export | 33/33 states equal |
| Distribution overlay, envelope and both CSV exports | Exact against retained array calculation |
| Small JSON project save/open and runtime Undo load | Pass; archived state 7 restored |
| Truncated archive | Rejected; previous workspace retained |
| Focused history/storage/project tests | 66/66 |

The optional display index adds about 2.2 MB to the previously verified archive:
the indexed file is **{index['archive_bytes']:,} bytes**. All compressed physical
records and original root metadata remain byte-identical to the earlier storage
proof, which compared 5,281 complete states and 660 checkpoints. The display
cache contains scalar values and descriptions only; a selected state always
comes from a complete physical record. Known cache entries are cross-checked
when their physical chunks are accessed. Older archives remain readable.

The first extraction of an unindexed quantity still scans the entire history:
Earth-Z takes **{browser['scanned']['seconds']:.1f} seconds** in this replay.
The interface reports progress, supports cancellation on quantity changes, and
caches up to four additional scalar curves. No state is interpolated or dropped.
Opening samples {browser['opened']['heap']/1048576:.1f} MiB of JavaScript heap;
the post-scan sample is {browser['scanned']['heap']/1048576:.1f} MiB. These are
samples, not peak memory or process RSS. Chromium runs with a 192 MiB V8 heap cap.
Desktop/mobile plots were inspected; the 390-pixel viewport has no horizontal
overflow. Other browsers and current WASM startup are not validated here.

The small workflow uses the actual **Save complete history**, file import,
selected-checkpoint continuation, project and Undo load handlers. The first
archive contains 17 states in {browser['saved_bytes']:,} bytes; the continued
archive contains 33 states in {browser['continued_bytes']:,} bytes. All exported
physical fields match, including internal method records and inherited contexts.
The browser's origin-private-file download fallback is exercised. The native
save-picker path has focused tests, not an interactive browser-picker test.

This is a retained-output replay, not a new integration or native-ASWING run.
A test-only worker adapter supplies recorded continuation output and serial
CPython model-inspection replies. Full-history display metadata and the small
fixture's workbench/request envelope are explicitly assembled for UI testing;
they are not claimed to reproduce an unavailable original workbench project.
The full archive is selected as a disk File and injected through the test hook;
the public file-import workflow is exercised with the small saved archive.

Two earlier attempts remain recorded as failures: they clicked Save or Undo
while the restored property editor was still loading, and the existing readiness
guard rejected the action. The final run waits for that guard to clear. No
solver settings, acceptance tolerances or physical outputs were changed.

Remaining: persistent large-archive project attachments, automatic durable
storage of continued segments, transactional references and durable undo/reload
recovery. Ordinary JSON projects retain their 64 MiB / 2,000,000-value limits;
larger histories must be kept as separate complete-history archives. First-time
unindexed scans remain costly. Broader UA frequency/amplitude/incidence coverage,
stall, UA-1 browser validation and native-ASWING provenance remain unfinished.

Evidence: [machine report](isae-ua2-archive-ui-20261102.json),
[format/API](../time-history-archive.md),
[browser replay](../../artifacts/isae/ua2-archive-ui-20261102/browser-03.json),
[terminal receipt](../../artifacts/isae/ua2-archive-ui-20261102/browser-03-execution.json),
[indexed payload identity](../../artifacts/isae/ua2-archive-ui-20261102/index.json),
[independent scalar reference](../../artifacts/isae/ua2-archive-ui-20261102/reference.json),
[replay script](../../scripts/test-isae-ua2-archive-workbench.mjs).
''')

paragraph = (f'The [complete-history workbench check](docs/validation/{DOC.name}) now opens and plots '
             f'all 5,281 lift samples in {browser["opened"]["open_ms"]/1000:.2f} s from the indexed archive. '
             'Full-state selection/playback, 33-state archive save/open/continuation, distribution CSVs, '
             'small JSON projects and runtime Undo load pass. All 66 focused tests pass. '
             f'A first unindexed-quantity scan still takes {browser["scanned"]["seconds"]:.1f} s with progress. '
             'Large project attachments and automatic durable segment storage remain unfinished. '
             'All 136 scientific modules and native comparison counts are unchanged.')
status = ROOT / 'docs/validation/ISAE_STATUS.md'
text = status.read_text()
text = re.sub(r'^The \[chunked archive proof\].*$', paragraph, text, count=1, flags=re.M)
old_end = 'The snapshot array alone is 4.22 GB and crosses the JSON limit by 84 states. The chunked archive preserves all 5,281 states / 660 checkpoints exactly in 252.5 MB, with complete standalone Chromium file persistence and chunk reads; 36 focused tests pass. Workbench integration, broader conditions and native provenance remain unfinished.'
new_end = ('The full 5,281-state physical history now works in the actual workbench through a 254.7 MB indexed archive. '
           f'Lift opens in {browser["opened"]["open_ms"]/1000:.2f} s; an unindexed-quantity scan takes {browser["scanned"]["seconds"]:.1f} s with progress. '
           'Complete state/checkpoint samples, 33-state archive save/open/continuation, distribution CSVs, small JSON project save/open and runtime Undo load pass; 66 focused tests pass. '
           'Large project attachments, automatic durable segment storage, broader conditions and native provenance remain unfinished.')
assert old_end in text or new_end in text
text = text.replace(old_end, new_end)
text = text.replace('Full-history UI performance, broader conditions and native provenance remain unfinished.',
                    'The subsequent workbench check below covers full-history UI use; broader conditions and native provenance remain unfinished.')
text = text.replace('the current 64 MiB archive limit is exceeded at **84 states**',
                    'the existing 64 MiB JSON-project limit is exceeded at **84 states** in this fixture')
text = text.replace('This reduces duplicate in-memory objects but leaves full-history persistence unfinished.',
                    'That earlier metadata-sharing increment did not provide complete-history persistence; the archive workbench follow-up is recorded below.')
other = lambda text: [line for line in text.splitlines() if re.match(r'\| \[?[A-Z]+-\d+', line) and not line.startswith('| [UA-2]')]
assert other(text) == other((BASE / 'status-before.md').read_text()) and len(other(text)) == 41
status.write_text(text)
status = ROOT / 'docs/STATUS.md'
text = re.sub(r'^The \[chunked archive proof\].*$', paragraph.replace('docs/validation/', 'validation/'), status.read_text(), count=1, flags=re.M)
text = text.replace('Full-history project persistence requires integrating the chunked store/archive;  the existing project limits remain unchanged.',
                    'Large histories now have separate complete-history archives; persistent project attachments remain unfinished and existing JSON-project limits remain unchanged.')
text = text.replace('Full physical-history loading, memory and archive saving remain unfinished; this adds no scientific or native comparison pass.',
                    'The later complete-history workbench check above extends this earlier scalar/segment milestone; neither adds a scientific or native comparison pass.')
text = text.replace('Full-history UI rendering, playback, memory and saving, broader conditions and native provenance remain unfinished; neither UA family nor the project is complete.',
                    'Full-history workbench checks are recorded above. Durable large-project storage, broader conditions and native provenance remain unfinished; neither UA family nor the project is complete.')
status.write_text(text)
backlog = ROOT / 'docs/validation/isae-suite-backlog.md'
text = backlog.read_text()
old_task = 'Next integrate joined-result metadata/provenance, plots, selection, playback, branching, save/export and project undo, then exercise the complete physical history in the actual workbench. Preserve every computed value; the scalar fixture and one complete segment do not establish full-history UI performance.'
new_task = (f'The [workbench follow-up]({DOC.name}) now checks the full physical history with indexed lift, '
            'complete selection/playback and a physical Earth-Z scan; small archive save/open/continuation, '
            'distribution exports, JSON projects and runtime Undo load pass. All 66 focused tests pass. '
            'Next implement durable large-project attachments and automatic segment storage with transactional references, '
            'reload recovery and persistent undo. Unindexed scans remain costly; no physical states are omitted.')
assert old_task in text or new_task in text
backlog.write_text(text.replace(old_task, new_task))
print(json.dumps(dict(passed=True, scientific_modules_unchanged=136, other_ISAE_rows_preserved=41,
                      full_history_states=5281, complete_continued_states=33, focused_tests=66)))
