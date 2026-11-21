# Daedalus: localized wing mass and a physical retrim

The localized mass peaks visible in Drela's wing paper do **not** recover the
published Bode notch in this disclosed reconstruction. At 1.157378 Hz, the
nominal peak masses give yaw **0.070624 deg/s per F3** when the original mean
shape is held, and **0.072955** after a physical nonlinear retrim. The literal
model gives **0.074218**; the published drawing gives **0.033986**. Retrimming
therefore leaves a **114.66%** amplitude excess at this frequency.

![Retained curves and newly computed sample points](../../artifacts/daedalus-wing-peak-mass-20261114/report/comparison.png)

The lines are the retained literal-aircraft sweep and reference digitization.
The new results are markers at three frequencies, not a newly computed sweep
or a newly located response minimum. All four published output channels remain
separate.

## Source and reconstruction

The [authoritative index](aswing-authoritative-references.md) and checksummed
catalog were consulted. Drela's *Method for Simultaneous Wing Aerodynamic and
Structural Load Prediction*, AIAA-89-2200, Figure 7 (PDF p. 8 / printed p. 329),
contains localized mass peaks. The [preceding property audit](daedalus-paper-properties-20261114.md)
retains the independent raster trace, calibration and uncertainty limitations.

| Existing station pair | Added weight at each station | Trace-area bound at each station |
| --- | ---: | ---: |
| ±14 ft | 1.738957 lb | ±0.282278 lb |
| ±42 ft | 0.631546 lb | ±0.220913 lb |

Concentrating these excess areas at the existing junction stations is an
explicit approximation. The traced peak maxima are at about 13.784 and
41.928 ft. Point centroids are placed at the existing section mass centroids,
with zero intrinsic inertia, drag area, volume and spin. The physical pylon
offset, its rotation and its inertia/gravity moments are retained. A separate
variant puts the centroids directly on the beam axes. Neither placement is a
measured centroid or an authenticated historical ASWING input.

The nominal addition is **4.741005 lb**. Lower/upper trace-area cases add
**3.734623 / 5.747387 lb**. These bounds concern vertical trace and baseline
endpoint uncertainty only; they do not bound all drawing, location or model
errors. Another case spreads exactly the nominal added weight proportionally
over the existing wing density, isolating localization from total weight.
At the dip, its yaw is **0.070517**, close to the concentrated case's 0.070624.

This is the paper's **peak excess** added to the public model. It does not
replace the rest of the wing density with Figure 7's complete curve, use the
separate Cruz measured weights as a normalization, or reconstruct every input
in the 1989 paper. Stiffness, aerodynamic tables, joints, speed, Mach number,
circulation lag and plume settings remain unchanged. The existing 108-node,
103-interval, 82-circulation mesh already contains the four stations.

## Equations and numerical checks

The unsteady technical description, section 6.3, Eqs. 46–47 (PDF pp. 9–10),
defines the point-mass loads. Four independent unit operators cover the two
station pairs and two centroid choices. Their gravity, translational inertia,
offset-induced rotational inertia and global moment derivatives are checked
against the complete nonlinear residual at two difference widths. Maximum
absolute error is **2.754e-13** in scaled units; maximum relative error is
**1.538e-10**. No finite-interval rotary correction is added to a point object.

Five changed-mass cases plus the baseline are solved at each of three
frequencies: **18 complete descriptor solves**. These first comparisons hold
the original mean state by a constant residual offset, while retaining all
gravity and inertia derivatives. No modes or equations are removed.

The nominal case then receives a **physical nonlinear trim**, with no residual
offset. A previously assembled literal-aircraft tangent accelerates the
iteration, but each candidate is evaluated against the changed aircraft's
full nonlinear equations. The residual decreases from 1.728e-3 to
**3.128e-10**. This is a converged physical equilibrium; reusing that tangent
does not establish a rank certificate for the changed aircraft.

| Quantity | Physically retrimmed nominal case |
| --- | ---: |
| Speed | 6.7 m/s |
| Mach number | 0.1 |
| Total weight | 238.042938 lb |
| Angle of attack | 3.287601° |
| Maximum section CL | 1.323737 |
| Wing-tip heights above loaded root | 8.107789 / 8.112471 ft |

The settings retain the source moving-airflow operator, SEGSPL interpolation,
live influences, circulation lag and plume. They do not identify the browser
defaults or the original Bode operating point.

For the new equilibrium, full 2,044-state harmonic residuals are corrected
using the old complete descriptor as an iterative preconditioner. The changed
aircraft's full nonlinear residual supplies every harmonic derivative,
including rudder forcing and changed aerodynamic, geometric and preload terms.
The old factor's condition estimate applies only to that preconditioner.

Every final state is checked at two fourth-order difference widths, 0.002
and 0.004 in forcing/state amplitude. Both must satisfy the unchanged
**2e-11** maximum harmonic residual and **2e-7** relative next-output-correction
gates. The largest accepted residual is **1.891e-11**; the largest relative
difference between the two widths' output corrections is **1.217e-8**.

At the dip, smaller widths produced residuals of 2.462e-11 and 2.820e-11 in
two rejected verification attempts, despite tiny output corrections. An extra
correction and the wider stencil pair resolve the subtraction-noise concern
without relaxing either gate. All attempts remain in the evidence directory;
an unsuccessful acceptance check is not credited as a validated response.

## Comparison

Yaw magnitudes are deg/s per native F3 unit. Reference values are interpolated
logarithmically from the retained drawing digitization where needed.

| Frequency, Hz | Literal model | Peak masses, held mean | Peak masses, physical retrim | Drela drawing |
| --- | ---: | ---: | ---: | ---: |
| 0.1 | 0.121763 | 0.121821 | 0.117368 | 0.118238 |
| 1.157378 | 0.074218 | 0.070624 | 0.072955 | 0.033986 |
| 1.5 | 0.094316 | 0.098722 | 0.099410 | 0.081818 |

Retrimming improves low-frequency yaw to **−0.74%** from the reference, but
worsens the 1.5 Hz yaw difference to **+21.50%**. At the dip, the retrimmed
roll, sideslip and bank errors are respectively **−43.67%, +19.23%, −51.43%**.
This cannot be described as agreement with the four published curves.

## Artifacts and consequence

- [Full comparison CSV](../../artifacts/daedalus-wing-peak-mass-20261114/report/comparison.csv)
  and [report](../../artifacts/daedalus-wing-peak-mass-20261114/report/result.json).
- [Conditional `.asw` file](../../artifacts/daedalus-wing-peak-mass-20261114/case/dae-wing-peak-mass.asw)
  and [converged physical state](../../artifacts/daedalus-wing-peak-mass-20261114/trim-1/state.json).
  This file is separate from the normal example. Its listed results require
  the recorded numerical policy and operating settings.
- [Bounded driver](../../scripts/check_daedalus_wing_peak_mass.py) and
  [verification receipt](../../artifacts/daedalus-wing-peak-mass-20261114/verification.json).

All **28** bounded serial jobs succeeded and were reaped; intermediate harmonic
iterates and the two rejected verification checks are retained with their
acceptance flags. The largest CPU time was **4.482 s**, wall time **15.741 s**
and RSS **134.78 MiB**, below the unchanged 15 CPU s / 25 wall s / 512 MiB caps.
All jobs used one BLAS thread. There are 326 explicitly recorded full-residual
probes, in addition to initialization, trim and reporting evaluations.

The peak-mass explanation is insufficient under these assumptions, including
its physical retrim. Before further parameter changes, the remaining sharp
in-plane stiffness transition in Figure 7 should be audited independently of
the Bode response; static vertical deflection alone does not verify that
stiffness distribution. Historical model differences must remain distinct
from production physics defects. Production files, the public aircraft and
ISAE fractions/history are unchanged. Browser/build work remains on hold;
native Bode agreement and the full project goal remain open.
