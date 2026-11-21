# UA-2 chunked history archive

Updated 2026-11-02. The new storage layer preserves the complete retained UA-2
physical history in **252,500,385 bytes (240.8 MiB)**, compared with
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
| Independent physical chunks in the archive | 331 |
| Archive size relative to snapshot JSON | 5.98% |
| Scientific modules matching source, public and dist | 136/136 |
| Persisted browser bytes compared after reload | 252,500,385/252,500,385 |
| Browser physical states read with chunk checksums | 5,281/5,281 |
| Browser full-state and checkpoint hash samples | 12/12 |
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
write/read comparison batch is 2.562 seconds;
the sampled maximum heap is 158.9 MiB.
This is not total process RSS or a peak-heap measurement. The original producer's
final reporting error means its process RSS was not retained.

Standalone Chromium 145.0.7632.0 copies the archive into its
origin-private filesystem, reloads the page, verifies every copied byte in
bounded slices, and then reads every physical chunk. The largest serial read
batch is 0.963 seconds. Sampled JavaScript heap during
these reads reaches 63.1 MiB; browser
process RSS and copy-phase peak memory are not measured. Opening reads only
364,775 bytes for the header, index and
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
