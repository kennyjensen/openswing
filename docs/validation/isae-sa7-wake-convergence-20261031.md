# SA-7 low-lift efficiency and wake verification

2026-10-31. The full-aircraft comparison still has a 3.54% high efficiency
at −5°. The preceding strength-20 diagnostic does not change this result.
This follow-up keeps the published approximate strength 40 and all original
section properties, and investigates discretization and induced-flow arithmetic.
No production equation, default setting or registered count changes.

The [mesh study](../../artifacts/isae/sa7-efficiency-wake-20261031/report.md)
completes all 12 declared states: −5° and 0°, cosine and modified-cosine
spacing, and 64/128/256 intervals per beam. Ten are new calls and two reuse
identical pinned captures. Every state converges and passes the independent
force/moment sum.

| Spacing | Intervals per beam | Efficiency at −5° | Error relative to ASWING |
|---|---:|---:|---:|
| Cosine | 64 | 0.38243122 | +3.5397% |
| Cosine | 128 | 0.38243211 | +3.5400% |
| Cosine | 256 | 0.38243233 | +3.5400% |
| Modified cosine | 64 | 0.37790261 | +2.3136% |
| Modified cosine | 128 | 0.38017515 | +2.9289% |
| Modified cosine | 256 | 0.38130575 | +3.2350% |

The archived efficiency is 0.369357. Modified spacing passes at the two
coarser meshes but loses that pass at 256 intervals. It therefore does not
provide a refinement-stable correction. All six zero-incidence efficiency
values are within 0.066% of the reference.

## Later check: total lift does not resolve the efficiency convention

2026-11-01. The [saved-state convention audit](../../artifacts/isae/sa7-efficiency-convention-20261101/analysis.json)
checks both remaining strength-20 cases. Substituting total CL/CY into the
efficiency numerator, while retaining the same Trefftz CDi, worsens the errors
from **3.5397%/3.5400%** to **3.6162%/3.6164%**. Both checks still fail; the
qualified full-aircraft count stays 404/406. No output change is adopted.

Conditional on zero native Trefftz side force for the symmetric literal model,
the printed CDi and efficiency imply native CLi = −0.0423556700. Their printed
precision gives the interval [−0.0423557398, −0.0423556003]. Current CLi is
−0.0426078351, **0.59535% high in magnitude**; current CDi is
**2.2653–2.2655% low**. Squared lift divided by induced drag combines these
small differences into the 3.54% efficiency error. Neither component has to
fail its own 3% gate for their ratio to fail.

The inferred native total-minus-Trefftz lift difference is −1.5630e−5;
the current difference is approximately −1.573e−5. This supports retaining
the distinction between total and wake lift. The inference is not a recovered
native circulation distribution or authenticated producing setup. Only two
saved states are read; no new solve or broader parameter search runs.
The [receipt](../../artifacts/isae/sa7-efficiency-convention-20261101/receipt.json)
records the original tokens, source checks and unchanged acceptance.

## Independent wake calculation

The separate reader reconstructs continuous circulation as a sine series.
Each wing's self-induced drag follows Fourier orthogonality exactly;
cross-wing drag integrates continuous shed vorticity using Gaussian quadrature.
Refinement and mutual-drag reciprocity checks pass, as do elliptic-wing,
coincident addition/cancellation and separated-wing controls.

For cosine spacing at −5°, the continuous-wake efficiencies are 0.38243002,
0.38243181 and 0.38243226 at 64/128/256 intervals, respectively. These agree
closely with the discrete output and preserve the mismatch. Modified-mesh
continuous estimates approach the same result. Fit errors are recorded;
ill-conditioned full interpolations at 128/256 modified intervals are
explicitly unavailable, and truncated reconstructions are only diagnostics.

The two wings have opposite lift at −5°. At 128 cosine intervals, their
self-drag coefficients are +0.000152249 and +0.000341112; the mutual terms
are approximately −0.000120761 each. This cancellation makes efficiency
sensitive to the relative circulation and wake geometry. It does not by
itself identify a defect or the native producing settings.

The [independent field verifier](../../artifacts/isae/sa7-efficiency-wake-20261031/field-verification.json)
also numerically integrates the regularized Biot–Savart expression in steady
equation (161), including every source vortex. It checks force and control
points at ten selected locations in each of the twelve states: **240 vector
samples**. Maximum velocity discrepancy normalized by flight speed is
1.07e−13; quadrature refinement changes it by at most 2.14e−15. The source
core is applied only between distinct physical surfaces, with the documented
chord and interval floor. The force-point self-bound segment is excluded.

These calculations independently verify wake reporting and selected induced
velocities for the retained geometry and circulation. They do not independently
solve circulation or recover ASWING's original mesh and settings. The current
evidence does not justify combining the coarse modified mesh with strength 20
to claim complete SA-7 validation. The registered full-aircraft result remains
**395/406**, with the separate strength-20 result **404/406**.
