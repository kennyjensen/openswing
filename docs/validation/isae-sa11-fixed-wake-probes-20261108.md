# SA-11 fixed wake probes: localized changes survive a fixed receiver

2026-11-08 UTC. Comparing the two retained grids at identical physical probes
shows that the remaining winglet problem is **not solely a moving-tip maximum**.
Many probes away from their own wake plane change little, but localized root
interactions remain sensitive. The current-wind lower-winglet circulation
integral also changes by **14.87%** between N48 and N96.

No new circulation solves, source changes, finite cores or production changes
are made. This is a comparison between two OpenSwing grids, not an ASWING
reference error or a new validation pass. SA-11 remains **163/4,592 at 5%**.

## A direct comparison at coarse force points is singular

The [previous study](isae-sa11-section-velocity-20261108.md) retained the native
N48/N96 circulation and geometry for the upper and upper/lower models, with
both frozen and current-wind influences. The present audit verifies their
manifests and production hashes before reuse.

On each upper winglet, all **48** coarse force receivers lie within
**1.422e-14 m** of an active refined-grid wake origin. There are **34 exact
coordinate matches on the right and 31 on the left**, for either influence
setting. The nested cosine/Glauert construction puts the old interior receiver
at the new interval boundary. The exact coincidences are filament origins,
where the zero-core field is singular.

Consequently, simply evaluating the fine field at the old force points is not
a valid convergence test. No velocities are evaluated at those coincident
probes here. The roundoff band only labels close locations; it does not snap
geometry, remove a source or impose a vortex core.

## Fixed off-sheet probes and an unchanged-source control

Each winglet has seven fixed root-to-tip fractions:
`0, 0.01, 0.1, 0.5, 0.9, 0.99, 1`. At each fraction, probes lie on both sides
of its wake plane, at **0.1%, 1% and 10% of local chord**. The plane normal is
the normalized cross product of influence-wind direction and section span.
The straight quarter-chord trace and local chord define the locations once;
the identical coordinates are used for both grids.

There are **504 common physical probes** over the four model/influence pairs.
These offsets move measurement locations only. They do not alter the source
geometry, the aircraft, the circulation on either saved grid, or any core size.
Every sampled probe has nonzero distance from the retained active wake rays.

A separate representation check splits every coarse bound segment in half
while giving both children the original circulation. The inserted internal
wake strengths cancel exactly. The resulting bound and wake fields match the
unsplit source field within **2.12e-9 m/s** across all probes. Thus merely adding
equivalent source segments does not cause the observed field changes.

## Wake changes at the same positions

The metric below is `100*|W96-W48|/30 m/s`. It is a velocity difference normalized
by flight speed, **not** relative error against ASWING and **not** a percentage
of the local wake velocity. Bound and total fields are also retained; reporting
the wake separately avoids confusing the large near-bound-line self-field with
the wake mechanism under investigation.

Each cell gives **maximum / median** change among the corresponding fixed probes.

| Model and influence setting | Offset 0.1% chord | Offset 1% chord | Offset 10% chord |
|---|---:|---:|---:|
| Upper, frozen | 139.99% / 25.33% | 17.17% / 4.72% | 1.011% / 0.028% |
| Upper, current wind | 136.96% / 42.33% | 15.74% / 4.01% | 69.32% / 0.252% |
| Upper/lower, frozen | 659.70% / 33.54% | 278.83% / 4.00% | 9.987% / 0.079% |
| Upper/lower, current wind | 278.34% / 24.93% | 39.27% / 4.31% | 29.15% / 0.709% |

![Wake differences at identical physical probes](../../artifacts/isae/sa11-fixed-wake-probes-20261108-review-final/fixed-wake-probes.png)

Moving farther from a winglet's own wake plane does not guarantee moving away
from every other wake. The current-wind 10%-chord maxima occur near the upper
root and remain close to a **main-wing** wake ray. This explains why the largest
change can increase while the median decreases.

For the upper-only current-wind pair, the worst 10%-chord probe is 1% of the
way along the right upper winglet. It remains **1.446 mm** from the same
main-wing ray origin/axis geometry on both grids. That grouped ray's circulation
strength changes from **0.342126 to 0.169195 m²/s**. Its vector contribution to
the field change has magnitude **19.03 m/s**; the complete wake change is
**20.80 m/s**. All other ray contributions, including their cancellations,
remain in the decomposition. These are fixed-position changes in the discrete
wake representation, not movement of the observation point.

For the corresponding upper/lower pair, the same main-wing ray's strength
changes from **0.170092 to 0.099552 m²/s**. Its contribution changes by
**7.76 m/s**, compared with **8.74 m/s** for the complete wake. Individual
vector magnitudes are not additive fractions of the total.

## The lower-winglet loading also changes

The circulation comparison integrates the two original piecewise-constant
representations over their common physical beam arclength. No circulation
interpolation or curve fit is introduced. Relative L1 difference means
`integral |Gamma96-Gamma48| ds / integral |Gamma96| ds`.

Symmetric branches agree to the recorded precision:

| Model and influences | Upper-winglet relative L1 difference | Lower-winglet relative L1 difference | Lower-winglet circulation integral change, N48→N96 |
|---|---:|---:|---:|
| Upper, frozen | 0.810% | — | — |
| Upper, current wind | 2.200% | — | — |
| Upper/lower, frozen | 0.976% | 2.185% | -0.653% |
| Upper/lower, current wind | 1.304% | **16.885%** | **-14.873%** |

The integral is circulation times arclength, not the full aerodynamic force;
force also depends on local velocity and section orientation. Its substantial
lower-winglet change nevertheless shows that the current-wind discrepancy
extends beyond how the maximum velocity is sampled. Two grids cannot establish
an asymptotic convergence rate or identify the correct continuum loading.

## Evidence and next action

All four small serial field jobs finish. Their recorded calculation stages
total **2.55 seconds**, excluding startup and the separate analysis/plot job.
The wake-source difference reconstruction agrees with direct field subtraction
within **6.04e-14 m/s**. All 143 production/status/scope hashes are unchanged.
The initial figure review is retained separately; the final figure explicitly
states that each grid uses its own saved circulation.

The next control should prescribe one smooth circulation function on a straight
swept line. That can separate near-wake discretization from changes in the
nonlinear solution, before revisiting the lower-root loading and the interacting
main-wing wake. Neither the present fixed probes nor the earlier moving maxima
justify an arbitrary core or a production force-law substitution.

- [One-pair serial driver](../../scripts/verify-sa11-fixed-wake-probes.py)
- [Independent saved-array and source audit](../../scripts/analyze-sa11-fixed-wake-probes.py)
- [Analysis, all probes, circulation metrics and source decomposition](../../artifacts/isae/sa11-fixed-wake-probes-20261108-review-final/analysis.json)
- [Standalone SVG plot](../../artifacts/isae/sa11-fixed-wake-probes-20261108-review-final/fixed-wake-probes.svg)

The four `artifacts/isae/sa11-fixed-wake-probes-20261108-{upper,both}-{frozen,current}/`
directories retain the plans, exact drivers, complete field arrays, results and
verification manifests. No completion fraction or progress observation changes.

The subsequent [prescribed swept-wake control](swept-wake-limit-20261108.md)
holds a smooth circulation function and receiver fixed on a straight swept
line. It confirms an analytically predicted logarithmic wake term without a
nonlinear solve. Finite chordwise attached legs remove this term in the ideal
control, but do not yet supply the force and junction treatment for SA-11.
