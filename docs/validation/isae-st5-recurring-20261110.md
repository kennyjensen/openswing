# ST-5 recurring mechanics validation

The declared ST-5 mechanics comparison is now available through the regular
ISAE runner and independent report importer. All **16 original static cases**
and **16,688 distinct structural observations** are registered. Production
equations, source models, reference values and the existing gates are unchanged.

The [complete five-grid study](isae-st5-mechanics-current-20261110.md) still
supports the primary **16,687/16,688** result. This integration adds no reference
votes. Historical strict scopes and unavailable reference evidence remain
separate; neither those results nor repeated meshes are pooled with mechanics.

## Fresh replay

Four configurations exercise the rigid, roller, forward-only and elliptical
branches through the new runner. Each requires five cold solves with a fresh
saved-state residual evaluation. All **20 physical states** and **56 final
field-convergence checks** pass.

| Configuration | Matching native values | Largest final mesh change |
|---|---:|---:|
| Rigid, 30 lb, 80/20 | 1,119 / 1,120 | 0.03335% |
| Literal type-2 roller, 20 lb, 80/20 | 1,120 / 1,120 | 0.01318% |
| Forward wing, cosine, 20 lb | 812 / 812 | 0.02993% |
| Rigid, elliptical, 20 lb, 80/20 | 1,120 / 1,120 | 0.01587% |
| **Selected replay** | **4,171 / 4,172** | **0.03335%** |

The [independent import](../../artifacts/isae/st5-recurring-20261110/pilot-summary/summary.md)
authenticates the full saved evidence and reproduces those counts. This is a
fresh four-case replay, not a second execution of all sixteen cases. The other
twelve remain supported by the prior complete study, whose production modules
are unchanged.

The single miss is unchanged, including its exact prediction: forward-wing
`Fn` at source line 67 is −0.0003280584535 lb versus native −0.000290 lb.
The absolute difference is **0.00003805845 lb**, or **13.12%**. Its required
slot remains; no near-zero floor was enlarged.

## Preserved comparison contract

The [input manifest](isae-st5-recurring-inputs.json) pins the original sources,
target decoders and reviewed recovery scripts. The solver uses current
production code; saved predictions are never inputs. Printed station centers,
known exact anchors, duplicate row traces and all original output fields are
retained. Five nested grids must pass the physical checks; every one of
the fourteen final-pair field changes must be at most **0.1%**. Convergence uses
deformation rather than absolute jig position or orientation.

The primary native prediction always comes from the archived-station grid.
The final refined solution independently qualifies convergence; the runner
does not choose whichever mesh happens to match best. The report retains
finer-grid predictions and all fields outside the mechanics denominator.

ST-5's declared allowance is **relative error plus original printed precision**.
The shared runner's existing default for other scopes remains the larger of
those two allowances. The explicit ST-5 rule is checked by both the runner
and importer and cannot be injected into another scope. Setting relative
tolerance to zero restores the original strict intervals. Numerical validity
requirements are independent of this reference allowance.

Selecting `st5-mechanics` replaces overlapping historical ST-5 jobs within that
run. Importing mixed historical and mechanics scopes is rejected. The legacy
`structure` adapter remains available without this selection. The report's
modified in-plane link, original unrounded nodes, unresolved reaction display
and unavailable modal evidence retain their earlier qualifications.

## Resource limits and checks

Each numerical child uses one BLAS thread, at most **512 MiB address space,
15 CPU seconds and 25 wall seconds**. Its supervisor waits at most 30 seconds,
reaps the child and saves its terminal receipt. Jobs and grids run serially.
The largest fresh child used **12.80 CPU seconds**, **15.06 wall seconds** and
**186,832 KiB peak RSS**. No numerical attempt failed or was retried.

A separate child audits the saved residual and position arrays. The importer
authenticates canonical source identity, all five execution plans, saved results
and arrays, row recovery, the audit receipt and file hashes. It verifies that reported native predictions and mesh measures derive
from those saved states. Failed or missing states never reduce the denominator.

All **121 focused tests pass**: reference-acceptance regressions, ST-4 runner
compatibility, ST-5 counts and complete-state requirements, overlap rejection,
corrupted physical artifacts and missing provenance. An initial combined
unit-test batch reached its 55-second cap; its receipt is retained. Splitting
the tests into small serial groups completed every check. No solver was run by
that capped unit-test batch.

The runner exits with status 1 because its full-suite goal remains open;
the four physical job statuses are all `computed`. The independent import
finishes with status 0. Browser, Vite and build checks remain held following
the earlier UserLAnd failures.

## Running a small batch

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 .venv/bin/python scripts/run-isae-suite.py \
  --adapters st5 --comparison-scope st5-mechanics --cases ST-5 \
  --workers 1 --max-new-jobs 1 --timeout-seconds 180 --output-dir PATH
```

This registers all sixteen cases but executes only the first unfinished job.
Use `--resume` with the identical arguments and directory to continue. Use
`--job-pattern 'ST-5/st5-mechanics/st5-30lb_80_20'` to explicitly select the
known-miss case instead. The complete upstream catalog remains visible.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
.venv/bin/python scripts/summarize-isae-suite.py \
  --run PATH --output-dir NEW_SUMMARY_PATH
```

Changed runner/importer code requires a new frozen run. Earlier studies and
their original helper versions remain preserved. The recurring adapter is
complete; the whole ST-5 family and broader OpenSwing goal remain open.
