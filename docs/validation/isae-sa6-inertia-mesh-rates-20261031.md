# SA-6: inertia-compatible meshes do not recover pitch-rate response

2026-10-31. All 14 candidates that retain the required control-break nodes
fail the same four pitch-rate outputs at the predeclared 15%-chord, F1=4°
operating point. Every candidate passes all six static outputs. Within the
tested grid family and fixed physical settings, changing the mesh alone
cannot resolve the SA-6 discrepancy. No production defaults or registered
comparison counts change.

## Candidate scope

The [native tensor follow-up](isae-sa6-source-inertia-20261031.md) retained
22 grids from the earlier uniform/cosine/modified-cosine search with requested
counts 4–128. Their spanwise second moments lie within the absolute printed
inertia constraint. Eight have no control-break anchors; they omit the
literal discontinuities at `y=±0.333×0.762 m` and are explicitly excluded.
The remaining 14 retain the control breaks and center, with or without the
two zero-weight stations at `y=±0.6096 m`:

| Spacing | Control-break anchors | Also zero-weight stations |
|---|---|---|
| Uniform | 33, 34 requested intervals | 33, 34 |
| Cosine | 42, 43, 44 | 42, 43, 44 |
| Modified cosine | 38, 39 | 37, 38 |

Inserted anchors increase the actual interval counts. Explicit node arrays
are retained and checked after production meshing. Arithmetic midpoints
are used only to test the native apparent-inertia constraint. Aerodynamic
sampling retains the published Glauert-angle midpoints; it is not replaced
by the inertia quadrature.

The model, native target and settings are fixed before running: the first
15%-chord native export, speed 20 m/s, incidence 12°, F1=4°, frozen influences,
stall strength 20, width 0.05 and pointwise circulation. The strength/frozen
setup remains a qualified hypothesis, not authenticated historical input.
One counterexample is sufficient to reject a grid as a complete remedy;
only a grid passing all six statics and all six q outputs would justify
extending this comparison to the other models and controls. None does.

## Results

| Pitch-rate output | Native ASWING | Candidate range | Matches / 14 | Median / maximum error |
|---|---:|---:|---:|---:|
| CXq | −0.00969 | −0.0327261 to −0.0303433 | 0/14 | 219.43% / 237.73% |
| CYq | 0 | 0 | 14/14 | Zero |
| CLq | 1.99878 | 2.0872951 to 2.1121598 | 0/14 | 4.95% / 5.67% |
| Clq | −0.09364 | −0.0954622 to −0.0880309 | 10/14 | See individual checks |
| Cmq | −0.46228 | −0.4915842 to −0.4843465 | 0/14 | 5.34% / 6.34% |
| Cnq | −0.00067 | −0.00195973 to −0.00102381 | 0/14 | 170.36% / 192.50% |

The four nonzero outputs with no matches fail on every candidate, so their
median/max errors describe failed checks only. CLq remains **4.43–5.67% high**;
the closest candidate is still outside the unchanged 3% gate.

Across the repeated comparisons, statics pass **84/84**, state derivatives
**410/504**, and their q subset **24/84**. These are 14 evaluations against
the same 42 native targets, not new independent targets or additions to
the registered ISAE denominator. The full qualified SA-6 state result remains
**2,780/3,168**; its earlier four-model mesh pilot remains separately qualified.

## Verification and execution

All 14 cold bases and analytic responses finish in one native process,
with one BLAS thread. Numerical work takes 2.625 seconds after imports.
No browser, Vite server or parallel worker is launched.

An independent straight-wing calculation reconstructs all 14 influence
fields, circulation residuals, Jacobians, force/moment integrals and state
responses without importing OpenSwing. Maximum differences:

- Force/moment derivative coefficients: `5.30e-15`.
- Static coefficients: `2.23e-16`.
- Circulation responses: `1.64e-13`.
- Field velocities divided by freestream speed: `1.55e-13`.
- Complete circulation residual: `1.86e-13`; linear residual: `2.98e-13`.

All 588 repeated scalar decisions are checked against the original native
tokens with rational arithmetic. Independent node generation and second-moment
integration verify the exact candidate grids. A first verification attempt
stopped because the older static-reference decoder lacks decimal metadata;
the verifier now derives precision from the original tokens for both scopes.
That partial attempt is retained. No physical solve was repeated.

Evidence: [predeclared plan](../../artifacts/isae/sa6-inertia-mesh-rates-20261031/plan.json),
[complete analysis](../../artifacts/isae/sa6-inertia-mesh-rates-20261031/analysis.json),
[verification receipt](../../artifacts/isae/sa6-inertia-mesh-rates-20261031/receipt.json).

This excludes the tested finite family as a standalone correction under the
recorded settings. It does not exclude all possible meshes, other circulation
representations, or undocumented historical settings. The broader ASWING
implementation and the SA-6–SA-10 comparisons remain unfinished.
