# Selective custom-trim sensor evaluation

Updated 2026-11-05. The full nominal20 AE-2 sensor-coordinate solve now takes
26.78 seconds, compared with 103.64 seconds in the retained
earlier run. All 6,269 compared numerical outputs are exactly unchanged.
This is a 3.87x observed before/after ratio, not a repeated benchmark;
host load and startup vary. Native ISAE scores and acceptance thresholds do not change.

## Implementation and retained accuracy checks

`evaluate_custom` now reads the declared sensor references. An explicit allowlist
of position, motion, attitude and airflow fields uses the same `measure_sensor`
equations, actual moving pylon, operating condition and aerodynamic sensor flow
as the complete report. Only requested sensor rows are measured. Nonconsecutive
IDs keep their original airflow-row association.

Any structural-load, strain, curvature, shell-stress or circulation reference
keeps full section recovery. Unknown future fields also keep that path.
Unselected expression branches preserve lazy handling of undefined values.
Complete exported sensor and section reports are unchanged.

Only `openswing/custom_constraints.py` changes in the production kernel.
The Newton/continuation and final tangent-check function bodies are unchanged,
as checked against the retained pre-change source. All centered and one-sided
stencils, rank/smoothness checks, residual tolerances and wall-clearance rules
remain. This removes unconsumed reporting work; it changes no aerodynamic or
structural equation and introduces no fitted parameter.

## Verification

All **63 distinct Python tests pass**: 16 new measurement comparisons, four
wall-root independent-speed comparisons, and 43 existing custom trim,
controller, allocation, launch and response tests. The new tests cover both
flow modes, legacy/source steady/source moving operators, elastic motion,
offset pylons, gusts, sparse sensor IDs, undefined axes/flow and mixed structural
expressions. Every nonstructural field is compared against the complete report.

The actual built workbench completes one sensor-constrained wall-root solve
offline. All **11 browser gates** and **1,695 Python/browser numerical
comparisons** pass, including the independent 10 m/s target and full rank and
smoothness gates. Its measured solve time is 6.56 seconds. This browser case
is the small wall-root control, not the full AE-2 model. The original independent
8/10 m/s controls are retained; one fresh Python custom solve and one fresh
browser custom solve are performed using the current kernel.

Two initial capped pytest attempts produced no completed result. A diagnostic
trace identified slow pytest failure-source formatting after a new fixture
mistake: `elastic_motion` requires four arrays, not a `NetworkMotion` object.
After correction, all 15 flight-condition cases passed. The separate no-airflow
fixture then required its engine to be removed; it subsequently passed. Those
fixture errors and all capped batch logs remain available. Only unfinished tests
were resumed; completed IDs are counted once. Short tracebacks avoid repeating
the expensive failure formatter. No production or tolerance adjustment was made
to satisfy these tests.

## AE-2 continuation results

The original source, requests, initial states and physical settings are retained.
The target is **sensor RY = 0.24 m**, used as a continuation coordinate while
solving airspeed. It is not an archived ASWING validation target.

| Requested mesh | Actual panels / nodes | Solve time | IAS | Heading Psi | Sensor V | Sensor beta |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Nominal20 | 21 / 22 | 26.78 s | 17.92343329 | 18.42213917° | 17.90899172 | −14.90458050° |
| Nominal40 | 41 / 42 | 51.26 s | 17.91766039 | 18.39979538° | 17.90170388 | −14.92998683° |

Both cases pass 15 independent physical checks, including a freshly restored
full residual, load balance, clamp conditions, sensor target, rank and smoothness.
The coarse result matches all 6,269 compared values from the earlier implementation
exactly. Execution counters/initialization text and the cancellation-sensitive
one-sided diagnostic are excluded from the output comparison; original diagnostic
acceptance gates are still enforced separately.

The finer result supplies an accepted state where the previous attempt was
stopped without one. From nominal20 to nominal40, changes are 0.0322% in IAS,
0.1214% in heading, 0.0407% in sensor speed and 0.1702% in sensor beta.
RY is imposed, so its zero change is not an independent convergence result.
These are observed changes, with no post-hoc pass threshold. Further refinement,
branch stability and historical setup remain open. This does not locate a fold,
prove absence of another equilibrium, or resolve the archived 17 m/s result.

The registered AE-2 baseline remains **2/2,200**; the earlier conditional native
18–20 m/s branch remains **0/24 strict matches**. No native reference cells are
added by this performance study. Other ISAE families and the full ASWING goal
remain incomplete.

## Evidence

- [Machine-readable report](selective-custom-sensors-20261105.json), with kernel and evidence hashes.
- [Distinct-test record](../../artifacts/isae/selective-custom-sensors-20261105/test-summary.json).
- [Complete AE-2 output comparison](../../artifacts/isae/selective-custom-sensors-20261105/ae2-output-parity.json).
- [Two-mesh observations](../../artifacts/isae/selective-custom-sensors-20261105/ae2-mesh-comparison.json).
- [Offline browser report](../../artifacts/isae/selective-custom-sensors-20261105/browser/report.json).
- [Original profiling experiment](../../artifacts/isae/ae2-custom-profile-20261105/README.md).
- [Preceding wall-root fix and unfinished attempts](wall-root-custom-trim-20261105.md).
