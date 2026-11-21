# SA-3/SA-4 spline endpoint comparison

Updated 2026-10-29. Switching the existing beam interpolation policy from
natural endpoints to Drela's SEGSPL endpoints does **not** resolve the
selected SA-4 failures. Twenty fresh paired calls give **45/70** accepted
outputs with natural endpoints and **42/70** with SEGSPL. The fine 4.06°
case fails with both, and the SEGSPL 7.06° fine case also fails. No production
equation, mesh default or registered ISAE score changes.

## Source distinction

Both endpoint rules occur in Drela's retained source:

- `SPLINE` imposes zero second derivatives at the ends. This is OpenSwing's
  existing `natural-v1` default.
- `SEGSPL` calls `SPLIND` with `−999,−999`, imposing zero third derivatives
  on the first and last intervals. This is the existing `drela-segspl-v1`
  option. It is not the general not-a-knot rule.

Both have C2 interior continuity, independent segments at doubled stations,
and a straight line for two points. The current implementations and their
independent rational coefficient tests already cover this distinction; the
audit found no new spline implementation defect. The ASWING guide specifies
cubic interpolation and break behavior but does not identify its historical
endpoint caller. The earlier ST-5 comparison supports investigating SEGSPL,
without proving which rule generated the SA-3/SA-4 archives.

Sources: [retained JVL routines](../../reference/third_party/jvl/src/spline.f), lines
21–58 and 514–526; [ASWING guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt),
local lines 1064–1078; [ST-5 interpolation study](isae-st5-spline-diagnostic.md).
The [source review](../../artifacts/isae/sa34-spline-endpoints-20261029/source-review.json)
retains the exact source identities and qualifications.

## Geometry sensitivity

Ten geometry pairs regenerate the ordinary cosine mesh under each policy,
holding original interval counts and all literal input tables fixed. SA-1,
SA-2 and SA-5 change only at roundoff level: maximum coordinate changes are
below 2.7e-15 in model units, and all sampled aerodynamic properties are
identical. Their substantial remaining discrepancies therefore have no
corresponding substantive difference between these two interpolation laws.
No new aerodynamic calls were made for those three cases.

Curved SA-3/SA-4 geometry changes materially. A separate calculation holds
the original parameter samples, material lengths and Glauert fractions fixed
to distinguish interpolation effects from remeshing:

| Case | Intervals | Maximum frame change, regenerated mesh | Maximum frame change, fixed samples | Maximum control-point shift, fixed samples |
|---|---:|---:|---:|---:|
| SA-3 | 100 | 1.572° | 1.561° | 2.702 mm |
| SA-3 | 200 | 2.078° | 2.772° | 2.626 mm |
| SA-4 | 80 | 0.151° | 0.386° | 20.905 mm |
| SA-4 | 160 | 1.469° | 1.450° | 21.498 mm |

SA-3 control-point shifts use 7.04348° incidence. SA-4 maxima span 0°, 0.29°,
4.06° and 7.06°. In the fixed-sample study, geometric positions, frames and
properties change while the natural lengths/fractions remain fixed; it is a
sensitivity discriminator, not a proposed consistent mesh. The flow study
below uses the regenerated, internally consistent meshes instead.

## Fresh paired flow results

Each row has one fresh cold call per interpolation rule on the same current
kernel. Physical settings, original interval counts, default cosine recipe,
solver strategy, numerical gates and archived targets are unchanged. There
is no combination with the earlier modified spacing, node-count or interior
frame candidates. The process-local parser wrapper records the actual model
and distribution policy; it changes no literal ASW input data.

| Case | Intervals | Incidence | Natural | SEGSPL |
|---|---:|---:|---:|---:|
| SA-3 | 100 | 7.04348° | 7/7 | 7/7 |
| SA-3 | 200 | 7.04348° | 7/7 | 7/7 |
| SA-4 | 80 | 0° | 2/7 | 2/7 |
| SA-4 | 160 | 0° | 2/7 | 2/7 |
| SA-4 | 80 | 0.29° | 7/7 | 7/7 |
| SA-4 | 160 | 0.29° | 7/7 | 7/7 |
| SA-4 | 80 | 4.06° | 7/7 | 7/7 |
| SA-4 | 160 | 4.06° | Solve failed | Solve failed |
| SA-4 | 80 | 7.06° | 3/7 | 3/7 |
| SA-4 | 160 | 7.06° | 3/7 | Solve failed |
| Total | | | **45/70** | **42/70** |

All 20 child processes exited zero, were reaped, and had no timeouts or
retries. They returned 17 valid solutions and three solver errors. Maximum
accepted normalized circulation residual is 3.477e-14; maximum accepted normal
Mach is 0.736668. A process finishing successfully does not make a reported
solver error a valid physical result. All failed solves contribute zero matches.
Independent saved-result verification passes 1,959 audit checks with zero
mismatches, including actual parser policy, process eligibility, raw numerical
gates and independent 3% arithmetic. There are zero gained and three lost
reference checks, all from the additional fine-grid 7.06° failure. Raw-result
hashes were established and rechecked by that audit; they are not claimed
as contemporaneous execution hashes.

At 7.06°/80 intervals, CD improves only from **7.280% low to 7.103% low**;
CDi stays about **6.70% low**, and efficiency **7.32% high**. At zero incidence,
the fine-grid absolute CL/Cm errors change from **4.827e-6 / 4.056e-6** to
**4.866e-6 / 4.082e-6**. Thus the small-load discrepancies also persist.
The two SEGSPL SA-3 controls pass all outputs, with maximum errors **1.698%**
and **2.036%** on their respective grids.

The result rejects a spline-policy switch as a standalone remedy for these
failures. It does not prove that natural endpoints are historically correct,
or that SEGSPL is wrong: both were already mathematically defined candidates,
and historical caller identity must come from independent evidence. These
ten pairs do not establish a new complete-case score or mesh convergence.

## Evidence and remaining source question

The public CASEI SCN listings offer a separate geometry comparison. The
retained CASEI model has rigid stiffness, zero twist and literal `y=t`, but
the archived current `y` differs from `t` near the tips. Both spline rules
reproduce a linear `y(t)` exactly, so this cannot identify the endpoint rule
by itself. CASEI also differs from registered SA-3 geometry and must not be
silently substituted for it. The earlier [CASEI metric audit](sa1-scn-load-audit-20261027/metric-report.md)
already evaluates natural-spline Eq.48 box geometry. A new independent
second-derivative implementation extends that calculation to zero-third
endpoints, keeping the original CASEI data, printed stations and arc quadrature.
It makes no production imports or physical calls.

| CASEI listing | Maximum y error, natural | Maximum y error, zero-third | Rows within 0.05 mm, natural → zero-third |
|---|---:|---:|---:|
| N6 | 4.547 mm | 2.798 mm | 1/3 → 1/3 |
| N12 | 1.948 mm | 1.468 mm | 3/6 → 3/6 |
| N96 | 0.099 mm | 0.165 mm | 44/48 → 42/48 |

The natural results reproduce the prior audit exactly. Tightening the arc
quadrature tolerance changes coordinates by at most 2.082e-13 m. Zero-third
endpoints reduce the coarse errors but worsen the fine listing, and neither
rule reproduces all coordinates. These counts compare central printed t
values and propagate no t rounding; they are not rigorous interval-consistency
tests. Exact producer input and `D=0` listing provenance remain qualifications.
This independent coordinate evidence also fails to select a historical caller.

- [Ten regenerated geometry pairs](../../artifacts/isae/sa34-spline-endpoints-20261029/geometry-report.json)
  and [geometry execution receipt](../../artifacts/isae/sa34-spline-endpoints-20261029/geometry-terminal-receipt.json).
- [Four fixed-sample geometry comparisons](../../artifacts/isae/sa34-spline-endpoints-20261029/fixed-samples-report.json)
  and [their verification/terminal receipt](../../artifacts/isae/sa34-spline-endpoints-20261029/fixed-samples-terminal-receipt.json).
- [Predeclared flow protocol](../../artifacts/isae/sa34-spline-endpoints-20261029/protocol.json),
  [independent protocol review](../../artifacts/isae/sa34-spline-endpoints-20261029/protocol-review.json),
  [every physical comparison](../../artifacts/isae/sa34-spline-endpoints-20261029/report.json),
  [root execution receipt](../../artifacts/isae/sa34-spline-endpoints-20261029/root-execution-receipt.json),
  and [independent saved-result review](../../artifacts/isae/sa34-spline-endpoints-20261029/saved-result-review.json).
- [Six conditional CASEI geometry cases](../../artifacts/isae/sa34-spline-endpoints-20261029/scn-box-spline/report.json)
  and [their terminal receipt](../../artifacts/isae/sa34-spline-endpoints-20261029/scn-box-spline/terminal-receipt.json).

The two failed geometry-preparation attempts are retained under `preparation-r0`
and `preparation-r1`: a blocked-job inventory access and a terminal path-check
typo were corrected before protocol creation. Neither attempt made a physical
call; their preliminary arrays are not accepted flow evidence.
