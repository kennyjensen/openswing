# ST-2 full recurring replay and combined-report support

**All 43 recurring jobs completed and all 91 mechanics comparisons pass at
5%.** The combined-report importer now authenticates and summarizes this
scope successfully. No target, material parameter, solver equation or
acceptance gate changed.

| Comparison | Matches | Median nonzero error | Maximum error | Maximum mesh change |
|---|---:|---:|---:|---:|
| All six published static curves | 77/77 | 0.06452% | 0.42168% | 0.02030% |
| Both modal orientations | 14/14 | 0.08584% | 0.86569% | 0.30270% |

The calculation retains the previously disclosed setup: explicit tip-pylon
reconstruction for static loads, literal modal files with self-weight and
source-density still-air inertia. These are the unchanged
[91 primary targets](isae-st2-mechanics-scope.json). Literal native handling
of the static file's out-of-domain attachment is still unresolved. This is a
completed mechanics comparison under that setup, not full ST-2 compatibility
or full ASWING implementation.

## Fresh execution and numerical evidence

The 41 static jobs include fresh unloaded baselines and all maximum-load
refinements, producing 85 static states. The two modal jobs compute both
80- and 160-node meshes, producing four modal states. Repeated baselines and
mesh refinements add no comparison votes. Every one of the 89 physical
states completed on its first attempt, passed its numerical checks, and has
a retained request, full result and source/evidence hashes.

The modal shape assignments agree across meshes with minimum mass-weighted
MAC **0.999995247**. All **160 left/right eigen-equation checks** pass, with
maximum relative residual **8.22e−13**. All 80 returned roots satisfy the
neutral-mode gate, with maximum normalized real component **6.52e−13**. Raw
complex roots remain in the artifacts; they are not replaced with zeros.

Every physical state ran serially with one BLAS thread, 512 MiB address space,
15 CPU seconds and 25 wall seconds. Peak child RSS was **180,484 KiB**.
Recorded supervised batch time totals **761.16 seconds**; solver time after
imports totals **79.16 seconds**. The batch total includes cold process,
source-verification and reporting overhead, and excludes pauses between
batches. No browser/build jobs were started.

The full plan was prepared by the regular CLI. The
[one-job resume wrapper](../../artifacts/isae/st2-mechanics-summary-20261109/resume-one.py)
then used the regular supervisor, worker, code/source checks and scoring,
reusing the already verified catalog. It holds an exclusive process lock,
verifies terminal/reaped results before resuming, and never retries a failed
job automatically. The original catalog preparation took 33.38 seconds;
it was not repeated for every small job.

## Combined-report importer

The prior importer expected legacy ST-2 row and complex-component fields.
It now supports the explicit `st2-mechanics` selection, including source byte
counts, original model identity, canonical job reconstruction, strict and
5% scoring, and mechanics-specific descriptions. Legacy archive behavior is
retained. Mixing mechanics with the overlapping archive is rejected rather
than adding their targets together.

Computed results are checked against the saved adapter/state reports and
their complete artifacts: requests, physical outputs, spectra, shapes and
sparse matrices. Those files join the source ledger and are rehashed before
publication. Failed or timed-out jobs remain in the required denominator.
No solver is imported or executed by the summary operation.

**98 focused checks pass:** 41 mechanics/summary tests and 57 shared reporting
tests. They cover altered targets, incomplete evidence, missing or changed
artifacts, failed-job accounting, policy integrity and overlapping scopes.
Saved-result fixtures are used only for contract regressions; the 91/91
result comes from the fresh complete run. The earlier failed assertion about
a stale legacy-only scope note is retained in the first test report; that
description is now conditional on the selected scope.

The actual combined import finished in **12.24 seconds**, reporting 91
finite, numerically valid matches, zero unrun/failed/unavailable slots in
this mechanics scope, and `full_suite_validated: false`. Its complete
41-family catalog is retained; the other families were not run in this batch.

## Commands and remaining work

The [regular runner instructions](isae-st2-mechanics-runner-20261109.md) apply.
For a new run, select `--adapters st2 --comparison-scope st2-mechanics`, use
one worker and a new output directory, and execute small batches with
`--max-new-jobs 1` / `--resume`. After a run, the combined importer is now usable:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python scripts/summarize-isae-suite.py \
  --run artifacts/isae/st2-mechanics-summary-20261109/full-run \
  --output-dir artifacts/isae/st2-mechanics-summary-new
```

Use a fresh summary directory; existing summaries are preserved. Frozen runs
must match current solver/helpers to be imported. The primary **91/91** count
is unchanged by this rerun. The supplementary **275/368 spanwise replay** and
original **56/490 archive** remain separate, with all unavailable legacy
values retained. Remaining work concerns native attachment/input semantics,
historical settings and legacy output compatibility. All 141 production
modules remain unchanged.

Evidence: [full run](../../artifacts/isae/st2-mechanics-summary-20261109/full-run/report.json),
[combined JSON](../../artifacts/isae/st2-mechanics-summary-20261109/combined/summary.json),
[combined Markdown](../../artifacts/isae/st2-mechanics-summary-20261109/combined/summary.md),
[41 mechanics tests](../../artifacts/isae/st2-mechanics-summary-20261109/mechanics-tests.xml),
[57 shared tests](../../artifacts/isae/st2-mechanics-summary-20261109/shared-tests.xml).
