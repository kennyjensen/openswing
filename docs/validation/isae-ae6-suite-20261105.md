# AE-6 shared modal comparisons

The later [source-density correction](isae-ae6-density-20261105.md) supersedes
this Weight7d comparison: its request used Weight7a's density rather than its
own original model constant. The 13/18 result below is retained as a wrong-density
diagnostic. The earlier Weight7a and Weight7c inputs and spectra remain unchanged.

All six original AE-6 modal tables are now registered in the shared runner.
Four fresh, serial solves give **49/56 computed scalar components within 5%**.
Including the selected malformed-model blocker gives **49/70 selected declared
components**. This is conditional agreement at three sampled operating points,
not full AE-6 or flutter-boundary validation.

| Configuration | Native point | IAS (m/s) | Nominal cosine intervals | Passing components | Failed-component errors |
|---|---:|---:|---:|---:|---|
| Weight7a | 2 | 120.5 | 32 | 11/12 | Lowest frequency 39.54% low |
| Weight7a | 2 | 120.5 | 64 | 11/12 | Lowest frequency 42.40% low |
| Weight7c | 2 | 95.5 | 32 | 14/14 | None; largest component error 1.1942% |
| Weight7d | 2 | 130.5 | 32 | 13/18 | Four real components: 5.52%, 18.92%, 34.97%, 105.97%; one frequency: 7.28% |

The seven failed components have median error **34.97%** and maximum **105.97%**.
Both Weight7a selected spectra exactly reproduce the retained
[earlier anchor](isae-ae6-anchor-20261105.md). They are repeat verification,
not additional independent native evidence. Weight7c and Weight7d add 32 distinct
native scalar cells; the current comparisons cover **44 distinct cells** in total.

## Complete registered modal scope

| Configuration | Original complex rows | Exported operating points | Declared IAS range covered by exports | Declared jobs on two meshes | Execution qualification |
|---|---:|---:|---|---:|---|
| Weight0 | 300 | 40 | 95–114.5 | 80 | Blocked: original model lacks final `End` |
| Weight7a | 300 | 41 | 120–140 | 82 | Explicit current setup |
| Weight7c | 300 | 42 | 95–115.5 | 84 | Explicit current setup |
| Weight7d | 174 | 21 | 130–140 | 42 | Explicit current setup |
| Weight7e | 300 | 40 | 110–129.5 | 80 | Explicit current setup |
| Weight7f | 300 | 39 | 90–109 | 78 | Explicit current setup |

The six historical records retain **1,674 complex rows / 3,348 original scalar
cells** as setup-qualified blockers. The opt-in `ae6-declared-airflow` scope
registers **446 jobs / 6,696 scalar slots** on nominal cosine32/64 meshes:
366 executable jobs and 80 malformed-model blockers. All 1,200 Weight0 slots
remain required. Source-catalog parsing independently confirms
`Line 34: beam is missing End.` No repaired input is substituted.

The complete declared score is **49/6,696 so far**: 70 selected slots are
accounted for and **6,626 further slots remain unrun**. That latter count includes
unexecuted blocker validations. Of the original 3,348 cells, **3,304 have no
prediction in this new shared scope**. Historical and declared ledgers reuse
the same targets and must not be added as independent observations.

All eighteen model/driver/export files are byte-identical ST-4 copies. The
literal command stacks explicitly set the first speed, increment each subsequent
point with `+`, and request `NN16` near `0+300i`. Commanded tail speeds without
archived modal rows acquire no fabricated targets. Original density, node arrays,
aerodynamic flags and startup state remain unauthenticated. Fixed frame, density
1.0771417304, PG0, lag, current influences, pointwise circulation and cosine
meshes are declared choices, unchanged from the anchor.

Every selected root is retained, including real and negative-frequency roots.
Native correspondence remains an injective minimum-complex-distance assignment,
as in the earlier AE-6/ST-4 study; native eigenvector identity is not established.
Other nacelle positions, aggregate tables, vacuum exports and exact flutter
onsets remain outside this adapter.

## Verification and limitations

All four solves pass the unchanged equilibrium and full-pencil checks. The
independent summary reopens the retained full matrices and left/right vectors,
recomputes **128 eigenvector residuals, 64 mass pairings and 64 clamp checks**,
and verifies original source, code and artifact hashes. No physical solve is
repeated by the summary. All eleven selected jobs are terminal and all four
workers are reaped; there are seven explicit blockers and no numerical failures.

The separate **0.1% mesh gate remains 5/12** for Weight7a. Weight7c and Weight7d
still lack their fine-mesh comparisons. Passing the native 5% allowance does not
establish spatial convergence or recover historical setup.

All **29 new adapter tests and 105 focused regression tests pass**. They cover
source and speed mapping, all required targets, unchanged strict/relative gates,
zero-solve blockers, altered-result rejection, full-artifact reassessment and
existing AE-4 behavior. A broader regression attempt reached its 90-second cap;
its partial log is retained and is not reported as a complete suite pass.

Numerical jobs ran one at a time with one BLAS thread and a 90-second worker
limit; coarse jobs used a 512-MiB address cap and the fine job 768 MiB. The three
coarse solver calls took 11.77–13.13 seconds, excluding source cataloging, process
startup, export and audit. The runner intentionally returns a nonzero exit status
while comparisons remain open; each job's explicit status distinguishes that
from a failed solve.

No production kernel changed, and no new browser run or distribution rebuild
was performed. Ten families still lack a shared adapter. Next work is the
Weight7c fine-mesh check, the Weight7d root correspondence/damping differences,
and the remaining sampled and unrun scopes. Full project validation remains open.

- [Independent summary](../../artifacts/isae/ae6-suite-20261105/summary/summary.md)
- [Exact accounting and error data](isae-ae6-suite-20261105.json)
- [Shared adapter](../../scripts/isae_suite_ae6.py)
- [Adapter regression tests](../../tests/test_isae_suite_ae6.py)
- [Saved-evidence completion verifier](../../artifacts/isae/ae6-suite-20261105/verify-completion.py)
