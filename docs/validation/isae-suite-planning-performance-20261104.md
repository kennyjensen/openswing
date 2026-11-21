# ISAE planning performance

2026-11-04. A serial planning-only profile for the six registered ST3 modal
jobs decreased from **47.34 to 38.97 seconds**, a **17.7% reduction** on this
device. This is one before/after measurement with profiler overhead, not a
general solver speedup estimate.

| Profile measure | Before | After |
|---|---:|---:|
| Complete profiled invocation | 47.34 s | 38.97 s |
| Catalog construction, excluding module import | 36.36 s | 27.86 s |
| File metadata recording | 9.08 s | 4.00 s |
| Calls to the model parser | 279 | 212 |
| Calls to `stat` across the invocation | 8,277 | 5,738 |

The catalog now uses one filesystem stat per source-file record. After each
model independently passes its original length, SHA256 and Git blob SHA1
checks, identical raw bytes can reuse a parse result from the same catalog
build. The archive has 279 model files with 212 distinct byte identities.
The cache stores copied diagnostics, not mutable model objects, and is discarded
after each build. BOM/newline differences retain separate byte identities.

The complete before/after catalogs are **byte-for-byte identical**, including
all 41 families, 2,539 files, 279 model integrity checks, 212 accepted imports
and 67 rejected imports. The full job plans are identical apart from the two
changed implementation hashes. No target, tolerance, selected job or physical
equation changed. No physical solve was needed for this tooling comparison.

All **33** catalog and ST3 modal regression tests pass, including changed or
missing files, duplicate-file integrity before cache reuse, independent mutable
diagnostics, fresh parsing on the next build, and changed parser outcomes.
The runner now prints the start and elapsed time of catalog checking.

Both profiles used one serial process, one BLAS thread, a 90-second cap and a
512 MiB address-space cap. Historical-report reading was only 0.67 s in the
baseline profile, so it was left alone. Imports and parsing the remaining
distinct models still account for substantial setup time. Numerical ISAE
agreement and broader ASWING functionality remain open.

[Measured results and evidence hashes](../../artifacts/isae/suite-planning-performance-20261104/assessment.json).
The `before/` and `after/` directories retain complete plans, source inventories
and frozen implementation files; both profiler files are retained alongside them.
