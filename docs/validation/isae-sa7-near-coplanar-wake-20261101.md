# SA-7: near-aligned wake quadrature accounts for most of the 18° coarse-grid error

2026-11-01. The two straight wake traces align at **17.7678°**. At 18° they
are separated by only **2.025 mm** in the wind-normal plane. This is where
the two coarse grids from the reported-count study give strongly different CDi.
The investigation below uses all 58 saved strength-40 states; no new aircraft
solve, browser test or build is run.

## Isolating quadrature from circulation

The projected gap follows directly from the model's wing offsets:

`h = 0.1525 cos(alpha) - 0.4759 sin(alpha)` metres.

The current Trefftz calculation evaluates the source filaments at each target
strip's Glauert midpoint. The exact mutual-sheet integral can instead be
calculated while retaining the same piecewise-constant circulation. For source
endpoints `c,d` and target endpoints `a,b` in the Trefftz plane, its endpoint
kernel is

`K = log(|b-c|²) + log(|a-d|²) - log(|a-c|²) - log(|b-d|²)`.

The directed mutual contribution is
`CDi_ij = Gamma_i Gamma_j K / (4 pi U² Sref)`.
This follows by integrating the infinite-filament velocity along the target
strip. It is symmetric under exchange of source and target. All distances are
nonzero for the saved states. No circulation interpolation or native target
enters this calculation.

At 18° with 20 intervals per wing:

| Quantity | Value |
|---|---:|
| Archived native CDi | 0.265852 |
| Current discrete CDi | 0.236351876 |
| Difference from native | −0.029500124 |
| Error in the summed mutual-sheet midpoint integral | −0.020418042 |

The isolated mutual-quadrature error is **69.21%** of the native discrepancy
in magnitude. This is a concrete numerical error for the retained coarse
circulation field, not evidence that the native calculation used this mesh.
On the 19-request grid the same error is **+0.101469884**, explaining why its
CDi swings in the opposite direction near wake alignment.

Four direct receiver-line integrations, using 32/64-point Gaussian refinement,
verify the endpoint formula at the actual 18° geometry. Their maximum CDi
difference is 9.11e−18. All 58 mutual integrals also satisfy reciprocity.

## A consistent smooth-wake reconstruction

The [steady description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf)
allows either pointwise circulation, equations 62/153, or a sine series,
equation 63, and defines the wake-force integrals in equations 207–211.
As a separate diagnostic, a full-rank sine series is interpolated through each
saved wing's circulation samples. This changes the distribution **between**
pointwise samples, so it must not be presented as the identical discrete model.
There is no truncation, smoothing parameter or fit to reference outputs.

For a straight wing, the continuous source integral has an analytic complex
Chebyshev form. The remaining target integral is evaluated with piecewise
Gaussian quadrature, refined from 32/64 to 128 points where required.
Self energy uses Fourier orthogonality, and mutual energy uses the same smooth
circulation. This treatment preserves opposite-wake cancellation.

| Requested intervals per wing | Current comparison | Smooth-wake comparison | Gains / losses |
|---:|---:|---:|---:|
| 19 | 195/203 | 197/203 | 3 / 1 |
| 20 | 199/203 | 197/203 | 1 / 3 |

Only CDi and efficiency are replaced in that diagnostic; the five force and
moment comparisons are retained. Using the original discrete circulation lift
instead of the continuous impulse produces the same pass counts.

For 20 intervals at 18°, smooth-wake CDi is **0.257545239**, an error of
**−3.1246%** instead of −11.0964%. Efficiency error becomes **+2.5294%**
instead of +11.4935%. The large localized error is therefore substantially
reduced. However, the complete comparison still fails CDi at 18°, 19°, 20°,
21°, 23° and 24°, with errors **3.12–3.97% low**. Both grids give 197/203;
the 19-request grid's six CDi errors range from 3.19% to 4.49% low.

This does not justify promoting the reconstruction or changing accepted
counts. Native node positions, circulation representation, stall strength and
the native wake-output algorithm remain unauthenticated.

## Why an isolated cross-term replacement is also unsafe

Literal piecewise-constant thin wake sheets have singular self energy.
Replacing only the mutual term by its exact integral while keeping the finite
midpoint self term would mix inconsistent approximations. A control with two
opposite single-strip wakes separated by 0.001 half-spans gives a negative
hybrid CDi of **−3.565645**, which cannot represent total wake energy.

The endpoint integral above is therefore used to measure the mutual quadrature
defect, not as a production correction. A future improvement must treat self
and mutual contributions consistently for its declared circulation representation
and retain cancellation and nonnegative energy.

## Independent verification

Four source velocities at the near-alignment geometry agree with direct
60-digit real Biot–Savart integration within 3.50e−12 in velocity units. This
checks the analytic source kernel independently of its complex formula.
An existing double-integral implementation agrees on a separated multi-mode
control, and exact coincident opposite wakes cancel.

All 20 discrete self-energy modes satisfy the independent uniform-theta
quadratic: relative to continuous modal energy, the factor is
`sinc(n delta) sinc(delta)`, with `delta = pi/(2N)` and an additional factor
of two for the highest sampled mode. Here `sinc(x) = sin(x)/x`. The maximum
matrix error is 1.35e−14. All 29 uniform N20 states also satisfy the exact
discrete/continuous impulse identity.

Across the 58 reconstructions, maximum sample interpolation error is 8.21e−16,
maximum CDi quadrature refinement difference is 3.29e−14, and maximum mutual
reciprocity error is 5.60e−16. All 1,218 scalar decisions are independently
re-scored against original native tokens at the unchanged tolerances.

An initial 32/64 quadrature check failed its refinement gate; the retained
rerun extends quadrature while preserving that gate. A scalar-extraction error
in the separate mutual audit was also corrected. Initial scripts/logs are
retained; no aircraft solve was repeated. All processes have terminal results.

Production and all 42 registered ISAE table rows are unchanged. SA-7 remains
**395/812** registered, including **395/406** for the full aircraft; the earlier
strength-20 result remains separately qualified at **404/406**. The full
project remains incomplete.

[Declared reconstruction](../../artifacts/isae/sa7-near-coplanar-wake-20261101/plan.json),
[58-state results](../../artifacts/isae/sa7-near-coplanar-wake-20261101/analysis.json),
[exact mutual integrals](../../artifacts/isae/sa7-near-coplanar-wake-20261101/mutual-integral.json),
[independent verification](../../artifacts/isae/sa7-near-coplanar-wake-20261101/verification.json),
[receipt](../../artifacts/isae/sa7-near-coplanar-wake-20261101/receipt.json).
