# Daedalus: sensitivity to the measured construction weights

The measured weight differences do **not** explain the Bode dip under the
uniform-distribution assumptions tested here. At 1.157378 Hz, matching all
component totals gives yaw amplitudes of **0.07154–0.07457 deg/s per F3**,
versus the literal model's **0.07422** and Drela's published **0.03399**.
This is a conditional comparison at the original loaded shape, not a fresh
physical trim or a reconstruction of Drela's undocumented operating point.

![Four response channels at the reference dip](../../artifacts/daedalus-measured-mass-20261114/report/comparison.png)

## Reference and declared inputs

The [authoritative reference index](aswing-authoritative-references.md) and
source catalog were consulted before changing the diagnostic setup. Cruz's
*Weight Analysis of the Daedalus Human Powered Aircraft*, Technical Soaring
14(1), 1990, Table 1 (PDF p. 3 / printed p. 4), supplies measured component
totals. The [source supplement](daedalus-weight-sources-20261114.json) records
the original journal PDF and visual check. The preceding
[property audit](daedalus-paper-properties-20261114.md) distinguishes these
measurements from both Drela's 1989 Figure 7 and the public `dae.asw`.

The baseline is the accepted source-equation/SEGSPL model at **6.7 m/s,
Mach 0.1**, with live influences, circulation lag and propeller plume enabled.
It retains 108 nodes, 103 intervals, 82 circulation states and **2,044 total
states**. These are the previously recorded diagnostic settings, not a claim
about the browser defaults or historical Bode settings.

| Distributed component | Original weight, lb | Target weight, lb | Distribution assumption |
| --- | ---: | ---: | --- |
| Wing, beam 1 | 38.538183 | 41.85 | Existing distribution multiplied by 1.085936 |
| Elevator, beam 2 | 1.1325 | 1.19 | Existing distribution multiplied by 1.050773 |
| Rudder, beam 3 | 1.13625 | 1.37 | Existing distribution multiplied by 1.205721 |
| Body/equipment, excluding pilot and water | 15.495 | 24.09 | Additional 8.595 lb assigned as described below |

The body/equipment baseline comprises beam 4's **3.295 lb**, beam 5's
**4.2 lb**, and **8 lb** of unchanged propulsion/gearbox point weights. The
three full-weight alternatives put the additional 8.595 lb entirely on beam
4, entirely on beam 5, or proportionally across their existing distributed
weights. In each alternative, the wing and both tail surfaces also reach
their measured totals. Empty weight becomes **68.50 lb**, an increase of
12.198067 lb. Pilot and water remain 165 and 12 lb.

These placements are explicit sensitivity choices. They are not measurements
of component centroids, exhaustive uncertainty bounds, or an assertion that
all absent equipment was physically attached to those beams. Section CG
offsets stay fixed; intrinsic section inertias scale with the corresponding
mass, and the finite-interval rotary term follows the changed mass. Point
weights, stiffness, aerodynamic properties, control derivatives and damping
are unchanged. No parameter or location was chosen to minimize Bode error.

## Equations and independent verification

The unsteady technical description's section 6.1, Eqs. 37–40 (PDF p. 9),
requires both gravity and inertial reaction at the section mass centroid.
Point-object terms in Eqs. 46–47 remain unchanged. The diagnostic preserves
the current source endpoint discretization, including its declared steady
Eq. 80 finite-interval rotary correction.

For each of the five beams, an analytic unit mass-increase operator includes:

- Translational and rotational inertia, with centroid offsets and the
  finite-interval rotary term.
- Gravity changes from aircraft attitude and offset rotation.
- Global moment changes from moving nodal force locations.
- The same local/global force transfer and scaling used by the full model.

Each operator is checked against a fourth-order difference of the complete
nonlinear residual with the beam's mass doubled, at two step widths and a
random full-state/rate direction. Maximum absolute error is **6.682e-13**
in scaled residual units; maximum relative error is **5.094e-10**.

The resulting matrices are combined with the unchanged full aerodynamic and
structural matrices. The **24 accepted harmonic solves** comprise a baseline
and seven mass configurations at each of three frequencies. Exact structural
elimination reduces the factorization to 748 variables without deleting any
of the 2,044 equations or using a modal truncation. The minimum estimated
reciprocal condition is **1.842e-8**; maximum scaled solve residual is
**5.680e-18**.

Because changing mass changes the mean gravity load, each diagnostic holds
the original mean state with a **constant residual offset**. This offset has
zero derivative; it does not remove gravity or inertial derivatives. The
combined proportional-body model was additionally replayed through the
complete nonlinear residual, including rudder forcing, at every sampled
frequency and two step widths. The largest harmonic residual is
**2.069e-11**. This verifies the conditional linear response, not the
equilibrium of an independently trimmed modified aircraft.

## Results

Yaw amplitudes below use deg/s per native F3 unit. Reference values come from
the retained digitization, with logarithmic interpolation where needed.

| Frequency, Hz | Literal model | All measured totals: tested placement range | Drela drawing |
| --- | ---: | ---: | ---: |
| 0.1 | 0.121763 | 0.122206–0.122231 | 0.118238 |
| 1.157378 | 0.074218 | 0.071536–0.074570 | 0.033986 |
| 1.5 | 0.094316 | 0.097991–0.104207 | 0.081818 |

At the reference dip, changing only the wing weight lowers yaw amplitude by
**3.975%**. The measured elevator and rudder increases separately raise it by
**0.133%** and **0.630%**. With all measured totals, yaw remains **110.49–119.41%
above** the published drawing. The wing increase also lowers roll and bank
amplitudes at this frequency, where the literal model is already too low.
At 1.5 Hz, all three full-weight alternatives worsen the yaw disagreement.

These three samples are not a frequency sweep, a newly located response
minimum, or a native-reference pass count. They weaken the explanation based
on total component weights alone. They do not rule out a different spatial
distribution, a changed equilibrium/preload, or other historical input
differences. Figure 7's localized wing mass peaks have not been substituted
by these uniform multipliers.

## Retained artifacts and next work

- [Comparison CSV](../../artifacts/daedalus-measured-mass-20261114/report/comparison.csv)
  and [machine-readable report](../../artifacts/daedalus-measured-mass-20261114/report/result.json).
- [Seven separate `.asw` inputs](../../artifacts/daedalus-measured-mass-20261114/cases/),
  with a manifest declaring their mass multipliers and need for a fresh trim.
  For example, [proportional body distribution](../../artifacts/daedalus-measured-mass-20261114/cases/dae-measured-all-shared.asw).
  Their mass-table values were parsed and checked; the normal example remains
  unchanged. A different interpolation or mesh can produce different integrated
  totals, so the stated targets refer to this source/SEGSPL discretization.
- [Bounded driver](../../scripts/check_daedalus_measured_mass.py) and
  [verification receipt](../../artifacts/daedalus-measured-mass-20261114/verification.json).

All 15 small serial jobs are terminal and reaped: 13 succeeded, and two early
response setup attempts were rejected by the existing exact-factor reuse
guards. The diagnostic was corrected to give each immutable modified matrix
pair its own structural factor; the guards were preserved. Maximum CPU time
was **3.238 s**, wall time **7.844 s**, and peak RSS **151.21 MiB**, below the
unchanged 15 CPU s / 25 wall s / 512 MiB limits. Only one BLAS thread was used.

Next distinguish localized wing mass from uniform scaling, then use a fresh
physical trim to assess preload/shape effects for a disclosed reconstruction.
The source papers do not identify a unique historical mass model, and total
weight must not be fitted to one channel. Production physics, the public
aircraft, ISAE fractions and progress history are unchanged. Browser/build
jobs remain on hold; native Bode agreement and the full project goal remain
open.
