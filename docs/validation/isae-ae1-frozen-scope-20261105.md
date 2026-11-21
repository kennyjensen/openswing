# AE-1: explicit frozen-influence comparison

Updated 2026-11-05. The current solver reproduces the earlier finding that the
documented frozen-influence option brings the Pazy steady-deflection calculation
much closer to archived ASWING output. At 5° and commanded IAS 56 m/s, nominal
mesh 80, sensor-3 Earth-Z error changes from −10.89884% with updated influences
to +0.27364% with frozen influences. Elevation error changes from −7.16859% to
+0.14087%. The historical influence setting remains unknown.

This is a comparison-setting result, not a new solver correction. No production
equation, default, physical property, archived target or tolerance changed. The
existing updated-influence baseline remains **98/1,200 strict matches**. None of
the new endpoint outputs matches the original decimal printed interval.

## Scope and results

The shared runner now accepts the explicit option
`--comparison-scope ae1-frozen-influences` with the `ae1` adapter. It registers
200 alternative jobs alongside the original 200 jobs, using separate identities
and mesh comparisons. Alternative settings reuse the same original native cells;
they do not add independent reference data.

This batch selected eight alternative records: the 5°/56 m/s and 7°/42 m/s
endpoints, plus both unidentified initial rows, each on nominal meshes 40 and
80. Four cold equilibria computed successfully and passed all 29 physical checks
per state, including a fresh restored residual and independent sensor recovery.
Four initial-state records stayed unsupported with zero physical calls.

There are **24 valid scalar comparisons to 12 distinct native cells** at the
two positive operating points. Including both initial rows on both meshes gives
48 required slots: **0/48 strict matches**, 24 valid outputs and 24 unavailable
outputs. All eight records are terminal; all four solver processes were reaped.
The runner's exit code 1 records open reference comparisons, not a stalled solve.

All six fine-mesh outputs are retained below. Signed error is
100 × (OpenSwing − archive) / |archive|. These are absolute Earth sensor
coordinates and absolute sensor elevation, without subtracting an initial state.

| Native channel | Error at 5°, 56 m/s | Error at 7°, 42 m/s |
| --- | ---: | ---: |
| Sensor 1 X | +0.020888% | +0.003232% |
| Sensor 1 Z | +0.272514% | +0.169851% |
| Sensor 2 X | +0.017982% | +0.002912% |
| Sensor 2 Z | +0.274786% | +0.171222% |
| Sensor 3 Z | +0.273640% | +0.170530% |
| Sensor 3 elevation | +0.140867% | +0.074668% |

The maximum error across all 24 computed comparisons, including the coarse
mesh, is 0.274786%. The largest relative mesh change is 0.016772%, in elevation
at 5°. These mesh changes are descriptive; no new acceptance criterion was
introduced. The user-approved 3% policy currently applies to SA comparisons;
AE-1 retains its printed-precision gates.

The four frozen solves took 10.27–14.86 seconds each on this host. The complete
shared run took 94.26 seconds, including a 27.21-second source-catalog check.
The separate current updated-influence endpoint took 18.59 seconds and passed
29/29 physical checks. These timings describe the native runner, not the browser.

## What the documented option establishes

The [ASWING manual](../../.reference/aswing_doc.txt), under “Fast,Slow
Vortex-Lattice Model”, defines OPER K/F: fast holds influence matrices at the
undeformed geometry and zero alpha/beta; slow updates them with current geometry
and wind-aligned trailing vorticity. Freezing matrices does not set the physical
flight incidence to zero. Circulation, deformed section frames, structural shape
and loads continue to solve.

The original `alpha5.sh` and `alpha7.sh` do not select K/F, and the paired archive
does not supply the historical `.set` file. The manual's displayed fast setting
therefore does not identify the setting used by the archived runs. The report
also does not resolve that flag. Both alternatives remain declared conditional
reconstructions; closer agreement alone is not grounds to change the default.

The unchanged literal `Pazy_wing.asw` is used, including its two inactive
zero-weight records. Its SHA-256 is
`5086107d412ebf8f43ef75173fe553914fb074dd7dca3b93f7bd56ab365c17c8`.
Density 1.23 kg/m³, zero PG Mach, mounted constraints, transverse gravity,
ground image, cosine interval counts and cold continuation retain the baseline
choices. NODE I40 does not recover the historical node arrays. Startup states,
historical atmosphere and the native executable build remain unverified.

The [earlier full frozen-influence study](isae-ae1-literal-frozen-curves.md)
already covered 196 operating/mesh states on nominal meshes 60/120, primarily
comparing baseline-subtracted displacement and absolute elevation. It removed
the two zero-weight input records. This new work registers the option in the
shared runner, preserves literal input bytes and checks every native sensor
channel at the selected endpoints. It does not rerun or replace that full sweep.

## Verification and evidence

The selected run was independently summarized with zero production imports or
physical calls. The final summary explicitly separates the alternative setting
and preserves unavailable initial rows. Regression logs record 44 baseline/scope
checks, 14 scope checks, 10 shared-runner checks and 30 summary/mixed-scope checks;
these groups overlap and are not added to native comparison scores. An initial
overlarge test batch timed out, and an import-path test fixture failed before it
was corrected. Both failed attempts remain in the evidence directory.

- [Detailed values, pins, timings and test receipts](isae-ae1-frozen-scope-20261105.json)
- [Independent final summary](../../artifacts/isae/ae1-frozen-scope-20261105/analysis-final/summary.md)
- [Frozen plan and source pins](../../artifacts/isae/ae1-frozen-scope-20261105/batch/plan.json)
- [Current updated-influence endpoint](../../artifacts/isae/ae1-current-anchor-20261105/summary.json)
- [Retained updated-influence raw files](../../artifacts/isae/ae1-current-anchor-20261105/retained-raw-manifest.json)

To reproduce in a new output directory, run one worker with one BLAS thread:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python scripts/run-isae-suite.py \
  --adapters ae1 --cases AE-1 \
  --comparison-scope ae1-frozen-influences \
  --job-pattern 'AE-1-a05-row057-m*-frozen' \
                'AE-1-a07-row043-m*-frozen' \
                'AE-1-a??-row001-m*-frozen' \
  --workers 1 --timeout-seconds 90 --relative-tolerance 0 \
  --output-dir artifacts/isae/ae1-frozen-reproduction
```

No browser/kernel change was made, so browser runs and distribution archives
were not rebuilt for this comparison adapter. Whole-family validation and the
project goal remain incomplete. The next priority is the AE-2 branch/continuation
discrepancy, followed by registering original AE-4/AE-5 flutter comparisons.
