# ST-4 circulation and spacing diagnostic

Changing node spacing explains much of the large lowest-mode discrepancy in
the earlier uniform-grid pilot. At 64 intervals the lowest oscillation-frequency
error is **66.49% with uniform spacing,
11.37% with cosine spacing, and
4.23% with modified-cosine spacing**.
All physical inputs, modal-search settings and acceptance tolerances are fixed.
No complete native root matches its printed precision; ST-4 remains unvalidated.

The Fourier alternative does not explain the remaining discrepancy: 16 and 32
circulation modes on the same 64-interval cosine mesh give nearly identical
tracked poles, while the lowest-frequency error remains
11.83%. The complete Fourier A/M
matrices agree with an independent projection of the pointwise matrices to
9.94e-16 in the row-scaled comparison.

## What the documents establish

Drela's [steady technical description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
Eqs. 62–63, explicitly permits both pointwise and sine-series circulation.
Eqs. 150–154 sample circulation and physical geometry at material Glauert-angle
midpoints. Eq. 201 applies sine-weighted flow-tangency residuals. The current
implementation follows this structure; its common 2/pi row factor does not
change the homogeneous constraints. The
[unsteady extension](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf),
Eq. 28, retains both representations. Eqs. 48–49 add the local circulation-rate
downwash with b=2/pi; the existing local residual uses this term.

The same-surface vortex influence has no finite core, consistent with the
distinction between steady Eqs. 160 and 161. The input manual's omitted airfoil
defaults Cdf=Cdp=alpha=Cm=0 and dCLda=2*pi agree with the parser. No new mismatch
in these audited definitions was found. This is a targeted code/document audit,
not an independent validation of every aerodynamic term.

The extended manual shows an example with 180 nodes and 19 circulation modes;
it does not authenticate the ST-4 settings. Modified-cosine is the existing
option checked against [SA-2 coordinates](isae-sa1-sa5-spacing-20261029.md).
That evidence makes it a useful numerical hypothesis, not proof of ST-4's
historical mesh. The application defaults and physical equations are unchanged.

## Saved-reference comparisons

All cases retain the original `Weight7a/7a_b17.asw`, first scripted speed 120,
density 1.0771417304, zero incidence/sideslip, Earth gravity 9.81 toward −z,
PG Mach zero, aerodynamic lag, fixed perturbation frame and 16 roots near
0+300i. Startup/pose/mesh assumptions remain those of the
[original pilot](isae-st4-zero-area-airflow-20261103.md).

Names give the requested interval count; the required point-weight station adds
one interval. The two uniform cases are reused from the preceding study. The
other six are serial public-API solves, all with completed numerical outputs.
The final 32-interval modified-cosine worker handle was no longer available when
polled after the interruption; its exit code is unavailable. Its completed result
and equation checks are verified independently.

| Case | Circulation unknowns | Seconds | Lowest imaginary pole (/s), native 5.8769355 | Lowest-frequency error | Other four frequency errors | Six real-component errors |
|---|---:|---:|---:|---:|---|---|
| uniform32 | pointwise | 29.54 | 11.5315307 | 96.217% | 0.080–0.892% | 0.261–7.925% |
| uniform64 | pointwise | 55.44 | 9.7847527 | 66.494% | 0.006–0.507% | 0.155–6.774% |
| cosine32 | pointwise | 29.48 | 5.2452135 | 10.749% | 0.032–0.523% | 0.320–1.694% |
| cosine64 | pointwise | 51.00 | 5.2086592 | 11.371% | 0.008–0.173% | 0.176–0.663% |
| cosine64_k16 | 16 | 120.16 | 5.1817374 | 11.829% | 0.010–0.173% | 0.228–0.701% |
| cosine64_k32 | 32 | 116.57 | 5.1814693 | 11.834% | 0.010–0.173% | 0.229–0.688% |
| modified32 | pointwise | 26.56 | 6.0353031 | 2.695% | 0.042–0.271% | 0.005–1.048% |
| modified64 | pointwise | 47.35 | 5.6285402 | 4.227% | 0.021–0.234% | 0.114–0.415% |

Each case gives **1/12 strict scalar matches**, solely the near-zero imaginary
component of the real root. No physical parameter was selected from these errors.
Closer agreement on a particular mesh is not evidence that it is the historical
mesh or a converged physical answer.

## Resolution and mode identity

| Comparison | Components within unchanged mesh-change gate | Lowest imaginary-component change |
|---|---:|---:|
| cosine32 → cosine64 | 5/12 | 0.7018% |
| cosine64_k16 → cosine64_k32 | 12/12 | 0.0052% |
| cosine64_k32 → cosine64 | 11/12 | 0.5220% |
| modified32 → modified64 | 3/12 | 7.2268% |

The gate is 0.1% relative to the finer nonzero component; the reference-zero
component retains its original absolute printed-precision rule. Spacing-only
differences are recorded separately in the assessment and are not convergence
checks. Cross-grid injective root matching is supported by displacement/rotation
shape comparisons. Native mode identity is still based on proximity because the
archive supplies no corresponding eigenvectors. All 16 returned roots and both
vectors are retained, including negative-frequency and real roots.

The Fourier-count refinement passes all 12 tracked component checks, but the
32-mode result differs from the pointwise result by more than 0.1% in the lowest
imaginary component. Its unprojected local flow-equation defects are
0.092–0.696% in the diagnostic weighted norm. These are retained rather than
treated as zero; projected eigenpair convergence alone does not establish local
flow accuracy or complete circulation convergence.

## Independent equation checks and execution

For each Fourier case, reconstructing sine sampling T and residual projection P
from the stored material angles gives `A_F = P A_pointwise T` and
`M_F = P M_pointwise T`. Maximum row-scaled differences are below
9.94e-16. This verifies the implemented projection at this operating
point, including its structural and kinematic couplings; the underlying pointwise
physical model still requires its own validation. The local-defect denominator
uses the weighted norm of the sum of magnitudes of circulation-state,
other-state and rate terms. It is a diagnostic, not a new acceptance threshold.

All **192/192 new left/right eigenvector residual checks** pass against the
saved full matrices, maximum infinity-norm backward error 1.11e-15
(limit 1e-8). Another 64 checks reverify the two retained uniform cases.
The saved-only assessment initially exceeded its memory cap by retaining every
mode's full output graph across cases. Retaining only the nodal shapes needed
for comparisons fixes that verifier memory use. No physical solve was repeated.

Each numerical child uses one BLAS thread, a 180-second timeout and a 512 MiB
address-space cap. The Fourier cases take approximately two minutes despite
their smaller pencils; this separate performance issue remains. The evidence
here is native CPython; no new browser replay or application build is claimed.
All 136 production kernels are unchanged from the prior delivered build.

The next work is further spatial convergence and historical numerical-setting
review. The remaining difference cannot be attributed to Fourier projection
algebra, and the current evidence does not justify changing physical parameters.
Registered ST-4 family counts and all broad partial requirements remain unchanged.

Evidence: [source audit](../../artifacts/isae/st4-airflow-discretization-20261103/source-audit.json),
[assessment](../../artifacts/isae/st4-airflow-discretization-20261103/assessment.json),
[independent projection](../../artifacts/isae/st4-airflow-discretization-20261103/projection.json),
and [retained earlier refinement](isae-st4-airflow-refinement-20261103.md).
