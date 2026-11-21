# Daedalus: wing-lift terms behind yaw sensitivity

The large wing-lift sensitivity near the yaw dip comes mainly from **relative
airflow changes caused by wing motion**, particularly rotation at the wing
root relative to the aircraft frame. Changing induced flow is a much smaller
part of this particular derivative. This identifies a coupling to investigate;
it does not establish an incorrect force law or justify changing stiffness.
The predicted Bode response is unchanged: **0.074218 versus 0.033986 deg/s/F3**
at 1.157378 Hz.

![Wing lift and velocity sensitivity decomposition](../../artifacts/daedalus-wing-lift-terms-20261113/report-v2/wing-lift-terms.png)

## Exact accounting of the accepted response

The [earlier load-sensitivity study](daedalus-load-sensitivity-20261113.md)
found ordinary wing lift to be a stronger local influence than fin lift, wing
profile drag or stall. This study differentiates the published vector lift law
at that same equilibrium and response:

`F = rho * Gamma * (V × s) * length`

Drela's [unsteady description](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf),
printed p. 8, Eq. 34, supplies the force law; Eqs. 30–31 supply the relative
velocity. The differentiated terms separately change circulation, relative
air velocity, span direction, and strip length. A fifth term accounts for
changing application/transfer arms, including `delta(r) × F_base` in the
global moment. All five sum to the previously measured wing-lift derivative.

Two fourth-order stencil widths, 0.001 and 0.0005, capture primitive field
derivatives from the complete nonlinear residual. The bound circulation and
aircraft motion are the supplied full coupled solution; no new trim or
circulation solve is substituted. The full 2,044-coordinate descriptor maps
each resulting load derivative to an output sensitivity. This includes all
existing aircraft feedback.

The entries below are **percent yaw-magnitude change for a +1% multiplier of
one differential contribution**, locally at the unchanged equilibrium. They
are not independently adjustable physical parameters, new Bode predictions,
or permission to extrapolate to large changes.

| Wing ordinary-lift term | 0.2 Hz | 1.157378 Hz |
| --- | ---: | ---: |
| Circulation change | +0.33954 | −0.05422 |
| Relative air-velocity change | −1.14089 | +1.28409 |
| Span-direction change | +0.00262 | −0.00108 |
| Strip-length change | approximately 0 | approximately 0 |
| Load-position/transfer change | −0.01927 | −0.05209 |
| Sum: complete ordinary wing lift | −0.81800 | +1.17670 |

## Which velocity and which wing motion?

At the stationary base, bound-point relative air velocity separates into
aircraft-frame motion, local elastic motion and induced flow. The last term
retains circulation changes, changing vortex geometry, body flow and propeller
flow together; no independent attribution inside that remainder is implied.

| Air-velocity contribution | 0.2 Hz | 1.157378 Hz |
| --- | ---: | ---: |
| Aircraft-frame motion | −1.18446 | +0.26587 |
| Wing elastic motion | +0.02045 | +1.02575 |
| Induced flow | +0.02311 | −0.00753 |
| Sum: relative air velocity | −1.14089 | +1.28409 |

The elastic velocity is further partitioned into rigid translation/rotation
transported from **beam 1, t=0**, and deformation relative to that root. This
is the local wing-root motion relative to the existing flight frame, not a
change in the aircraft-frame definition or a released joint.

| Wing elastic-velocity contribution | 0.2 Hz | 1.157378 Hz |
| --- | ---: | ---: |
| Root translation | +0.00006 | +0.01500 |
| Root rotation | −0.01645 | +1.39084 |
| Deformation relative to root | +0.03684 | −0.38010 |
| Sum: wing elastic motion | +0.02045 | +1.02575 |

At the dip, the corresponding root-rotation and relative-deformation
contributions to body-z moment are **6.41064 + 2.75658i** and
**−5.84975 − 0.36101i lb ft/F3**. Their cancellation is hidden by a single
total wing moment. These are only the velocity-dependent part of ordinary
circulation lift; geometry/circulation/rate-lift/apparent-load feedback remain
outside this last partition.

This makes the **wing-root/fairing/forward-boom rotational response and its
aerodynamic coupling** a concrete next check. The paper's roll-pin diagnostic
already [worsened the Bode mismatch](daedalus-wing-paper-20261113.md); this new
accounting is not evidence to adopt that hinge or tune the fairing stiffness.
The [fin apparent-load replay](daedalus-fin-phase-20261113.md) found no omitted
frame-acceleration term. Both findings are diagnostic progress, not a native
ASWING pass or proof that the historical operating settings are correct.

## Numerical evidence

| Check | Maximum absolute error |
| --- | ---: |
| Product-rule sum versus full wing-lift residual derivative | 2.138e−14 |
| Global wrench sum versus full derivative | 2.754e−9 in respective native units |
| Full wing-load derivative versus previous saved result | 0 |
| Sum of output sensitivities versus previous saved result | 2.390e−11 |
| Velocity/elastic partition residual closure | 5.343e−20 |
| Velocity/elastic partition output-sensitivity closure | 7.958e−16 |

Unchanged gates are 2e−8 for the primary scaled residual and output replay,
2e−6 for wrench/primitive derivative checks, 2e−12 for the velocity partition
and 2e−10 for its output sum. All six numerical jobs and both presentation jobs
completed successfully under the one-thread, 512 MiB, 15 CPU-second,
25 wall-second limits. Maximum numerical CPU time was 3.100 seconds; maximum
wall time was 12.533 seconds. All workers and tool sessions were reaped.

The [bounded driver](../../scripts/check_daedalus_wing_lift_terms.py) retains
job-specific source snapshots, hashes, terminal receipts and complex arrays.
The [combined result](../../artifacts/daedalus-wing-lift-terms-20261113/report-v2/result.json)
and [CSV](../../artifacts/daedalus-wing-lift-terms-20261113/report-v2/terms.csv)
contain both frequencies and every decomposition. The first report is retained;
the second adds the completed root/deformation partition. No production
equation/default, ISAE completion fraction or browser/build verification changed.

**Follow-up:** the [mounting-path reconstruction](daedalus-wing-mount-20261113.md)
now traces that root rotation through the fairing and forward boom. The short
boom section supplies most of it and is driven predominantly by the wing
reaction. Literal-stiffness/moment checks and joint/load closure find no
correction. The reaction contains large opposing aerodynamic, real-inertial
and brace contributions; the wing inertial reaction is the next focused check.
