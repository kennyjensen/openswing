# ST-2 registration overhead and source verification

ST-2's source-only registration repeatedly hashed every production module for
each of its eight legacy modal jobs. It now shares one set of production hashes
within a registration and rehashes the complete inventory before returning.
This reduces production-file reads from **1,128 to 282**, or **75%**, while
rejecting source edits, additions, removals and symlink changes during planning.
The hashes are never cached across registrations or worker verification calls.

This is a validation-workflow change. All 141 numerical solver modules, original
inputs, physical settings and reference targets remain unchanged. The primary
ST-2 mechanics result stays **91/91**; no new scientific solve or comparison pass
is claimed. The legacy 490-slot archive and its existing results stay separate.

## Measurements

The two bounded, serial registration measurements retained all 17 legacy jobs
and 490 required scalar slots:

| Measurement | Original implementation | Revised implementation |
|---|---:|---:|
| Registration wall time | 20.466 s | 5.233 s |
| Production-file hash calls | 1,128 | 282 |
| Time in production-file hashing | 8.744 s | 1.119 s |
| Production bytes read | 14,441,480 | 3,610,370 |

These are individual observations on UserLAnd, not a controlled timing estimate.
Filesystem/cache and scheduling variability are substantial: unchanged source
pinning also became faster between these measurements. A later single source
test took 21.21 seconds, and a broader source-test batch still reached its
25-second limit. The deterministic improvement is eliminating six redundant
complete production scans. This does not establish browser loading performance
or a faster numerical solver.

The former source-registration runner test, which previously hit its 25-second
limit, passed in 9.46 seconds after the change. Each check uses one BLAS thread,
a 512 MiB address-space cap, 15 CPU seconds and 25 wall seconds. No background
solver, browser, build or Vite job was started.

## Verification

An independent standard-library comparison verifies **every field of all 17
before/after job definitions**. Only the adapter's own source checksum and byte
count differ. The comparison also rehashes all 141 production files, 31 unique
job source files and the authoritative Part III, steady, unsteady and extended
manual PDF/text pairs. No production module is imported by this verification.

**45 focused checks pass:** six new snapshot-lifetime/source-change checks,
the runner registration check, and 38 existing adapter checks. The remaining
six selected source-validation checks were in the interrupted broader batch;
that attempt reports no completed results and is not counted as passing.

The new checks reject same-size edits with restored timestamps, file additions,
file removals and symlink retargeting while registering. They also establish
that a subsequent registration observes changed bytes, including after a failed
registration. Canonical per-job source verification still reads current files.

One older adapter test initially failed because it compared the legacy
`.reference/` spelling with canonical `reference/` source pins. The same spelling
mismatch is present in the saved pre-change job definitions. The test now resolves
the compatibility symlink and actually checks original model/driver hashes
against the manifest. It also requires every original model and static driver
to be checked, preventing an empty verification loop from succeeding. The initial
failure and the passing isolated rerun are both retained.

## Attachment question remains open

The reviewed Weight documentation distinguishes the beam anchor parameter from
the point object's physical coordinates. Drela's steady §3.3, Eqs. 87–96,
defines its rigid-arm kinematics and load transfer. Part III §2.8, pp. 25–26,
describes concentrated forces as discontinuities at zero-length intervals.
These passages do not establish clipping or extrapolation for the original
ST-2 anchor t=0.558 outside the beam ending at t=0.55. The manual's explicit
spline-extrapolation passage applies to **Jangle moment–angle tables**, not
Weight attachment stations.

The existing [static attachment evidence](isae-st2-attachment-interpretations-20261109.md)
and [loaded modal equivalence](isae-st2-loaded-attachments-20261109.md) continue
to support the disclosed rigid tip-arm reconstruction. No general native
out-of-domain policy follows from them. Production attachment handling remains
unchanged; original-input compatibility remains open.

A subsequent [audit of the retained MIT examples](../../artifacts/isae/st2-official-attachments-20261109/report.json)
checks all 40 attachment entries in `dae.asw` (17), `fw.asw` (2) and `usa.asw`
(21), including both sides of each joint. All lie within their declared beam
domains. Each input matches the retained MIT download checksum, and all 141
production modules remain unchanged. These examples therefore supply no
out-of-range attachment example that would resolve ST-2. The audit constructs
no physical system and runs no solver; its interpretation remains conditional
on the current ASW parser.

Evidence: [baseline measurement](../../artifacts/isae/st2-registration-performance-20261109/baseline/measurement.json),
[revised measurement](../../artifacts/isae/st2-registration-performance-20261109/revised/measurement.json),
[complete job/source verification](../../artifacts/isae/st2-registration-performance-20261109/verification.json),
[snapshot checks](../../artifacts/isae/st2-registration-performance-20261109/snapshot-tests.xml),
[runner check](../../artifacts/isae/st2-registration-performance-20261109/runner-test.xml),
[initial adapter checks](../../artifacts/isae/st2-registration-performance-20261109/adapter-core-tests.xml),
[corrected source-path check](../../artifacts/isae/st2-registration-performance-20261109/reference-path-test.xml),
[interruption record](../../artifacts/isae/st2-registration-performance-20261109/source-check-interruption.json).
