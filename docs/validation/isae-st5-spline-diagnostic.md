# ST-5 interpolation and discrete-load diagnostic

Updated 2026-10-25. **The isolated candidate is numerically converged but does
not yet reproduce the archived ASWING solution.** This study preserves the
original `JW_1_20lb_80_20` input. Experimental agreement is optional. Production
interpolation and the browser app are unchanged.

The subsequent [source-discrete comparison](isae-st5-source-discrete.md)
implements the structural/load averaging too, reaching much closer agreement
on the archived node grid. Its visual PDF review also corrects an earlier
text-only interpretation of the stiffness average. Results below remain the
completed spline-only study.

## Fixed interpolation rule

Official Drela XFOIL 6.97, AVL 3.27 and XROTOR 7.55 sources contain a segmented
cubic routine whose first and last intervals have zero third derivative,
with C2 continuity inside each segment. Two knots give a line; three give a
quadratic. For more knots this differs from not-a-knot interpolation.
OpenSwing currently uses natural, zero-second-derivative endpoints.

The source equations were specified before evaluating the candidate. The
historical ASWING caller remains unavailable: shared authorship does not prove
that ASWING used this routine. The primary implementation is `SEGSPL` calling
`SPLIND(...,-999,-999)` in the [official XFOIL archive](https://web.mit.edu/drela/Public/web/xfoil/xfoil6.97.tar.gz),
`Xfoil/src/spline.f`, lines 63–137 and 533–558.

Independent arithmetic on the original tables provides several discriminators:

| Archived quantity | Natural endpoints | Zero-third endpoints |
|---|---:|---:|
| EPS/tau entries consistent with propagated printed uncertainty | 108/160 | 160/160 |
| Chord/Cm entries, using a uniform endpoint-value average | 89/160 | 160/160 |
| Normal-projected weight entries, same uniform averaging rule | 20/80 | 76/80 |

The narrower output-half-unit-only counts for the candidate are 121/160,
153/160 and 56/80 respectively. The broader checks propagate printed input
coordinates and, where used, archived resultants/angles. They are separate
scalar consistency checks, not proof of one shared unknown coordinate per row.
EPS/tau recovery uses archived wrenches; weight projection uses archived angles.
Neither is an independent prediction of equilibrium.

The candidate forward clamped angles are 4.777734964° and −30.687604532°,
versus archived 4.777737° and −30.687611°. Natural interpolation gives
4.886146300° and −30.851726706°. The candidate removes most of that geometric
discrepancy, but the strict printed-angle checks still fail.

## Five unchanged-input physical comparisons

Only the compiled beam-table spline rule changes in this diagnostic. Original
source text, loads, stiffnesses, joints, solver tolerances and output decoding
remain fixed. Each cold solve has a separate fresh residual reconstruction.

| Forward/rear intervals | Native solve | Strict structural entries matched | Mesh checks against previous level |
|---|---:|---:|---:|
| 38 / 32 | 0.86 s | 117/1,120 | — |
| 76 / 64 | 1.06 s | 124/1,120 | 2/14 |
| 152 / 128 | 1.77 s | 124/1,120 | 7/14 |
| 304 / 256 | 3.65 s | 118/1,120 | 13/14 |
| 512 / 512 | 8.85 s | 116/1,120 | 14/14 |

The final grid is nested and respects the existing 512-interval-per-beam cap.
Its refinement rule was frozen before solving. All numerical gates pass;
maximum fresh residual is 8.21×10⁻¹⁵. The final mesh pair passes the predeclared
0.1% gate in all 14 structural measures, with maximum change 0.0312%.
An independent saved-array audit passes 8,209 checks, reconstructing all 400
sampled rows and all 56 mesh comparisons without importing the production code.

| Positive tip quantity | Archived ASWING | Candidate, finest mesh | Difference / absolute reference |
|---|---:|---:|---:|
| Forward vertical displacement, ft | 0.012013 | 0.011933944 | −0.6581% |
| Forward twist, degrees | −0.060040 | −0.058006445 | +3.3870% |
| Rear vertical displacement, ft | 0.006272 | 0.006261927 | −0.1606% |
| Rear twist, degrees | −0.059695 | −0.058949343 | +1.2491% |

No complete structural row passes strict printed precision. Some resultants
move farther from the archive under refinement; all errors remain in the
[machine-readable record](isae-st5-spline-diagnostic.json). The natural-rule
baseline has forward/rear displacement errors of −2.0638%/−1.5342% on its
152/128 grid. At that same grid, the candidate forward error is −0.5998%;
the finer candidate result above is a separate comparison.

## Discrete load and display interpretation

One uniform display hypothesis averages endpoint signed weights and projects
them onto the normal calculated from the arithmetic mean of archived endpoint
Euler angles. It explains all 70 finite-width `f_reac` rows within propagated
printed uncertainty. Four zero-width forward rows still fail: original lines
50, 56, 62 and 68, by −5.681×10⁻⁷, −5.200×10⁻⁷, −5.638×10⁻⁷ and
−1.3704×10⁻⁶ lb/ft. These failures are retained.

A separate original-node calculation sums endpoint-averaged weight times
undeformed endpoint chord length. It gives 38.5802312858 lb, within
1.50×10⁻⁶ lb of the decoded archived root-traction sum. Using unloaded arc
length gives 38.5802339653 lb instead. The finest 512/512 candidate gives
38.6150993 lb. This points to finite-mesh load averaging as a
specific remaining difference; it does not justify renormalizing the weights.

The [ASWING theory](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf)
defines unloaded **arc length** in Eq. 48 and arithmetic endpoint averages in
Eqs. 49–51, followed by conservative force/moment balances in Eqs. 55–56.
OpenSwing's midpoint sampling and rotation formulation differ from those
discrete equations. A closer chord-length total alone is insufficient reason
to replace the source-defined arc length. The next bounded comparison should
isolate the documented discrete operators and retain both numerical and
reference failures.

## Reproduction and compatibility

```sh
.venv/bin/python scripts/diagnose-isae-st5-drela-spline.py prepare --stage /tmp/st5-spline-new
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  .venv/bin/python scripts/diagnose-isae-st5-drela-spline.py run --stage /tmp/st5-spline-new
```

All five saved candidate equilibria are marked diagnostic-only from their
first disk write. They are not app-importable projects. Production adoption
would require explicit interpolation identity, preserved semantics for older
saved states, and separate treatment of beam tables versus time/Jangle tables.
No browser replay or production rebuild was performed for this isolated study.

The [evidence archive](isae-st5-spline-20261025-evidence.zip) preserves source
provenance, both fixed-rule diagnostics, the earlier preparation blockers,
five solved states, fresh physical fields and independent reviews. The
producer's original midpoint/scalar display fields are preserved; the later
display hypotheses are separate reports. The [production baseline](isae-st5-reference.md)
and its browser evidence remain unchanged. The full ST-5 family and project
goal remain incomplete.
