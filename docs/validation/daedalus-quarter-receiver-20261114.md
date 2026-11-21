# Daedalus: physical versus wind-aligned quarter-chord receiver

The two conditional interpretations tested here change yaw amplitude by only
**+0.07241%** and **−0.11693%** at the published dip. Neither explains the
current **+118%** yaw discrepancy. The complete feedback calculations converge,
and independent aerodynamic quadrature verifies the receiver-change derivative.
No production equation, aircraft property, default or ISAE fraction changed.

![Full response and small changes from the original](../../artifacts/daedalus-quarter-receiver-20261114/report/quarter-receiver.png)

## What the sources actually say

The [authoritative reference index](aswing-authoritative-references.md) and
[checksummed catalog](aswing-authoritative-sources.json) were consulted.

The [steady description](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf)
defines relative velocity at a specified spatial location in Eq. 64, printed
p. 15, and evaluates lift velocity at the bound vortex in Eq. 67, p. 16.
Equation 155, p. 32, explicitly puts that receiver along the wind direction:

```
r_hv = r_a + ((c/4 - x_o) / |wind × span|) wind
```

In contrast, the [unsteady extension](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf),
Eqs. 29–31, printed p. 8, defines the quarter-chord offset along the physical
chord direction and uses it for bound-vortex velocity. Equations 34–36 use
that relative velocity for both steady and circulation-rate lift.

This distinction is not confined to the two different documents. The steady
description's Eq. 72, pp. 16–17, already computes the lift moment with the
physical chord arm while Eq. 155 defines a wind-aligned velocity receiver.
OpenSwing follows that combination. Unsteady Eq. 36 likewise puts both lift
terms at physical quarter-chord; the production moment arm already does so.
Thus the apparently mixed geometry is present in the primary formulation,
and these tests do not establish that either occurrence is a solver bug.

## Two separate diagnostics

Both use the unchanged source-airflow/SEGSPL equilibrium at 6.7 m/s, Mach 0.1,
with 108 nodes, 103 intervals, 82 circulation states and 2,044 coordinates.
Both retain the wind-aligned bound endpoints, control points, wakes, source
cores and exclusion of each receiver's own bound segment.

1. **Physical kinematic arm:** add
   `−(Omega + local_omega) × (r_physical_quarter − r_hv)` to force-receiver
   incident velocity. Induced, volume and plume fields stay at the original
   receiver. At the stationary equilibrium, the correction is identically zero.
2. **Physical field receiver:** move the force receiver to
   `r_a + (c/4 − x_o) chord_direction`, including its motion and vortex, volume
   and plume sampling. The existing section formulas, including profile drag,
   use the resulting velocity. Other receivers and source vortices stay fixed
   by the original construction. This is explicitly a hybrid diagnostic:
   it does not establish native ASWING's treatment of off-bound-line receivers.

Moving the field receiver changes mean loads, with maximum scaled residual
change **1.18261e−4**. A constant offset holds the original equilibrium for
this linear comparison; the result is not a physical retrim. The kinematic
variant requires no such nonzero offset. The diagnostics do not reallocate
moment arms, change airfoil laws or fit parameters to the Bode plot.

| Beam | Maximum receiver displacement, ft | Maximum mean velocity change, ft/s |
| --- | ---: | ---: |
| Wing | 0.057071 | 0.304881 |
| Stabilizer | 0 | 0 |
| Fin | 0 | 0 |
| Fairing | 0.318488 | 3.068363 |

The fin and stabilizer have `Xax = 0.25`, so their two receiver locations
coincide. Their coupled responses can still change through the aircraft.

## Full coupled response and independent checks

At each iteration, fourth-order real/imaginary stencils with step 0.0005
evaluate the complete change to the network residual. The iteration solves
`K0 dz = −(K0 z − B0 − delta_R)`, where `K0 = iω M − A`. The existing exact
beam/velocity elimination factors 748 coordinates and recovers all 2,044;
no mode truncation is used. The original factor's reciprocal-condition
estimate is 2.076e−8. It is not an estimate for a separately assembled
modified matrix.

The unchanged acceptance gates are absolute residual below 2e−11, relative
residual below 2e−8, and next-output relative correction below 2e−7. The
kinematic variant needs two corrections; the field-receiver variant needs
four. The latter's three-correction state misses the absolute gate at
2.60662e−11 despite a tiny output correction, so it was not accepted.

| Accepted variant | Absolute residual | Relative residual | Next-output relative correction | Residual with step 0.001 |
| --- | ---: | ---: | ---: | ---: |
| Kinematic | 6.49837e−14 | 1.47546e−12 | 2.48750e−9 | 4.37500e−14 |
| Field receiver | 2.81893e−13 | 3.84425e−12 | 1.10626e−9 | 2.81893e−13 |

Both wider-step evaluations use exactly the same accepted states. Their
remaining output corrections differ from the first step by at most
1.63537e−9 relative to the accepted outputs. The report uses the evaluated
states `kinematic-update-1` and `receiver-update-3`; the later diagnostic
corrections are not silently treated as evaluated states.

A separate evaluator integrates the vortex, volume and plume fields and
transfers physical loads without calling production aerodynamic routines.
Its complex-step real/imaginary directional differences verify the complete
field-receiver residual change, including changing moment arms, within
**3.50401e−14** scaled units. This checks the declared conditional model,
not its historical provenance. All unchanged body and engine force
derivatives in that comparison are exactly zero.

## Comparison with the drawing

Magnitudes at **1.15737773741517 Hz** are below. Rates use deg/s per native
F3 unit; sideslip and bank use degrees per native F3 unit.

| Output | Original | Physical kinematic arm | Physical field receiver | Published reference |
| --- | ---: | ---: | ---: | ---: |
| Yaw rate | 0.07421777 | 0.07427151 | 0.07413099 | 0.03398619 |
| Roll rate | 0.02421862 | 0.02425621 | 0.02417401 | 0.03685267 |
| Sideslip | 0.03031630 | 0.03031363 | 0.03030526 | 0.02517766 |
| Bank | 0.00309191 | 0.00309736 | 0.00308612 | 0.00507383 |

The largest amplitude change among the eight diagnostic outputs is 0.18725%.
The field-receiver variant still has yaw **+118.121%**, roll **−34.404%**,
sideslip **+20.366%**, and bank **−39.176%** relative errors. These are one-mesh,
one-frequency diagnostics, not a full-spectrum validation or a browser run.
The source/SEGSPL operator remains an explicit diagnostic selection.

## Consequence and evidence

Further quarter-chord location experiments are lower priority. Preserve the
documented steady geometry until stronger evidence resolves the convention.
Next compare the documented K/F frozen-influence default under this same
source/SEGSPL operator, with a fresh physical trim. The
[earlier frozen/live comparison](daedalus-speed-controlled-20261113.md) used
the preceding midpoint operator. Its small effect is useful evidence, but
does not replace a controlled check of the selected source formulation.

The [driver](../../scripts/check_daedalus_quarter_receiver.py),
[report](../../artifacts/daedalus-quarter-receiver-20261114/report/result.json),
[CSV](../../artifacts/daedalus-quarter-receiver-20261114/report/comparison.csv),
and [verification receipt](../../artifacts/daedalus-quarter-receiver-20261114/verification.json)
retain the details. Twenty-five serial bounded jobs are terminal and reaped;
24 succeeded. The initial base reporting job incorrectly requested a lifting
velocity field on a body strip. Its traceback is retained; `base-v2` selects
lifting strips explicitly. No solver equation changed. Successful jobs used
183 native residual evaluations and eight independent evaluations. Peak child
resources were 3.374 CPU seconds, 5.575 wall seconds and 115.211 MiB RSS,
within the unchanged one-thread, 512 MiB/15 CPU-second/25 wall-second caps.
No browser, Node, build or background solver job ran.
