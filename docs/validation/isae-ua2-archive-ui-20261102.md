# UA-2 complete histories in the workbench

Updated 2026-11-02. Complete-history archives are connected to the workbench.
The retained **5,281-state** UA-2 case opens and plots lift in
**0.95 seconds** in this Chromium replay,
reading only the display index, root metadata and first physical chunk
(4,163,619 bytes). Every state is retained.
This is a frontend/storage change: all **136 scientific modules**, numerical
tolerances, UA scientific results and native-ASWING comparison counts are unchanged.

| Check | Result |
|---|---:|
| Indexed lift samples, exact binary64 comparison | 5,281/5,281 |
| Earth-Z samples from all physical chunks, exact binary64 comparison | 5,281/5,281 |
| Rendered point labels checked for both quantities | 10,562/10,562 |
| Selected full-state and checkpoint hash pairs | 12/12 |
| Rapid six-selection burst | 2 physical chunk reads; latest selection wins |
| Checkpoint continuation and complete archive export | 33/33 states equal |
| Distribution overlay, envelope and both CSV exports | Exact against retained array calculation |
| Small JSON project save/open and runtime Undo load | Pass; archived state 7 restored |
| Truncated archive | Rejected; previous workspace retained |
| Focused history/storage/project tests | 66/66 |

The optional display index adds about 2.2 MB to the previously verified archive:
the indexed file is **254,675,073 bytes**. All compressed physical
records and original root metadata remain byte-identical to the earlier storage
proof, which compared 5,281 complete states and 660 checkpoints. The display
cache contains scalar values and descriptions only; a selected state always
comes from a complete physical record. Known cache entries are cross-checked
when their physical chunks are accessed. Older archives remain readable.

The first extraction of an unindexed quantity still scans the entire history:
Earth-Z takes **96.1 seconds** in this replay.
The interface reports progress, supports cancellation on quantity changes, and
caches up to four additional scalar curves. No state is interpolated or dropped.
Opening samples 42.9 MiB of JavaScript heap;
the post-scan sample is 37.9 MiB. These are
samples, not peak memory or process RSS. Chromium runs with a 192 MiB V8 heap cap.
Desktop/mobile plots were inspected; the 390-pixel viewport has no horizontal
overflow. Other browsers and current WASM startup are not validated here.

The small workflow uses the actual **Save complete history**, file import,
selected-checkpoint continuation, project and Undo load handlers. The first
archive contains 17 states in 1,179,117 bytes; the continued
archive contains 33 states in 2,032,060 bytes. All exported
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
