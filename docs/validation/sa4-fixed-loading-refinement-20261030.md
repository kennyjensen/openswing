# SA-4 fixed-loading refinement and a vortex-kernel correction

2026-10-30. **A real numerical error was found and corrected:** the finite-vortex
kernel incorrectly clipped nonzero velocity near the extension of a segment,
outside the segment itself. The analogous upstream-ray clipping is also fixed.
These locations are nonsingular; the change evaluates the same Biot–Savart
integral without the inappropriate absolute-distance cutoff. The existing
near-filament convention on the physical segment/downstream ray is unchanged.

The actual SA-4 refinement experiment is complete, but does not establish a
correction for its native drag discrepancy. The derived cosine-spacing term
passes all six tested loadings; modified cosine retains 10–20% prediction errors.
The complete native SA-4 diagnostic remains **562/588**. No new native reference
passes are claimed.

## The implementation correction

On a 1024-interval cosine refinement, a force receiver lies 1.25 segment lengths
from a neighboring bound segment's start and 4.25e−14 length units from its
extended axis. The old `distance_squared > 1e-26` test returned zero. Independent
90-digit arithmetic gives unit-circulation velocity approximately
`(-0.000134716, 0.000507476, 0.000328699)`.

The exterior finite-segment and upstream-ray formulas already use rationalized
expressions that remain finite as transverse distance approaches zero. The
[kernel correction](../../openswing/aero.py) allows those expressions to operate
there and removes the small-distance denominator floor in that nonsingular
region. It adds no vortex core, drag correction or fitted parameter. This is
consistent with the directed integral in
[Drela's steady formulation, Eq.160](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf).

The [regressions](../../tests/test_stable_vortex.py) now cover transverse distances
down to 1e−18, inverse-length scaling from 1e−12 to 1e6, the recorded rotated
SA-4 geometry, regularized fields and the retained singular-filament convention.
Before the correction, 8 checks failed and 9 passed in that test file. Afterward,
**194/194 targeted tests pass**, including factored fields, self influence,
filament subdivision, Trefftz, ground images and field/state derivatives.

Packaged Pyodide/WASM passes **1,413 scalar reference comparisons**, with outputs
equal to native Python for these fixtures. The largest relative reference
difference is 1.31e−8 in the ill-conditioned rotated SA-4 sample; the axial
references retain their 3e−14 relative target. The public and built kernels are
synchronized. This fixes a numerical defect, but its near-CD effect in the ten
comparable pre-fix states is at most **4.28e−13**; it does not explain the native
drag mismatch.

## Actual SA-4 experiment

All four failing CD-table states are included: 7.12392°, 7.60807° and 8.10951°
from the saved K36/N36 solutions, and 10.098° from K18/N18. Passing controls use
4.08069° from both retained representations. Every saved Fourier coefficient,
including numerical even-mode terms, is held fixed. No load distribution is
fitted, smoothed or re-solved.

The original `.asw` file, material arc, natural-cubic geometry, wind direction,
section data and force-receiver construction are retained. Each loading is
evaluated on uniform, cosine and modified-cosine meshes at 128, 256, 512, 1024
and 2048 intervals: **90 prescribed states**, plus six baseline replays.
Every mesh shares adjacent wake origins. The two largest counts use a research
mesh constructor, verified against all ten production geometry arrays at each
supported count/spacing. The public **512-interval limit remains unchanged**.

The precomputed candidate spacing term is

```text
Delta CD = rho/(4*pi*qS) integral Gamma^2 * (wind dot q')/|q'|
                                      * d(log H)/ds ds,
```

where q is the smooth nodal quarter-chord curve and H describes the material
spacing distribution. Quadrature is split at input spline knots. Its first
accuracy check failed; increasing quadrature order meets the same 2e−9 CD gate,
with final changes at most 1.83e−10. All predictions were retained before field
evaluation. The derivation is a candidate accumulated local asymptotic term,
not a general proof of the global force limit.

At N2048, errors against that prediction are:

| Spacing | Raw near-drag difference | Near-minus-Trefftz difference | Separate gates passed |
|---|---:|---:|---:|
| Cosine | 0.038–0.499% | 0.181–0.676% | 12/12 |
| Modified cosine | 10.82–20.33% | 9.99–19.18% | 0/12 |

Each comparison retains its original `max(1e-7 CD, 1% of prediction)` target.
These percentages describe the proposed spacing term, **not native ASWING error**.
All mesh levels and signs of prediction errors are in the
[complete table](../../artifacts/isae/sa4-fixed-loading-refinement-20261030/after-kernel-fix/report.md).

![SA-4 spacing prediction refinement](../../artifacts/isae/sa4-fixed-loading-refinement-20261030/after-kernel-fix/comparison.svg)

Independent long-double segment/ray calculations pass 3,072 vector comparisons,
with maximum scaled difference 8.34e−12 after the correction. The six baseline
replays reproduce saved near/Trefftz CD within 5.56e−17. All 540 retained
array/force checks pass.

**None of the refined prescribed states is a valid new equilibrium.** All 90
fail the residual criterion; 36 also exceed normal Mach 1, with a maximum of
16.4. These failures remain explicit. Holding Gamma fixed is useful for isolating
the force operator, but cannot establish refinement of the coupled nonlinear
solution or improve an ISAE score.

## What follows

The actual geometry supports the cosine-spacing mechanism quantitatively;
the modified-cosine result is unresolved. More nodes alone do not validate the
force recovery, and the newly found exterior-axis bug is too small to account
for the original drag error. The next scientific task is to localize the
remaining modified-spacing discrepancy and distinguish tip/geometry resolution
from the assumptions in the accumulated asymptotic term. The intended native
singular-force treatment remains unauthenticated. No empirical spacing or
near-field drag correction is warranted.

The subsequent [local geometry audit](../../artifacts/isae/sa4-local-geometry-20261030/report.md)
locates a sharp quarter-chord tangent reversal inside the dominant 95–98%
region. Even N2048 does not resolve its measured transition width. Independent
field calculations reproduce the large neighboring-bound influence, and
smooth-position/affine receiver changes retain most of it. Thus the finest
cosine agreement above is not evidence that this geometric feature is resolved.
The full discrepancy and native singular-force convention remain open.

[Protocols, failure records, fields and verification receipts](../../artifacts/isae/sa4-fixed-loading-refinement-20261030/README.md)
retain the initial quadrature failure, public mesh-cap rejection, failed field
audit, ten pre-fix fields, and every corrected result.
