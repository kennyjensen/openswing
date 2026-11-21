# SA-4 circulation initialization diagnostic

Updated 2026-10-29. Reusing the preceding converged circulation does **not**
recover the unresolved 160-interval solution at 4.06 degrees. No new archived
precision match is obtained. The registered SA-4 count remains **0/588**.

The original lift driver builds 22 operating points and invokes `XX` once.
Its output table contains 21 rows: the declared 8.06-degree point is absent.
This diagnostic computes that point when reachable but does not score it.
The first incidence is taken from the archived printed `-0.0`; historical
startup is unspecified. The intermediate `!A 0.016150740242261596` command is
overwritten by `!A 0.29` on the same operating point.

The manual documents copying operating settings when adding a point. It does
not establish that historical `XX` uses the preceding converged circulation
as a Newton guess. This is an explicit current-equation initialization study,
not a claim to have recovered historical ASWING startup.

| Structural intervals | Computed states | Accepted supplied guesses | Successful cold fallbacks | Failed states | States blocked after failure | Archived matches |
|---:|---:|---:|---:|---:|---:|---:|
| 80 | 22/22 | 17 | 4 | 0 | 0 | 0/147 |
| 160 | 9/22 | 7 | 1 | 1 | 12 | 0/147 |

Each sequence begins with one cold solve. The 160-interval failure also
attempts a cold fallback, so that sequence has two attempted fallbacks, one
successful and one failed. Its 12 blocked points include the unscored 8.06
point. There are 210 valid reference comparisons across both sequences; the
remaining required comparisons have no valid prediction.

At 4.06 degrees on 160 intervals, the supplied-guess Newton attempt stops at
normalized residual **0.0932482**. Automatic cold continuation and its existing
direct fallback also fail, ending at **0.197719**. Both exceed the unchanged
`1e-8` physical residual gate. The largest residual among accepted states is
`9.33e-13`. The two sequence processes finish in 8.21 and 7.05 seconds;
these are diagnostic timings in this environment, not ASWING or browser timings.

Among valid failed comparisons, median absolute errors are **CL 0.260%, CD
0.401%** for all 21 coarse-mesh reference states, and **CL 0.0737%, CD 0.0553%**
for the nine computed fine-mesh states. The fine-mesh sample stops at 3.59
degrees, so these medians cannot be used as a mesh-convergence comparison or
substituted for the full registered SA-4 errors. Near-zero-incidence references
produce large relative-error outliers; the
[saved analysis](../../artifacts/isae/sa4-operating-sequence-20261029/analysis.json)
retains every channel, sample count, maximum and tiny-reference partition.

Two additional current-code cold comparisons at 6.55 and 7.06 degrees on
80 intervals confirm **different numerically accepted solutions at identical
settings**, depending on initialization. Relative to the sequence, cold CL is
lower by `0.000316445` and `0.000340587`; CD is lower by `0.0000224663` and
`0.0000281576`. Both cold results pass the original numerical checks. This
establishes initialization sensitivity, not historical root selection or
physical stability. Comparing only against the older baseline would not have
isolated initialization because its recorded kernel version differs.

The new `initial_circulation` keyword in `solve_rigid` and
`evaluate_aerodynamics` accepts a copied finite physical circulation vector.
It corrects that guess using the unchanged residual and existing analytic
Jacobian where available. In automatic mode, a failed seed attempt returns
to the original cold algorithm. Prescribed circulation remains a separate
operation. Shape, Fourier representation, physical residual and local Mach
checks remain enforced; no reference tolerance or physical parameter changes.
The default path without a supplied guess is unchanged.

All 30 new initialization tests pass. The initial combined run also passed
32 existing fallback/polishing tests but exposed one new negative-test failure:
nonfinite seeded output raised the wrong exception before attaching metadata.
A narrow rejection before residual evaluation fixed that failure; the new
30-test suite passed on recheck. The original failure is retained.

The sequence runner retains raw solved outputs before numerical verification,
checks finite circulation/loads/coefficients, independently reconstructs total
force and moment, and verifies coefficient normalization and drag decomposition
at the original `2e-10` gate. It stops after any failed state and never carries
an invalid circulation to the next point. All source pins are checked before
and after execution.

Evidence: [80-interval sequence](../../artifacts/isae/sa4-operating-sequence-20261029/n80/report.json),
[160-interval sequence](../../artifacts/isae/sa4-operating-sequence-20261029/n160/report.json),
[matched current cold comparisons](../../artifacts/isae/sa4-operating-sequence-20261029/current-cold-comparison.json),
[source/API review](../../artifacts/isae/sa4-operating-sequence-20261029/source-review.json),
and [native test receipt](../../artifacts/isae/sa4-operating-sequence-20261029/initialization-tests/receipt.json).

The focused [native/offline-WASM witness](../../artifacts/isae/sa4-operating-sequence-20261029/wasm/execution-receipt.json)
passes both synthetic pointwise and Fourier cases. It compares 2,124 numeric
values with maximum scaled difference `1.92e-11`, below the predeclared `1e-9`
gate; warm and replay residuals remain below `2.64e-14`. All 130 synchronized
native/dist modules match and the run makes no network requests. These are
kernel witnesses, not a browser UI performance measurement. Build verification
is recorded separately from these numerical checks.
