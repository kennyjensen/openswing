# ST-4 recurring validation

The reviewed ST-4 mechanics comparisons are now available through the regular
ISAE runner and combined-report importer. Production structural equations,
original model files, reference values and acceptance gates are unchanged.

| Explicit scope | Models | Required frequencies | Meshes | Reviewed result |
|---|---:|---:|---|---:|
| `st4-mechanics` | 24 | 72 | 64 / 128 | 66 / 72 |
| `st4-native` | 5 | 31 | 128 / 192 | 31 / 31 |

These scopes overlap. The runner rejects selecting both, and the importer
rejects pooling them with each other or with the historical ST-4 archive.
Selecting either scope replaces overlapping historical jobs for ST-4 in that
run. The legacy archive remains available through the `modes` adapter without
either new scope. No new reference votes or progress passes are added.

## Evidence and gates

The [input manifest](isae-st4-mechanics-inputs.json) retains source checksums,
original properties and point weights. The [target manifest](isae-st4-mechanics-targets.json)
retains all original table cells, tokens, line numbers and declared mappings.
Paper triplets compare ascending frequency ranks; original bending/torsion
labels remain attached to their targets but are not claimed as identified
native modes. Native exports retain their original frequency ordinals,
including the seventh Weight7d root.

Each comparison requires two fresh serial solves. The reported prediction is
the worse reference error of the two meshes, so the reference policy cannot
select the more favorable mesh. Printed-precision checks remain separate
from the configurable 5% allowance. Both scopes retain physical equilibrium,
neutrality, left/right matrix residual and mass-normalization checks; frequency
refinement must be at most 0.1%, with mutually corresponding shapes and MAC
at least 0.99. An independent discrete beam calculation checks the fine-grid
roots. Every native frequency additionally requires agreement within 0.1%
with the independent continuous beam solution.

The unchanged numerical helper executes in children capped at 512 MiB address
space, 15 CPU seconds and 25 wall seconds, with one BLAS thread. Matrix auditing
has the same separate limits. Complete eigenvectors and sparse matrices are
saved; only JSON whitespace is removed to reduce writing overhead. Importing
a report authenticates the canonical inputs, terminal child receipts, physical
requests, saved reports and artifact hashes. It does not rerun a solver.

## Fresh execution check

Three recurring jobs, comprising six fresh physical states, completed serially:

| Selected model and scope | Result at 5% | Interpretation |
|---|---:|---|
| WING, paper | 1 / 3 | Preserves both known unloaded discrepancies |
| 7a_b8, paper | 3 / 3 | Weighted-wing passing control |
| 7d_b48, native | 7 / 7 | Largest native mesh sensitivity; all seven roots retained |

All six states passed their numerical gates. Both report imports succeeded.
The [paper pilot](../../artifacts/isae/st4-recurring-20261109/paper-summary/summary.md)
retains the full 72-target plan with 66 targets unrun in this new replay.
The [native pilot](../../artifacts/isae/st4-recurring-20261109/native-summary/summary.md)
explicitly selects seven targets and does not claim a fresh replay of all 31.
The earlier complete studies remain the evidence for the reviewed totals.
The runner's exit status 1 retains its whole-suite-open convention; both
pilots' actual job statuses are `computed`.

All **80 focused tests pass**. Tests cover the two complete reviewed counts, failed-job denominators,
overlap rejection, missing provenance, altered physical states, corrupted
matrices, changed requests and independent accuracy gates. ST-3 accounting
tests also exercise the shared importer and runner changes.

## Full native replay completed

The [combined native report](../../artifacts/isae/st4-recurring-20261109/native-complete-summary/summary.md)
now completes all five declared native configurations with ten fresh physical
states. All **31/31** original frequencies pass, along with all **320** left/right
matrix checks, mesh/shape correspondence and independent beam checks.
Maximum native error is 0.81275%, mesh change 0.06841%, and independent
continuous-beam error 0.05472%; minimum MAC is 0.9999994968. The largest
recorded peak RSS is 225,536 KiB. Four remaining jobs ran in two serial batches,
and the importer authenticated them together with the earlier seventh-root
pilot without duplicate comparisons.

The paper replay has separately reached four of 24 jobs: twelve frequencies
computed, ten passing, and the same two unloaded discrepancies. Its
[updated import](../../artifacts/isae/st4-recurring-20261109/paper-four-job-summary/summary.md)
retains the other sixty targets as unrun in this replay. The existing complete
physical study still supports the paper's 66/72 result. The original pilot
reports and verification receipt remain unchanged.

See the [native verification receipt](../../artifacts/isae/st4-recurring-20261109/native-complete-verification.json)
and the [source-row investigation](isae-st4-source-rows-20261109.md).

## Running a small serial batch

**Stopped at the user's switch to ST-5:** the paper replay subsequently reached
16 completed configurations out of 24. The runner exited with status 130;
the interrupted `7e_b21` directory was preserved under
`paper/interrupted-20261109/`. Eight configurations remain unfinished. The
[stop receipt](../../artifacts/isae/st4-recurring-20261109/paper/stop-receipt-20261109.json)
lists completed results, artifact hashes and the terminal process check.
The old `progress.json` active marker and aggregate report predate cancellation;
they do not indicate a live process or a completed aggregate refresh.
No ST-4 solver remains running. The earlier full study still supports 66/72.

The separate [documented-node-spacing probe](isae-st4-node-placement-20261109.md)
tested Drela 1989 Eqs. 37–38 in two bounded airflow states, with 96 saved-matrix
checks passing. Its sensitive frequency/decay errors were 20.15% / 99.01%,
so it does not settle the archived node convention or add accepted passes.
The existing point-weight jump regression also passed. These findings remain
available for a future return to ST-4; they do not change the structural totals.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
.venv/bin/python scripts/run-isae-suite.py \
  --adapters st4 --comparison-scope st4-mechanics --cases ST-4 \
  --workers 1 --max-new-jobs 1 --timeout-seconds 100 --output-dir PATH
```

Use `st4-native` for the separate native-export scope. `--resume` continues an
identical frozen plan; changed numerical or orchestration code requires a new
run. In particular, the older partially completed ST-3 replay retains its
original frozen runner and importer and cannot be resumed as unchanged after
this integration. No job or watcher is left running by this work.

The six paper failures, unloaded-input identity, source-position conflicts,
native mode identities/startup settings and airflow comparisons remain open.
See the [paper analysis](isae-st4-mechanics-current-20261109.md) and
[native refinement](isae-st4-native-refinement-20261109.md). Browser/build
checks remain held following the earlier UserLAnd failures.
