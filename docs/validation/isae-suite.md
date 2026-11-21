# ISAE regression coverage

Matching the archived ASWING calculations across the entire ISAE collection is
the current development priority. The earlier selected comparisons were useful
diagnostics, but did not constitute a regression suite for the collection.
Experimental agreement is not the acceptance target. The active user-directed
scope is SA-2 and later steady aerodynamics; SA-1 is paused.

The catalog includes all 41 case families in the pinned ISAE checkout and every
one of its 279 original `.asw` models, including the supplemental model outside
the case directories. SA-9 is absent from the upstream collection and is recorded
as absent. Original file hashes and import errors remain visible. Importing a
model does not establish a matching calculation.

The [frozen broad comparison report](isae-suite-current.md) combines six completed
batches against the same numerical implementation. Seven adapters account for
declared scopes in 18 families; 23 families still need adapters. Of 2,443 planned
jobs, 1,167 computed their outputs, 1,214 recorded unsupported scopes, and 62
failed or timed out. These are execution units, including multiple meshes, not
2,443 distinct ISAE cases. All 35,193 declared output slots remain accounted
for; 26,251 are finite. The [family backlog](isae-suite-backlog.md) records the
unimplemented scopes and the order of work.

The [current FFWT/ST-4 follow-up](isae-suite-followup-20261026.md) verifies source-rank and exact-station fixes on a newer kernel. Five FFWT equilibria and all fifteen ST-4 modal grids now pass numerical checks; reference and refinement failures remain. Those bounded reruns are kept separate from the broad baseline.

The [latest completed source-only registry](../../artifacts/isae/sa6-postprocessor-pairing-20261028/registry.json)
has **sixteen adapters, 4,043 jobs and 66,682 required output slots across
selected scopes in 26 families**. Fifteen families lack adapters. This includes
the previously prepared ST-2 modal scopes, SA-13 figure registration and expanded
SA-6 static execution support. Its recorded kernel predates the analytic-control
implementation; it is a plan, not a claim that every current job has run.

SA-6's separate conditional control-derivative comparison uses the analytic
`openswing.rigid_derivatives.rigid_control_derivatives` API. It preserves all six
original F1 channels at all 44 chordwise states on the two declared meshes.
Historical derivative settings and producer execution remain unverified. The
prescribed rigid response is explicit and its derivative checks remain separate
from the 528 registered static-coefficient checks. The shared analytic control-input terms
also enter the coupled equilibrium derivative API; its directional output
recovery remains centered. See the [source audit](../../artifacts/isae/sa6-control-tangent-20261028/source-audit.json)
and [native verification](../../artifacts/isae/sa6-control-tangent-20261028/native-verification.json).

The [completed derivative comparison](../../artifacts/isae/sa6-control-tangent-20261028/analysis/summary.json)
has 88/88 analytic cases computed, all 528 values numerically valid, and 88/528
printed matches, exclusively zero CY derivatives. No complete derivative row
matches. All four independent perturbation validations pass at both step sizes;
the maximum coefficient-derivative difference is 1.59e-9. The
[source rigidity evidence](../../artifacts/isae/sa6-control-tangent-20261028/rigidity-evidence.json)
establishes infinite stiffness in all four original decks, ruling out elastic
shape response as an explanation of the fixed-state derivative differences.
Historical NODE, K/F and startup remain unresolved. All 264 original F1 cells
are retained in this conditional comparison; the additional 1,584 state
derivatives and 1,452 tensor entries are not covered by it.

The F1 scope is now available in the standard runner through the explicit
`sa6-f1-rigid` option. It adds 88 derivative jobs and 528 slots to an SA-6 plan;
default static planning is unchanged. The derivative and static summaries keep
separate counts. A single registered integration case has completed with all
six values valid and one match, its zero side-force derivative. Registration
does not constitute a new full 88-job run.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python scripts/run-isae-suite.py \
  --adapters sa6 --cases SA-6 --comparison-scope sa6-f1-rigid \
  --job-pattern '*:rigid-F1' --workers 2 --timeout-seconds 180
```

The separate [state-derivative increment](isae-sa6-state-derivatives-20261028.md)
adds analytic speed, angle and rate responses. Its conditional comparison keeps
the original state-derivative targets separate from these static and F1 ledgers.
The standard runner now exposes this scope through `sa6-state-rigid`, retaining
all 36 original cells per operating point and their printed precision. It adds
88 jobs and 3,168 slots. Default SA-6 planning remains 91 jobs / 528 static slots;
state-only opt-in planning totals 179 / 3,696, and enabling both derivative
options totals 267 / 4,224. These are separate static, F1 and state ledgers.
The state route differentiates the full current steady operator; historical
ASWING influence linearization remains unverified.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python scripts/run-isae-suite.py \
  --adapters sa6 --cases SA-6 --comparison-scope sa6-state-rigid \
  --job-pattern '*:rigid-state' --workers 2 --timeout-seconds 180
```

The [mass/inertia scope](isae-sa6-mass-tensors-20261028.md) is available through
`sa6-mass-rigid`. It retains all 33 dimensional body-axis entries per native
file: 88 jobs and 2,904 slots from 1,452 distinct archived cells. It uses the
literal undeformed geometry and existing mass assembly without an aerodynamic
solve. Zero real mass keeps an undefined physical CG; the archive's reported
zero coordinate is explicitly qualified as a tensor reference. Native tiny
nonzeros and their original precision remain required. The mass-only opt-in
plan totals 179 jobs / 3,432 slots; all three opt-ins total 355 / 7,128. These
totals include the default static scope; the selector below runs only mass.

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python scripts/run-isae-suite.py \
  --adapters sa6 --cases SA-6 --comparison-scope sa6-mass-rigid \
  --job-pattern '*:rigid-mass' --workers 2 --timeout-seconds 60
```

The [SA-13 batch](../../artifacts/isae/sa13-registration-20261028/summary/summary.json)
records eight blocked series with 612 retained ordinate slots. Original geometry
and operating settings are missing. It distinguishes 239 finite original-
discretization values, 237 finite modified-ASWING values, and 136 unavailable
entries, without inventing precision tolerances or using experimental data as
targets.

The [ST-2/AP-1 batch](isae-suite-st2-ap1-20261026.md) adds all
identified native target rows in those families: 37 records, six computed AP-1
header comparisons and 31 blocked records. All 78 computed values remain
different from archived printed precision. Blocked span targets and unresolved
model/settings bindings remain required, unavailable outputs.

The [ST-5/AE-2 expansion](isae-suite-st5-ae2-20261027.md) adds the remaining rigid-joint 30 lb 80/20 snapshot and all eight coupled-layup sensor sweeps: 369 jobs and 7,952 required slots. Original models, coupling terms and accuracy gates are preserved. These additions extend existing families.

The [AP-2 expansion](isae-suite-ap2-20261027.md) registers all 117 original
MAT grid ratios, both paired endpoint CL/CD tables and three unpaired text
exports: 237 jobs and 248 required slots. Intermediate Engine positions are
explicitly reconstructed from the original producer. MAT storage identity is
reported separately from native coefficient print precision. Historical setup
and exact R5.92 exporter formulas remain qualified.

The [AE-1 expansion](isae-suite-ae1-20261027.md) registers both complete sensor
sweeps: 100 original rows, six absolute outputs, two declared meshes, 200 jobs
and 1,200 required slots. The four repeated unknown initial-state records remain
blocked. All 196 executable jobs complete and pass physical checks; 98 scalar
print matches do not establish any complete six-channel row match. The
[ST-6 audit](isae-st6-readiness-20261027/report.md)
identifies no archived ASWING solve there; MATLAB analytical curves and
experiments are retained as source evidence, not invented comparison targets.

The [AE-3 expansion](isae-suite-ae3-20261027.md) adds all six native finite-control coefficient states on two meshes and retains every native derivative, inertia and rate cell, all 113 separately qualified embedded values, and five unpaired models. All 50 jobs finish: 12 computed and 38 blocked/inventory records. Of 725 slots, 72 are numerically valid and 653 remain unavailable. Fifty scalar print matches do not establish any complete six-coefficient state match.

The [ST-1 expansion](isae-suite-st1-20261027.md) registers 37 jobs and 200 slots from all 197 distinct native scalars, preserving all ten models and both components of all 76 complex roots, including 25 real-only roots. Two conditional structural comparisons of unchanged `[45_0]_3a` on prospective 100/200 intervals compute six body-anchor positions; two coarse-grid channels match printed precision, while neither full state matches. The remaining 194 native slots and nine model inventories stay blocked. Additional arrays and plots remain outside this provenance-bound denominator.

The earlier [SA-11/SA-12 batch](isae-suite-expanded-20261026.md) retains all 1,676
results against its own kernel: SA-12 completes all 1,020 solves; SA-11 has 47
computed, 281 errors and 328 blocked jobs. Results from incompatible kernel
versions remain separate; no complete-family pass is claimed.

Run the registered comparisons from the repository root:

```sh
npm run test:isae:plan
npm run test:isae -- --output-dir /tmp/openswing-isae-run
```

These commands use the prepared reference cache in this workspace. A fresh
checkout needs the pinned upstream archive (`scripts/fetch-isae-validation.py`),
the P-1 input tables and decoded figures (`scripts/fetch-isae-p1.py` and
`scripts/extract-isae-figures.py`), and the referenced source-audit evidence.
Planning checks those dependencies before any aircraft solve; it does not
download or execute upstream scripts automatically. Some historical evidence
records contain absolute paths, so moving the checkout also requires relocating
those source records with their byte hashes preserved. Fresh-checkout setup is
not yet automated for every adapter.

By default every registered comparison is selected. For bounded runs, `--cases ST-5 AE-2` selects exact family IDs, and quoted `--job-pattern` globs select job IDs within those families and adapters. Every requested family and pattern must match. Selectors are frozen in the plan and must remain identical on resume. Selected-run reports retain all 41 families and identify omitted scopes separately from the global registry.

The recovered earlier SA-7 fore-wing model has an explicit supplemental pairing:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python scripts/run-isae-suite.py \
  --adapters extra_polars --source-pairing sa7-fore-f745fb40 --cases SA-7 \
  --job-pattern '*historical-f745fb40*' --workers 1 --timeout-seconds 90
```

This compares all 29 unchanged rows on 64/128 intervals, with 406 comparison
slots reusing 203 native target cells. The default registry and current-file
comparisons remain separate. Planning and execution verify the earlier commit
tree and model blob, the byte-identical driver/table, and the pinned current
archive. The summary independently reconstructs that pairing and labels it
separately. Historical executable, startup state, node placement, and the cause
of the negative archived drag remain unresolved. This requires the retained
source-history evidence under `artifacts/isae/sa7-drag-source-audit-20261028`.

The default creates a fresh timestamped directory under `artifacts/isae` when
`--output-dir` is omitted. `--plan-only` inventories inputs without running the
aircraft solvers. Select a batch with `--adapters polars`, `components`,
`extra_polars`, `structure`, `modes`, `aeroelastic`, `sa6`, `sa11`, `sa12`, `st2`, `ap1`, `ap2`, `ae1`, `ae3`, `st1`, or `sa13`.
`--workers` bounds concurrent processes and
`--timeout-seconds` bounds each job, including its imports. The default is two
workers and 180 seconds per job. Numerical libraries use one thread per process.

Use `--resume` with the same explicit directory, adapter selection, worker count,
timeout, source code and references to reuse finished jobs from that plan.
Changed inputs require a fresh directory. A timeout or failed solve stays in
the denominator; it is not silently skipped or retried until something passes.

Each run writes `catalog.json`, `plan.json`, `progress.json`, `report.json` and
`report.md`, plus requests, results and logs for individual jobs. The plan pins
the numerical implementation, adapter code, original inputs, runtime and
execution policy. `frozen-code` preserves the planned code. Unsupported rows
retain their required outputs and blocker descriptions without starting a
numerical solver. Each subprocess is reaped before its job is recorded complete.

The command currently exits **1** because the full suite has unresolved
comparisons. Inspect `report.json` to distinguish a recorded mismatch, unsupported
case, solver failure and interrupted execution. A successful inventory-only
command exits 0; this says nothing about physical agreement.

Reports separate these questions:

- Is the original model/output pairing established, and is its setup known?
- Did the numerical solve and independent physical checks succeed?
- Were every required row and output produced?
- How sensitive are the results to the declared mesh?
- Do the calculated outputs match the archived values at their stated precision?

| Adapter | Registered scope |
|---|---|
| `polars` | Every row and seven outputs in ten original SA-1–5/SA-7–8 tables, on two declared meshes. |
| `components` | All six P-1 archived propeller CT curves; 110 values with the original supplied power inputs. |
| `extra_polars` | Five runnable SA-10 variants and three SA-14 CL tables; all selected SA-15 rows and the invalid SA-10 variant retain explicit blockers. SA-12 has moved to its dedicated adapter without duplicate jobs. |
| `structure` | One original ST-3 and four ST-5 static snapshots, with full declared output recovery on three grids and fresh restoration checks. |
| `modes` | Five original ST-4 vacuum weight variants, all 13 native modal exports, summary candidates and unpaired models; unsupported scopes remain blocked. |
| `aeroelastic` | All 263 positive-speed coordinates in twelve AE-2 sweeps (uncoupled and both coupled layups) and all eight FFWT-1 Flare10/A5 coordinates, on two meshes; all twelve original AE-2 NaN rows remain visible. |
| `sa6` | All 11 original states for four chord variants, six static coefficients and two meshes: 88 solves / 528 checks. Optional `sa6-f1-rigid` adds 88 jobs / 528 F1 derivative slots; `sa6-state-rigid` adds 88 jobs / 3,168 state-derivative slots. Each scope has a separate ledger. The 35c shell driver supplies its controls; the other three variants use the original MATLAB degree labels and exact archived Cl/Cn token pairs. Missing shell drivers, historical startup and derivative linearization remain qualified. Three spanwise models lack paired exports; tensor scope remains outside this adapter. |
| `sa11` | All eight baseline/extension tables, 328 original rows and seven outputs on nominal 64/128 grids. Four 0.75/0.78 tables remain blocked by force/coefficient normalization conflicts. Literal speeds and declared PG are retained; historical startup state is unresolved. |
| `sa12` | All six ground-effect tables, 510 original rows and four raw coefficients on nominal 100/200 grids. Image flag, normal and origin height are forwarded and checked. Pitch=alpha is an explicit wind-parallel assumption because historical Euler pose is absent. |
| `st2` | All 396 native modal/static targets, ten separately qualified workbook cells and six literal models. Existing registrations remain blocked. Null-object handling now permits the two modal models to reach setup; output/generating-state ambiguities remain, and active static attachments remain invalid. |
| `ap1` | All six paired header/span exports on two nominal meshes, plus unpaired PROWIN and PROWIM.t targets. Six positive-slope header jobs execute with source engine coupling; all span recovery and zero-slope/unpaired routes remain blocked. |
| `ap2` | All 117 original position-grid ratios on nominal 150/300 meshes, plus two endpoint CL/CD pairs; all three unpaired TXT exports remain explicit blockers. Original model bytes survive at the two retained endpoints; other states alter only the producer-specified Engine rows. |
| `ae1` | All 100 original rows and six absolute Earth sensor outputs on nominal 40/80 interval meshes. Both unknown initial states remain blocked on both grids. The original model and its null Weight records remain byte-identical; positive-speed setup is explicitly conditional. |
| `ae3` | All 576 native output cells and 113 separately qualified embedded values. Six finite-control coefficient states run on nominal 80/160 grids; native derivatives/inertia/rates, embedded producer settings and five unpaired models remain explicit blocked scopes. |
| `st1` | All 197 native scalars from 27 files, both components of all 76 complex roots, and ten literal models. Two conditional static body-anchor position jobs repeat three cells on prospective 100/200 interval meshes; 194 other slots and nine model inventories stay blocked. Extra arrays and plots remain outside this native denominator. |


These are explicit comparison scopes, not claims that every variant, derivative,
sensor or dynamic result in those families is implemented. Historical setup
qualifications accompany each job.

All families remain in the report, including those without an executable
comparison adapter. A selected curve or snapshot can match without completing
its whole family. Output candidates are inventoried artifacts, not automatically
proven model/output pairs. Historical comparisons remain identified as historical;
they do not count as a fresh pass against the current implementation.

ST-1 compares `Decimal(str(predicted))` against the exact original token and its decimal half-last-place, consistently in the adapter, runner and independent summary. Existing families retain their declared precision conventions; no interval is widened to absorb binary rounding.

The comparisons preserve original model properties. Unknown historical settings
are explicit qualifications. They must not be hidden with fitted inputs,
widened tolerances or a choice of whichever mesh happens to agree best.

`scripts/summarize-isae-suite.py --run RUN_DIRECTORY --output-dir SUMMARY_DIRECTORY`
independently checks result accounting and produces a combined report. Repeat
`--run` for nonoverlapping batches. It rejects duplicate jobs and incompatible
reference or numerical-code versions; changes confined to the runner are retained
with their original hashes.

For AP-2/AE-1/AE-3/ST-1, independent summarization builds one canonical source context per
adapter and run, retains every job-field and physical-output check, and rehashes
unique inputs, helpers and kernel modules before publication. The cache is local
to that summary call; source changes or kernel inventory changes reject it.

A selected batch report describes only the supplied runs. Use the full default plan or the current family backlog for global adapter coverage; families absent from a selected batch may have comparisons registered elsewhere.
