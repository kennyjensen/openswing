# ST-5 shared-suite registration — 2026-11-03

The normal ISAE runner now registers **12 original ST-5 snapshots**, up from four.
This adds the four tested type-2 roller cases and the four distinct forward-only
cosine/elliptical-load cases. It preserves the existing four rigid cases and ST-3.
The structural adapter now has 13 jobs; ST-5 accounts for **70,632 required output
slots**, an increase of **44,712**. Each snapshot retains all original rows and
27 output fields on its existing three grids. Duplicate copies of forward-only
files do not create additional independent comparisons.

This is a test-runner change. The eight decoded targets and recovery implementations
match the retained studies; only path binding, operation counts and mesh-summary
reporting differ. All five pre-existing structural targets and generated recovery
implementations are unchanged. The production kernel and acceptance tolerances
are unchanged.

Validation completed:

- **409 tests pass** across structural registration, independent summary contracts,
  and the runner. These cover raw token preservation, model/output identity,
  duplicate rows, complete output counts, unchanged grids and tampered targets.
- Two fresh ordinary-runner jobs exercise the roller and forward-only paths:
  **six cold solves and six fresh residual checks pass**.
- **All 11,178 reported values match the earlier studies exactly**, as do every
  recovered row and numerical-check record. The separate saved-result summarizer
  also completes without changing counts or precision rules.

| Fresh shared-runner case | Raw scalar matches | Qualified matches excluding unresolved f_reac | Required slots | Mesh gate |
|---|---:|---:|---:|---|
| Roller 20 lb, 90/10 | 3,695 | 3,683 | 6,480 | Fail retained |
| Forward-only elliptical, 30 lb | 2,626 | 2,623 | 4,698 | Fail retained |

The runner correctly exits 1 because exact reference agreement is incomplete.
Both workers report `computed`; neither timed out or failed numerical convergence.
The raw summary includes coincident numerical matches in the unresolved reaction
column; those are excluded from qualified counts above. Conditional zeros and
input echoes are not independent physical predictions. These reruns add execution
coverage, not new independent reference data or whole-family validation.

The six actual solve calls total **16.57 s**. The serial worker phase takes
**46.54 s**, and the whole command takes **130.59 s**. The remaining **84.05 s**
cover preparation and reporting, including the full source-inventory rebuild.
Tests take **327.30 s**. Each worker used one BLAS thread, a 180 s limit and an
inherited 512 MiB address-space cap. No app build, browser rerun or distribution
packaging was needed. Worker validation now decodes only its selected snapshot
instead of rebuilding the full structural plan before each solve.

Run the registered ST-5 cases with:

```sh
npm run test:isae -- --adapters structure --cases ST-5 --workers 1 --timeout-seconds 180 --output-dir artifacts/isae/st5-current
```

For one snapshot per invocation, add `--max-new-jobs 1`, then repeat with
`--resume` and the same options/output directory. Use `--job-pattern` to select
an individual registered snapshot. Planning and missing outputs never count as
passing tests.

Evidence: [integration assessment](../../artifacts/isae/st5-suite-20261103/integration-assessment.json),
[ordinary suite report](../../artifacts/isae/st5-suite-20261103/integration/report.json),
[independent summary](../../artifacts/isae/st5-suite-20261103/summary/summary.json), and
[unchanged recovery check](../../artifacts/isae/st5-suite-20261103/recovery-equivalence.json).
The study retains the previous helper sources, and the ordinary runner freezes
all executed helper/kernel code. Existing detailed [roller](isae-st5-roller-20261103.md)
and [forward-only](isae-st5-forward-20261103.md) error summaries remain authoritative.

Remaining work includes historical node/exporter precision, failed refinement
checks, unresolved reaction display, additional joined-wing loading variants and
modal comparisons. A separate workflow improvement is reducing full-inventory
preparation for narrowly selected reruns while retaining selected-source integrity.
