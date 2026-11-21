# Endpoint candidate regression: test-path repairs

Fourteen further failures reproduce with the unchanged baseline solver. The repairs below preserve physical matrix and residual checks while selecting the paths those tests intend to exercise. All 25 selected tests pass on both baseline and endpoint candidate modules. The 97 production modules are unchanged, and the endpoint candidate has not been applied.

| Tests | Original failures | Repaired checks per source | Change |
|---|---:|---:|---|
| Grouped network Jacobian | 11 | 12 | Explicitly select the retained finite-difference mechanical/circulation fallback; keep exact full-matrix equality and original call counts. |
| Structured initial frames | 1 | 6 | Select the mechanical fallback for grouped/individual comparison; retain subsequent direct-column, complete-border and zero-load matrix checks. |
| Dynamic/trim load evaluation | 1 | 2 | Check exact trial/detailed residual equality at nonzero motion and complete output recovery; trim must still compute its CL constraint. |
| Newton retained source maps | 1 | 5 | Refine the same direct geometry/structural path as the coarse Newton matrix; keep all accuracy, refinement and state-restoration gates. |

## DAE refinement diagnosis

The coarse Newton matrix uses direct geometry and structural blocks. The old fine-step test omitted both flags, so it changed approximations while reducing the step. Its maximum scaled error was 0.000243352, compared with 0.000307930 for the current coarse matrix. That mismatch failed the original refinement gate.

With identical derivative paths, reducing the step from 1e-6 to 3e-7 lowers the maximum scaled error to 0.0000923778, a ratio of 0.299995784. The original requirement of less than half the coarse error is retained. Independent fourth-order differences of the complete nonlinear residual at steps 3e-6 and 1e-6 agree to 5.07291e-08 in the same entrywise metric, |difference| / (1 + |reference|). All 342 geometry columns of the 727-row DAE fixture are included.

The source-map-disabled coarse reference has error 0.00694449. The repaired test still requires the current coarse matrix to improve that reference; other established cases retain their 2e-5 bound. These first-order, off-equilibrium Newton errors do not measure error in an accepted physical solution or justify relaxing its residual tolerance.

## Scope and remaining gate

Earlier work repaired ten failures in scalar retry dispatch, geometry fallback selection and input-column reuse. Together, 24 observed failures have baseline reproductions and test-only repairs. The original full candidate run remains untouched. Its progress snapshot at this audit is 2727 of 2,989 outcomes, with 24 failures. Progress is not a completed regression result.

No numerical tolerance, physical residual, solver algorithm or validity guard changed. Complete the original broad run and assess any further failures before applying the isolated zero-radius endpoint parser fix. Experimental validation and the swept force-velocity defect remain separate unfinished work.

The evidence bundle includes the DAE matrices and probe, original/repaired tests, exact source manifests, baseline/candidate logs and the full-run progress snapshot. The current released application remains SA-12.
