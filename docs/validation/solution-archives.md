# Computed-solution archives

OpenSwing project version 2 stores named computed solutions separately from
editable cases. The complete original ASWING objective remains unchanged;
these records do not implement ASWING's binary `.state` format or its `.set`
and `.pnt` companion formats.

## Record and restoration

A record contains the exact primary calculation request and result, its ASW
source and editable configuration, the current result selectors, and any saved
ROM, stability sweep, sampled flow field and Bode comparison curves. A time
result retains every physical snapshot and restart context. A modal result
retains its complex modes and base; frequency results retain all samples and
gaps. External Bode curves retain their original grids, unit conversions and
visibility. Records are owned copies; subsequent case edits do not change them.

The worker records SHA-256 hashes of its 55 loaded Python modules and the
reported Python, Pyodide, NumPy and SciPy versions. A numerical fingerprint
covers those records. A separate canonical SHA-256 checksum covers the analysis
kind, configuration, primary and supplementary results, selectors and provenance.
Names, record IDs and creation dates are metadata outside the numerical checksum.
The checks detect inconsistent or modified data; they are not signatures or
proof of physical validity. Archives contain results and provenance, not an
embedded executable copy of the historical kernel.

Opening a solution inspects its saved model and restores the stored result
without a new physical solve. Model inspection and spline previews may run to
reconstruct the editor. The UI labels matching or different recorded numerical
versions. New calculations use the current kernel. Frequency handles refer to
objects owned by one worker and are deliberately not serialized; adding new
samples requires a fresh analysis. Stored physical time checkpoints remain
available for a checked continuation. A continued history records half-open
snapshot ranges for each retained numerical origin; branching clips these
ranges and a new segment records the current worker. Old snapshots are never
relabeled as having been computed by the new kernel.

Supplementary setup is restored before its results, and dependent output
selectors afterward. Failed application restores the preceding inputs and
computed solution. Opening a solution can be undone. Persistent writes and
undo use IndexedDB revision checks to reject conflicting writes from other
tabs. Import, reload, startup and durable undo verify all archive checksums and
fingerprints before adopting a project. Verification happens before the write
transaction so a failed undo cannot replace the stored project.

## Verification

The browser workflows use real packaged-WASM calculations and disable network
access after local initialization. They compare complete exported data before
and after restoration and observe worker requests to exclude new analyses.
Independent mechanical checks use the original spring example: mass 2, stiffness
500 and viscous damping 10 in SI units. Its poles are
`-2.5 ± i sqrt(243.75)` and its tip displacement per unit engine force is
`1 / (500 - 2 omega^2 + 10 i omega)`.

Coverage includes:

- Mounted and rigid steady results, immutable archives after editing/removing
  cases, reload, rename/delete/undo and desktop/mobile layouts.
- All 55 loaded source hashes and the independently recomputed numerical
  fingerprint; changed source/runtime records are detected.
- Bode responses, external comparison grids/gaps and identical comparison CSV,
  saved flow samples, selected frequency/station/phase and absent live handles.
- Modal complex data, ROM matrices and acceleration feedthrough, root sweeps,
  supplementary output selectors and archives of an inspected sweep point.
- Complete time histories, selected snapshots and Earth views, identical history
  CSV and physical checkpoints, followed by a real continuation.
- Vacuum modal bases and geometry, version-1 migration, different numerical
  versions, checksum rejection, renderer rollback and corrupted persistent
  reload/startup/undo.
- Existing editable-case, controller, weighted-allocation, cross-tab conflict,
  rollback and storage-failure workflows.

All **38 JavaScript tests and 13 browser workflows passed** on the final source.
`solution-archives.json` records the 176 source identities, tested asset hashes
and terminal counts; the corresponding `docs/STATUS.md` entry records release
checks. The native numerical kernel is
unchanged in this increment; its existing independent wake-core study is usable
only while all of its recorded source/runtime hashes still match. Browser
archive checks are not a new aircraft-level physical validation campaign.

## Reproduce

```sh
node --test tests/*.test.mjs
npm run build
npm run test:browser -- tests/browser/solutions.spec.js tests/browser/projects.spec.js tests/browser/project-controller.spec.js
```

The same-origin runtime is packaged in the local application. Start its static
server before setting `OPENSWING_BASE_URL`; the Playwright configuration can also
start the development server when that variable is omitted.
