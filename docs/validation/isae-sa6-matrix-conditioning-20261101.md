# SA-6: conditioning of the saved derivative systems

The remaining SA-6 pitch-rate differences are not explained by numerical error
in solving the retained linear systems. Replaying all 88 saved state matrices
with single-precision LAPACK changes no comparison decisions: **2,780/3,168**
state derivatives and **282/528** pitch-rate derivatives pass in both precisions.
This is the previously qualified frozen-influence, strength-20 scope; it is
not an authenticated native setting or a new registered result.

| Quantity | Result |
|---|---:|
| Saved states / paired native exports | 88 / 44 |
| Matrix dimensions, including required break nodes | 66–130 |
| Unscaled infinity-norm condition numbers | 378.6–2,195.9 |
| Largest normalized backward error of saved response | 9.18e−17 |
| Largest output-error bound from the saved linear residual | 2.53e−13 |
| Largest coefficient change in the float32 replay | 1.631e−6 |
| Largest float32 change divided by its acceptance tolerance | 0.008468 |
| Gains / losses under the existing comparison policy | 0 / 0 |

The retained system is `A X = -P`, with output
`C = T (D + H X)`. The audit uses the original captured Jacobian, forcing,
direct wrench, circulation-to-wrench map and coefficient transformation.
Double-precision residuals are accumulated separately with scalar `fsum`.
The output-error estimate propagates those residuals through an inverse-norm
bound and the absolute output map. The inverse residual is also checked.
These are floating-point norm estimates, not interval-arithmetic certificates.

The precision experiment explicitly calls LAPACK `SGESV` on float32 matrices
and forcing, then uses float32 wrench and coefficient maps. It holds the
nonlinear equilibrium and assembled model fixed. A separate input-rounding
bound, allowing one float32 unit roundoff in each matrix/forcing entry, is at
most 2.277% of the existing discrepancy for any failed pitch-rate scalar.
That bound concerns input rounding only; the measured replay also includes
factorization and output arithmetic.

An independent verifier imports no numerical solver or NumPy. It reconstructs
both saved and float32 solution residuals with scalar arithmetic, reconstructs
the double-precision outputs, bounds the float32 output accumulation error,
and reads all 44 native files directly. All 6,336 acceptance decisions are
recomputed with decimal arithmetic. Maximum double-output reconstruction error
is 1.33e−15; the float32 output errors are within their accumulation bounds.
All 42 registered status-table rows are unchanged.

The numerical replay takes 1.66 seconds after input verification and imports,
in one process with one BLAS thread. There are no new aircraft solves, field
evaluations, browser launches, builds, or changes to production equations.

This does **not** establish the precision of the native executable, validate
the assembled derivative equations against ASWING, or bound errors in native
geometry, equilibrium, or derivative assembly. It excludes improving the
accuracy of the saved linear solve as a remedy. Failed fine-mesh pitch-rate
errors remain typically 20.81% for CXq, 18.84% for Cnq, 3.84% for CLq and 3.96%
for Cmq. The next investigation should concern the rate/stall linearization
or authenticated native conventions, not a higher-precision linear solver.

Evidence: [plan](../../artifacts/isae/sa6-matrix-conditioning-20261101/plan.json),
[audit](../../artifacts/isae/sa6-matrix-conditioning-20261101/audit.py),
[results](../../artifacts/isae/sa6-matrix-conditioning-20261101/analysis.json),
[scalar verifier](../../artifacts/isae/sa6-matrix-conditioning-20261101/verify.py),
[verification](../../artifacts/isae/sa6-matrix-conditioning-20261101/verification.json).

The source equations for the implicit response system are the Technical
Description, §8.3, equations (212–213). The
[previous full comparison](isae-sa6-frozen-derivatives-20261031.md) records the
native error distribution and independent nonlinear finite-difference checks.
