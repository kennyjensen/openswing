# Daedalus: historical plume note and receiver-specific response

The documented September 2008 plume correction is relevant to the provenance
of Drela's June 2008 Bode drawing, but a simple missing-plume interpretation
does not produce agreement in the diagnostic below. Keeping plume flow on the
wing while suppressing it on the other beams lowers yaw at 1.157378 Hz by
**6.29%**, to **0.069550 deg/s/F3**. The drawing gives **0.033986**. Roll and
bank move farther from their reference values. Production physics and the
accepted aircraft remain unchanged.

## What the version history establishes

The freshly fetched [official release notes](https://web.mit.edu/drela/Public/web/aswing/version_notes.txt)
are byte-identical to the retained notes. The
[visible copy and HTTP receipt](../../reference/daedalus-plume-receivers-20261114/receipt.json)
record the source, time and checksum. Relevant distinctions are:

| Release | Documented change | Relevance to the current comparison |
| --- | --- | --- |
| 5.78, April 2008 | Conjugate modes restored to ROM Bode sums | Predates the drawing; current comparison uses the full descriptor |
| 5.80, July 2008 | ROM acceleration, Earth-position and heading recovery corrected | These are not the four frame rate/angle outputs being compared |
| 5.82, September 2008 | Engine mount-rate effects added for propeller forces and moments | Literal Daedalus uses proportional engine type 0; the newer type-2 terms are inactive |
| 5.83, September 2008 | Plume reception corrected beyond the first beam | Potentially relevant; the notes do not describe the defective algorithm |
| 5.84–5.85, October–December 2008 | Apparent-inertia printouts and stability-derivative reporting corrected | Notes distinguish these outputs from simulation calculations |
| 5.97–5.99, 2012–2014 | Concentrated inertia inputs introduced and corrected | Literal Daedalus point intrinsic inertias and spins are zero |

The [animation provenance review](daedalus-animation-20261113.md) retains the
different PDF and GIF publication dates. The [1999 lag-law source review](daedalus-historical-lag-sources-20261113.json)
already found the current circulation-rate coefficients in an earlier primary
paper. None of this identifies the original Bode run's executable, saved
settings or exact plume defect.

## Controlled diagnostic and results

The independent source-equation aerodynamic evaluator removes jet velocity
at selected receivers. Engine inlet evaluation and type-0 thrust remain
unchanged. Each beam's force, moment and circulation residual are selected
together, including their changing load-transfer arms. Point-drag receivers
are tracked separately. The final diagnostic suppresses plume reception on
beams 2–5, retains it on beam 1, and leaves point-drag plume active.

This is an **affine, fixed-equilibrium linearization**, not a retrimmed
aircraft. Removing plume changes the steady loads and circulation residual;
an explicitly subtracted constant residual holds the accepted equilibrium.
The all-receiver removal has a maximum static circulation defect of 0.009441
and changes vertical aerodynamic force by −2.060 lb. Those changes are not
silently treated as another physical trim.

All values below are at **1.157377737 Hz**. Rates are deg/s/F3; angles are
deg/F3. Errors use the digitized central curves, without converting graphic
uncertainty into new acceptance counts.

| Output | Current | Conditional non-wing plume removal | Drawing | Conditional error |
| --- | ---: | ---: | ---: | ---: |
| Frame yaw rate | 0.074218 | 0.069550 | 0.033986 | +104.64% |
| Frame roll rate | 0.024219 | 0.022659 | 0.036853 | −38.51% |
| Sideslip | 0.030316 | 0.028493 | 0.025178 | +13.17% |
| Bank | 0.003092 | 0.002893 | 0.005074 | −42.99% |

The separate receiver screen applies only one correction, before feedback is
converged. Its yaw changes are dominated by the fin: −0.004762 deg/s/F3,
versus no more than 0.000062 for any other individual beam. The aggregate
first correction gives 0.069492. Iterating the complete descriptor settles
at 0.069550; these first-correction values must not be called full responses.

The previously completed, separately retrimmed **all-plume-off** case gives
0.071443 at the same frequency; see the
[operator-option comparison](daedalus-operator-options-20261113.md).
That physical case and this fixed-equilibrium diagnostic have different
scopes. Neither matches the drawing.

## Numerical checks

For the original pencil `P = iωM − A`, the independent evaluator supplies the
selected change in linearized residual, `ΔR(z,u)`, including control forcing.
The iteration solves `P δz = B + ΔR(z,1) − Pz`. No state, aerodynamic feedback,
matrix entry or mode is discarded. The unchanged original-pencil condition
and residual gates apply to each correction solve. They are not a separate
condition estimate for the modified pencil.

After six corrections, the checked state's complete modified-equation
relative residual is **1.503e−11** and the next output correction is below
**1.691e−12**. All 2,044 physical coordinates are retained. Two complex-step
widths change the screen's residual action by at most **4.988e−18**; summing
the individual receiver groups recovers the total within **3.180e−22**.

A separate production-residual check uses 34 evaluations and two stencil
widths. Its all-receiver plume-deletion action agrees with the independent
evaluator within **1.507e−13**; the static residual difference agrees within
**3.123e−17**. The physical-coordinate map was also checked against both
previously captured frequency directions. Only the dip-frequency diagnostic
was iterated here; no local or modified-aircraft Bode sweep was run.

[Driver](../../scripts/check_daedalus_plume_receivers.py),
[report generator](../../scripts/report_daedalus_plume_receivers.py),
[comparison CSV](../../artifacts/daedalus-plume-receivers-20261114/report/comparison.csv),
[report](../../artifacts/daedalus-plume-receivers-20261114/report/result.json),
and [verification receipt](../../artifacts/daedalus-plume-receivers-20261114/verification.json)
retain reproduction inputs, complex states and checks. Nine small serial jobs
finished: seven successes and two retained diagnostic failures. The first
screen needed a complex accumulator. The first production comparison reused
the normal state-keyed aerodynamic cache across a changed temporary field
hook; the corrected diagnostic explicitly invalidates that cache. Neither
failure required a production change. Every child used less than 6.5 CPU
seconds, 9 wall seconds and 142 MiB RSS, within the original limits.

## Remaining work

The absence of plume at selected receivers is only one possible interpretation
of the historical defect. The old implementation and a physically retrimmed
selective-plume case remain unverified. This result supplies no justification
for changing current plume physics or fitting gains to the Bode drawing.

The next concrete numerical issue is the
[remaining roll/bank mesh sensitivity](daedalus-structural-resolution-20261113.md)
near 1.5 Hz: complex changes of 19.44% and 20.30% remain between the two
current-source grids. The small yaw-dip mesh change does not close that issue.
ISAE completion fractions, scopes and progress history are unchanged.
