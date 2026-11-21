# ST-3 recurring mechanics comparisons

The recurring runner now has an explicit `st3-mechanics` selection for the
existing **86 static and nine modal targets**. It retains both unavailable
static ordinates, requires both meshes for each comparison and excludes the
overlapping historical ST-3 selections from the same run. The primary reviewed
result remains **93/95**. The fresh recurring replay stopped scheduling after
36 of 43 jobs completed when the user switched focus to ST-4. Its saved progress
has 77 matches, one unavailable reference and 17 unrun targets; no job remains
running. Seven jobs and the final import are pending. The pilot below is a
subset and does not replace the primary denominator.

## Fresh pilot

Three regular supervisor jobs cover the largest uncoupled force, the largest
negative-coupling torque, and the negative-coupling modal case. Each runs its
64/128 mesh pair serially. All six physical states completed successfully.
All **five readable reference values pass**, and the two clipped ordinates
remain unavailable in the pilot's seven required slots. The combined importer
preserves these counts, with no failed or unrun pilot jobs and no whole-family
validation claim.

The pilot includes the source scripts' signed torque loads and their disclosed
1.3734 torque-axis conversion. It retains complete requests, physical outputs,
modal matrices, eigenvectors, source hashes and terminal child receipts.
Maximum equilibrium/check residual is 8.89e−16 in the corresponding SI units;
matrix/shape checks also pass. Solver time totals 14.73 seconds, supervised
batch time 78.79 seconds, and peak child RSS is 146,496 KiB. These times include
different work and should not be treated as competing solver timings.

Seven additional artifact checks pass. They accept both complete static and
modal evidence and reject changed requests, failed child receipts, changed
physical settings, changed matrices and missing mode shapes. These checks use
the fresh pilot artifacts without running a solver. The preceding 33 focused
adapter/accounting/import checks and shared runner/report checks remain recorded.

## Scope and execution

The full plan selects **43 jobs and 86 physical states**: 40 static load states
on two meshes, plus three modal configurations on two meshes. Mesh repeats add
no reference votes. Available comparisons use the larger of the two mesh errors;
missing reference values remain unavailable even when both physical solutions
exist. The source targets and acceptance gates are unchanged.

Each physical child uses one BLAS thread, 512 MiB address space, 15 CPU seconds
and 25 wall seconds. The supervisor executes one job at a time through the
regular worker and scorer. The one-job wrapper reuses the verified complete
catalog, checks current code and terminal/reaped prior results, and holds an
exclusive process lock. A failed job stops continuation for review and is never
retried automatically. No background solver or browser/build job is started.

Both pilot and full plans were prepared by the regular CLI. An initial wrapper
omitted the scripts import path and failed before creating a plan or starting
a solver; its failure record is retained. The corrected wrapper made no source,
target or solver change. Catalog preparation took 15.02 seconds for the pilot
and 39.51 seconds for the full plan, illustrating the variable source-I/O cost
on this environment.

The original signed-load conventions, unavailable ordinate handling, native
startup/modal-identity qualifications and historical archive remain as explained
in the [static study](isae-st3-static-curves-20261109.md) and
[modal study](isae-st3-modal-current-20261109.md). ST-2's original-input attachment
ambiguity remains open. The interrupted ST-4 attempt is preserved separately
from the newly authorized ST-4 continuation.

Evidence: [pilot plan](../../artifacts/isae/st3-mechanics-runner-20261109/pilot/plan.json),
[pilot results](../../artifacts/isae/st3-mechanics-runner-20261109/pilot/report.json),
[combined pilot report](../../artifacts/isae/st3-mechanics-runner-20261109/pilot-combined/summary.md),
[artifact checks](../../artifacts/isae/st3-mechanics-runner-20261109/artifact-tests.xml),
[full plan](../../artifacts/isae/st3-mechanics-runner-20261109/full-run/plan.json),
[full replay progress](../../artifacts/isae/st3-mechanics-runner-20261109/full-run/report.json),
[one-job wrapper](../../artifacts/isae/st3-mechanics-runner-20261109/resume-one.py).
