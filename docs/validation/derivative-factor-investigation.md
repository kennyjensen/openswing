# Isolated derivative performance investigation

This investigation identifies complete centered Jacobian assembly as the remaining bottleneck. It does **not** establish a production speedup, general accuracy, ASWING parity, or experimental validation. The prototype remains isolated; no production modules were edited.

## Selected paired comparison

Both children restored the saved `20O-05-n128` equilibrium. Neither performed an equilibrium solve. Each had a 300-second cap; both completed and were reaped. The system had 1,702 unknowns and used the original `control.1` and `p` centered derivatives.

The candidate retained every original Jacobian entry and column scale, converted the scaled matrix to exact CSC storage, and reused one sparse LU. A conservative inverse-norm bound could certify the unchanged `1e-10` rank threshold; an inconclusive certificate used the original dense SVD and LU. The original complete `J dx + Rp` residual gate remained `1e-8`.

- All **2,896,804 raw Jacobian entries**, scaled entries, column norms, and parameter partials were entry-for-entry identical.
- All **13,342 physical numeric outputs** passed `2e-8` absolute plus `2e-8` relative, applied componentwise in each field's units. The largest dimensionless tolerance fraction was `0.04838`.
- Fresh full linear residual maxima were `6.24e-14` for baseline and `4.98e-14` for candidate.
- The candidate used one sparse factorization, no SVD, and no dense factorization. Its reciprocal-condition **lower bound** was `1.41335e-7`; it did not compute an exact reciprocal condition.

| Phase | Baseline, monotonic seconds | Candidate, monotonic seconds |
|---|---:|---:|
| Complete derivative call | 49.44 | 39.99 |
| Centered Jacobian and scaling | 45.99 | 39.06 |
| Rank check and optional sparse factor | 2.765 | 0.179 |
| Physical RHS solve and full residual | 0.207 | 0.00395 |

The factor-related phase reduction was about **2.79 seconds**. Jacobian assembly accounted for **93–98%** of the derivative call. It used identical code in both children but varied by 6.94 seconds under concurrent work. Therefore the observed total ratio of 1.24× cannot be attributed to the factorization change alone. Wall-clock derivative times were 89.63 and 59.25 seconds; the substantial wall/monotonic discrepancy is preserved, not averaged away. There were no timing-only retries.

## Synthetic controls and remaining coverage

The separate 60-second bounded synthetic child completed and was reaped. **25 of 26 cases passed, with 84 of 85 checks passing.** Singular, near-threshold, nonnormal, scaling/floor, tiny-entry, inverse-failure/corruption, physical-RHS failure/corruption, and failed dense-fallback controls behaved as required. Original source and all outcomes remain immutable.

The retained failure is a string matrix rejected with `TypeError` instead of controlled `AnalysisError`. The numeric derivative assembly cannot generate this input, but a separate revision should fix the helper API and add its regression test.

This candidate still needs forced fast-path coverage for free flight, feedback, branch transitions, actual Pyodide, and browser serialization/rendering. In particular, `web/main.js` currently calls `toExponential` on the exact reciprocal condition; the candidate’s explicit `null` exact value requires a labeled lower-bound display. Existing tests that require a numeric exact reciprocal condition must retain their dense-path meaning.

## Next implementation strategy

The static Newton and BDF Newton matrices lag nonlocal fields and use forward differences. They are not interchangeable with this derivative Jacobian. The complete mounted correction and `linear_dynamics` tangents reconstruct moving-field physics, but use different direct/refined stencils and, for dynamics, a different rotation/state chart. Physical completeness alone does not establish equality with the original centered columns.

The next isolated revision should first own a bounded exact `TangentInfluences` cache around the unchanged complete centered probes. Then it should group only mechanical/reaction columns with proven disjoint full-residual supports, preserving the exact perturbations, branch checks, division order, and all rows. A subsequent narrow mounted frozen-influence geometry path may group geometry probes only after proving complete supports; frozen influences still retain moving normals, kinematics, load transfer, and structural geometry. Free-flight, feedback, engine/body, branch-sensitive, and unsupported layouts retain the original full-column fallback until separately covered.

Any adaptation of the complete analytic/refined tangent is a separate numerical-method change requiring full-matrix comparisons and step-refinement evidence. No further physical run or production promotion was performed.

Machine-readable evidence: `benchmark-report.json`, `synthetic-controls/report.json`, `structured-tangent-assessment.json`, `closeout.json`, and the terminal `artifact-pins.json`. Original plans, sources, raw matrices, outputs, clocks, exceptions, and process outcomes are retained alongside them.

The [machine-readable record](derivative-factor-investigation.json) and [complete evidence archive](derivative-factor-investigation-20261024-evidence.zip) preserve the original scripts, source snapshots, matrices, outputs and failures.
