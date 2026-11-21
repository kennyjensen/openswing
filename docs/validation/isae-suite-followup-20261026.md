# ISAE suite follow-up: startup rank and exact stations

Updated 2026-10-26. Comprehensive comparison with the archived ASWING calculations remains the development priority. **No entire family is fully validated.** All 41 families and 279 original models remain inventoried; seven adapters cover selected scopes in 18 families, and 23 families still lack adapters. The fresh inventory still accepts 211 original models and records 68 import failures.

The [broad baseline](isae-suite-current.md) is frozen against the preceding numerical implementation. This follow-up reruns the affected FFWT-1 and ST-4 scopes against the changed kernel. Its counts must not be merged into the baseline as if all other families had been rerun. [Machine summary](isae-suite-followup-20261026.json).

## Fixes and their scope

The source structural equations now have their own grounded rigid-tree initial-rank proof. Exact zero source compliances, smooth source angle charts, supported tree/hinge geometry and the unchanged circulation-block checks are required. The proof eliminates conservative wrenches and then rigid compatibility; it does not assume an energy Hessian, claim loaded stability, or enable the midpoint tangent for source equations. Other configurations retain the numerical fallback. This is a proof of the implemented source equations' rank, not a claim that historical ASWING used this certificate algorithm.

Scaled Weight stations now resolve to beam endpoints or declared discontinuities only when their original decimal expressions are exactly equal. This fixes the original ST-4 expression `48 × 0.0254 = 1.2192` without widening a distance tolerance. Original text and raw records remain intact. Geometry, structural/dynamic consumers, local point motion, wall-root handling, canonical serialization and edits share the resolved analysis station. Other attachment types remain outside this change.

Verification passed: 40 new source-rank checks, 39 existing rank checks, 68 existing source-equation tests, and 138 station/parser/editor/identity checks (including 33 new station checks; two physical-solve tests in that group were deliberately deselected). Independent source reviews passed. The actual original-model runs below supply the physical integration checks.

## Original case reruns

| Scope | Completed numerical jobs | Failed/time-limited | Unsupported jobs | Valid scalar comparisons | Strict archived matches |
|---|---:|---:|---:|---:|---:|
| FFWT-1 Flare10/A5, eight rows × two original meshes | 5/16 | 7 later Jacobian subsonic-guard failures; 4 timeouts | 0 | 20/64 | 0/20 available |
| ST-4 five vacuum Weight variants × three grids, plus retained blocked scopes | 5/5 runnable jobs; all 15 grids | 0 | 37 | 93/3,749 | 0/93 available |

All 16 FFWT requests and mesh preflights are byte-identical to the failed broad baseline. Every job advances beyond the initial tangent. Five completed equilibria pass all 205 physical checks, with maximum fresh residual `9.58e-13`; all eight two-mesh comparisons remain unavailable because at least one member failed. Row4 coarse took 110.57 seconds including native verification and predicts lift 8.28339234 N against 8.23892 N. A successful solve does not establish archived agreement. [Independent FFWT audit](isae-suite-followup-20261026/ffwt-review.json).

All 42 ST-4 job contracts are unchanged apart from implementation pins. Previously rejected 7d/7e/7f now run all three grids. All 15 grids pass 960 numerical checks, and all 93 required vacuum frequencies are available; 3,656 unsupported scalar slots remain explicit. Maximum finest-grid frequency differences are 0.278237% (7a), 0.309836% (7c), 0.567327% (7d, seventh root), 0.295257% (7e), and 0.296825% (7f). Every variant still fails at least one original 32→64 mesh gate. These errors are not accepted by changing tolerances or omitting high ordinals. [Independent ST-4 audit](isae-suite-followup-20261026/st4-review.json).

## Browser verification

The built offline app passes both original-model checks. Weight7d n16 passes 846 checks: its full base, A/M matrices, selected sixteen roots, full left/right residuals and saved-project restoration match the native run. Startup was 43.97 seconds; the solve was 17.97 seconds. FFWT row4 coarse passes the unchanged physical parity, literal/canonical input, preview and saved-project checks; startup was 40.05 seconds and its cold solve 44.47 seconds. Neither test made an HTTP request after switching offline. Timings are specific to these runs, not a controlled speedup measurement.

The FFWT test needed a synchronization correction: identical literal/canonical previews could satisfy old visible-plot checks before the new worker reply arrived. The first failed attempt and a subsequent stale test-packet rejection are retained; both performed zero solves. The final test waits for the exact new reply. No numerical threshold changed.

## Remaining high-priority work

The remaining FFWT Newton/flow failures and ST-4 refinement/reference differences are open. Coverage also remains incomplete inside registered families and across the 23 missing adapters. The next SA-11 adapter can reuse the existing polar worker, but its [source audit](isae-suite-followup-20261026/sa11-readiness.md) retains a roughly 104.7-fold force/coefficient normalization conflict in four of eight tables. All 328 rows must remain visible; no rescaling or fitted PG setting is justified. SA-12 still needs a ground-aware comparison adapter.

See the [complete family backlog](isae-suite-backlog.md) for every family, model, output candidate and remaining implementation step. The goal remains active. Original failures and unknown historical settings are preserved alongside successes.
