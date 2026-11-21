# AE-4 shared modal registration

AE-4 now has a shared-runner adapter. It inventories **all eighteen original
text modal exports: 4,740 stored eigenvalue rows and 9,480 real/imaginary
components**. Identical archive files are identified; their content/line
identities reduce to 3,643 rows. File copies and mesh repeats are not independent
validation evidence. The historical ledger remains explicitly blocked where
setup, base state or exact writer pairing is unresolved.

The optional `ae4-undeformed-alpha0` scope registers the **entire original
undeformed alpha-zero table**, on both nominal cosine40/80 meshes. It has
218 jobs and **1,200 required components**: 216 executable commanded-speed
jobs and two blocked unknown initial states. All 600 original scalar cells
remain required on both meshes, including real poles and the extra small root
at native point104. No terminal point110 values are invented. The complete
plan contains 236 jobs and 10,680 slots across historical and declared scopes;
these scopes deliberately reuse native cells.

The executable route reuses the checked wall-mode helper, retaining the literal
model, solid wall, fixed frame, density1.23, PG0, lag, current influences,
pointwise circulation, `NN4`, shift `0+200i` and full matrices. It checks full
left/right pencil residuals, mass normalization and clamp motion. The real-pole
certificates introduced in the [later-branch study](isae-ae4-later-20261105.md)
are retained. No production equation, default or model byte changed.

All three fresh shared-runner solves complete and pass their numerical checks:

| Declared IAS | Native point | Nominal intervals | Reference result at 5% |
|---:|---:|---:|---|
| 80 m/s | 81 | 40 | 4/4 pass; reproduces the earlier roots exactly |
| 100 m/s | 101 | 80 | 3/4 pass; retains the 5.9134% damping failure |
| 103 m/s | 104 | 40 | 0/8; all eight components remain unavailable because the selected spectra cannot be completely paired |

The selected batch also validates all eighteen historical blockers and both
unknown initial states without importing or calling the numerical solver.
All 23 jobs terminate: three computed and twenty unsupported. The selected
declared ledger is **7/28**: seven passing components, one finite failure,
eight unresolved modal components and twelve blocked initial-state components.
Against the full registered declared sweep, that is **7/1,200 so far**, with
1,172 slots unrun in this batch. The historical 9,480 slots remain unavailable.
The runner's exit status1 records open comparisons; it is not a worker crash.

The earlier seven-speed results remain [63/68 conditional matches](isae-ae4-later-20261105.md).
The two repeated states add no independent targets. Including the newly attempted
103 m/s components gives **63/76 in the accumulated sampled evidence**, with
eight unavailable. The full shared sweep and this accumulated sample have
different denominators and are reported separately. No old result is relabelled
as a fresh shared-runner solve.

At 103 m/s the current selected roots are approximately
`−3.471048+182.193618i`, `29.102314+114.334714i`, `0.093297+0i` and
`−179.601081+0i` (raw imaginary remainders are retained). The archive instead
contains `0.000071831+0.000077429i`, `0.033334576+0i`,
`29.005996+114.62964i` and `−3.5140312+182.09349i`.
The two larger oscillatory modes look similar, but the positive-frequency set
is incomplete under the declared local search. The adapter does not discard
the small native root or guess a real-pole correspondence to award passes.
Historical constraints, local-search selection and branch identity remain
questions for further source-based investigation.

The new adapter pins original inputs against the immutable manifest and verifies
the literal insertion stack. The shared runner and independent summary reject
changed targets, missing modes, altered physics/search settings, failed pencil
or real-pole certificates, unqualified historical claims and incomplete outputs.
The summary authenticates the retained raw files and binds its compact spectrum
to the helper report. Compact residual audits are checked algebraically; full
matrices and vectors remain available for independent re-evaluation. A separately
declared **0.1% component mesh gate** is not relaxed by the 5% native-reference
allowance. These selected jobs do not contain a completed executable mesh pair,
so their mesh diagnostics remain incomplete.

The independent shared summary completes successfully and reproduces the full
selected denominator, including all historical blockers and unmatched roots.

All **207 focused Python tests pass**, including all 35 new AE-4 checks and
shared runner, summary, acceptance-policy and batching contracts. A broader
444-test command reached its 90-second cap in an older AP-1 fixture after sixty
passes and no failed assertions. Its partial log is retained; no claim is made
that all 444 tests completed. The focused selection excludes unchanged heavy
per-family decoders and is recorded explicitly.

The final summary counts four native rows with finite paired predictions.
Four further 103 m/s rows have valid physical solves but unavailable reference
pairing. An initial summary counted all eight as valid reference samples; that
sample tally is corrected and regression-tested. Scalar counts are unchanged,
and the initial summary remains in the evidence directory.

The full plan is inspectable without solving:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
.venv/bin/python scripts/run-isae-suite.py --adapters ae4 --cases AE-4 \
  --comparison-scope ae4-undeformed-alpha0 --workers 1 --plan-only \
  --output-dir NEW_PLAN_FOLDER
```

For one bounded fresh coarse case, use a new directory:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
.venv/bin/python scripts/run-isae-suite.py --adapters ae4 --cases AE-4 \
  --comparison-scope ae4-undeformed-alpha0 \
  --job-pattern 'AE-4:declared:op081:n40' --workers 1 \
  --timeout-seconds 90 --max-new-jobs 1 --output-dir NEW_RUN_FOLDER
```

The original reference cache is required. Completed jobs can be resumed only
with the same frozen source/selection settings. Each numerical job ran serially
with one BLAS thread and a 90-second worker cap. Coarse jobs used a 512 MiB
address cap; the fine full-matrix export used 768 MiB. These are shared native
Python runs; no new browser/UI claim follows. Production kernels retain their
previously verified browser hashes.

The rest of the declared sweep, deformed/divergence branches, original sensor
and LCO histories, other aggregates, historical setup and native modal identity
remain unfinished. Eleven other ISAE families still lack shared adapters.
The full ASWING implementation goal remains active.

- [Machine-readable registration and evidence](isae-ae4-suite-20261105.json)
- [Complete frozen plan](../../artifacts/isae/ae4-suite-20261105/full-plan/plan.json)
- [Selected shared-runner report](../../artifacts/isae/ae4-suite-20261105/batch/report.json)
- [Focused regression selection](../../artifacts/isae/ae4-suite-20261105/regression-selection.json)
