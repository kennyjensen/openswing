# AE-3: full native-export validation adapter

Observed 2026-11-11 UTC. The adapter now computes every numerical channel in
the six archived `Straight_20O.fmat` exports. The original **725-target** ledger
is unchanged: 612 native comparisons (576 distinct native values, with the
36 finite coefficients checked on two meshes), plus 113 separately qualified
embedded postprocessor values. Enabling a calculation does not count as a pass.

## Audited results

The bounded replay currently gives **229/725 passing at 5%** (205 at original
printed precision): **324 computed, 95 mismatches and 401 uncomputed**. This is
an expansion of comparison coverage, not a claim that the physical model has
improved. The nine completed coefficient states agree with the earlier replay
within **1.475e−17** absolute coefficient difference.

| Output group | Passing / required | Computed | Mismatches | Uncomputed |
|---|---:|---:|---:|---:|
| Finite coefficients, both meshes | 36/72 | 54 | 18 | 18 |
| Native derivatives | 88/252 | 126 | 38 | 126 |
| Native mass/inertia/centroid | 87/252 | 126 | 39 | 126 |
| Native normalized rates | 18/36 | 18 | 0 | 18 |
| Embedded original-ASWING locked curves | 0/43 | 0 | 0 | 43 |
| Embedded ASWING-m locked curves | 0/43 | 0 | 0 | 43 |
| Embedded ASWING-m rolling curves | 0/27 | 0 | 0 | 27 |
| **Total** | **229/725** | **324** | **95** | **401** |

All native output groups completed for operating points 1–3. Coefficients also
completed on both grids at point 4 and the coarse grid at point 5. Eighteen
computed jobs pass **522 base physical checks and 129 auxiliary checks**; the
maximum fresh residual is **3.676e−13**. All **67 adapter and suite integration
regressions pass**, in ten small serial groups; earlier fixture failures and
capped test attempts are retained separately.

Typical errors among computed failures are **44.88% for Cl**, **50.92% for CX**
and **48.55% for derivatives** (range 7.52–231.57% for failed derivatives).
For inertia, 32/39 failures have reference magnitude at or below 1e−8 and retain
the original absolute gate. The other seven have median relative error
346.53%; these are also small entries. The largest absolute error across all
39 failed mass/inertia fields is **3.004e−5** in the native dimensional units.
Large percentages in these small entries are not comparable to a percentage
error in the dominant diagonal inertia.

The 401 uncomputed targets comprise **180 in six timed-out jobs, 108 in six
not-yet-run jobs, and 113 source-blocked embedded targets**. The first point-4
derivative retry also timed out under the same limits. All 25 numerical child
attempts were reaped: 18 completed and seven timed out, including that retry.
No numerical replay remains running. Interrupted tests do not count as failed
physical comparisons. The host showed large UTC/monotonic-clock discrepancies,
and a bounded stack diagnostic caught significant time in SciPy imports;
these observations do not prove the cause of every timeout. The runner
retains exact timestamps and measured durations, including delayed delivery
of a timeout on a suspended/slow host.

The [saved assessment](../../artifacts/isae/ae3-native-adapter-20261111/assessment.json)
checks strict results, reconstructed mappings, current source pins and the 5%
policy. The [test assessment](../../artifacts/isae/ae3-native-adapter-20261111/test-assessment.json)
contains all 67 distinct passing test names via checksummed JUnit files. The
[isolated retry](../../artifacts/isae/ae3-native-adapter-retry-20261111/) preserves
its own identical source/settings plan. The earlier **50/725** comparison and
qualified alternative-constraint sweep remain historical, separate evidence.

## Calculation and conventions

The [adapter](../../scripts/isae_suite_ae3.py) keeps the original finite-control
equilibria on nominal 80/160 meshes. The new
[observable module](../../scripts/isae_ae3_observables.py) evaluates the native
derivatives, mass properties and normalized rates on nominal 80. All literal
model bytes and base operating conditions from the
[previous replay](isae-ae3-current-20261111.md) are retained. No production
equations, physical parameters or numerical acceptance gates were changed.

For each derivative job, one complete coupled matrix factorization serves
seven right-hand sides: fractional speed, alpha, beta, normalized p/q/r and
file-unit F1. The calculation includes elastic and circulation responses,
moving induced-field geometry, analytic mechanical/circulation/control blocks,
and fourth-order local geometry differences. Outputs use fixed base stability
axes and dynamic-pressure normalization; angular inputs are radians. The
scaled full-matrix rank gate remains in place. This extends the
[independently verified control-response method](isae-ae3-control-response-20261111.md);
it does not substitute the geometry-lagged Newton matrix for a physical tangent.

The moving-source operator is checked against the original stationary source
at equilibrium and at two perturbed physical states before it supplies rate
partials. Full tangent directions, refined input/output differences and all
seven linear residuals must pass. Accelerations are explicitly held fixed;
the original `MM` constraint convention remains an unresolved setup question.

Drela's steady technical description, **§8.7, pp. 54–57, Eqs. 237–256**, defines
reported mass/inertia integrals separately from the solution equations. The
previous blanket block on native mass properties was therefore unnecessary.
The adapter verifies this literal model's zero real mass and section/point
inertia. It reports the native zero-origin display convention while retaining
`physical_real_centroid: null`; it does not invent an apparent-mass centroid.
Apparent tensors use the actual deformed section normals, midchord offsets and
interval lengths. All six spatial-mass columns are independently recovered
from positive/negative acceleration loads and checked against those integrals.
The report tensor is never substituted for a structural descriptor matrix.

Saved-result validation independently reconstructs each tensor entry, normalized
rate and derivative-channel mapping. Missing checks, changed normalization,
nonfinite values, inconsistent recovered tensors and invalid rank evidence
cannot produce a computed comparison.

## Remaining reference limitations

All 113 embedded targets remain required and explicitly unavailable: 43
original-ASWING locked-wing values, 43 modified-ASWING locked-wing values and
27 modified-ASWING rolling values. Their exact producing inputs, constraints
and control/observable conventions are not uniquely paired. The report's
Reynolds-dependent ASWING-m lookup is not supplied as executable source and
must not silently be replaced by the original constant-coefficient model.
Five unpaired model records remain visible with zero targets and no passes.

Jan's **Part IV, §3.3, pp. 13–14**, distinguishes mounted rolling-moment and
free-rolling experiments, explains the ASWING-m Reynolds correction and notes
the unavailable experimental mass/inertia distribution. The
[authoritative index](aswing-authoritative-references.md) and
[checksummed catalog](aswing-authoritative-sources.json) identify the retained
primary sources. This extension provides a complete **native-file comparison**
under declared assumptions; it does not establish exact historical settings
or complete AE-3 validation.

## Bounded replay

The [serial runner](../../scripts/replay_isae_ae3_bounded.py) defaults to one new
job per invocation. Repeating the command resumes the same pinned plan; code
or setup changes require a new directory. Every worker uses one BLAS thread
and the unchanged 512 MiB address-space / 15 CPU-second / 25 wall-second caps.
Each child is reaped before the next launch, and timeouts remain unavailable.

```sh
.venv/bin/python scripts/replay_isae_ae3_bounded.py \
  --output-dir artifacts/isae/ae3-my-replay --plan-only
.venv/bin/python scripts/replay_isae_ae3_bounded.py \
  --output-dir artifacts/isae/ae3-my-replay --max-new-jobs 1
```

Use `--job-pattern '*001-derivatives'` to select one native derivative export.
The summary still contains the entire 725-target denominator. The ordinary
`run-isae-suite.py --adapters ae3` path also includes the new outputs.

The current run, original strict results, 5% acceptance views, physical checks
and terminal receipts are retained in
[ae3-native-adapter-20261111](../../artifacts/isae/ae3-native-adapter-20261111/).
