# Daedalus yaw output and Earth-frame animation

The plotted **Flight frame → Yaw rate r · body z** is the dimensional body-frame
angular velocity **Ωz**. It is not a fin sensor, yaw inferred from tail
translation, or the derivative of the heading angle. The exact production
output is `system.W * Omega[2]` in
[output_perturbation](../../openswing/linear_dynamics.py); the UI takes that
complex value's magnitude and converts radians to degrees when selected.

For the literal [dae.asw](../../examples/dae.asw), `Ground 5 -15.6 0` fixes the
structural reference frame at the bottom of the cabin/fairing. In free flight
this is a moving aircraft reference, not attachment to stationary Earth.
The physical rate of a flexible section can differ from this frame rate.
Simply changing the spatial origin within the same rigid frame cannot change
its angular velocity.

The user confirmed **Earth frame** was selected, so Body-view removal of frame
motion does not explain their observation. Both the body and Earth geometry
paths were nevertheless checked. At the time of this audit, phase playback
used four wall-clock seconds per cycle at every selected frequency. The
[subsequent playback correction](daedalus-playback-clock-20261114.md) makes
model time the default and retains that old clock as labeled phase inspection.
Input amplitude scales the animation, while Bode plots retain unit input.

## References and interpretation

The [authoritative reference index](aswing-authoritative-references.md) and
checksummed catalog were reviewed before this check. Drela's
[rudder Bode drawing](https://web.mit.edu/drela/Public/web/aswing/rudder-bode.pdf)
explicitly labels yaw as **Ωz** and the forcing as unit **F3**. The original
[user manual](../../reference/aswing_doc.txt), Ground block and operating
constraints sections, specifies body-axis rotation rates and explains the
fictitious ground in free-flight calculations. The
[unsteady description](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf),
printed p. 22, Eq. 108, distinguishes an attached gyro:
**Ω_sensor = T_sensor (Ω_frame + ω_elastic)**.

At a steady base the model's Euler kinematics give
`Ω = E(bank, elevation) * d(bank, elevation, heading)/dt`. Thus body yaw rate
and heading rate need not be identical. Their magnitudes differ by only about
**0.1453%** in these cases. Neither a sign convention nor this small projection
accounts for the published dip discrepancy.

## Current-mesh numerical check

This check uses the freshly trimmed, redistributed **98-interval / 103-node**
mesh at **6.7 m/s**, 232.5336 lb, with the literal model, SEGSPL, source airflow,
Mach 0.1, lag, plume, and live influence geometry. It does not establish the
user's exact currently loaded settings or Drela's unavailable operating point.
All **1,953 states** remain in the equations; exact structural elimination
reduces the frequency factorization to 717 coordinates, without modal
truncation. All dynamic columns and the mass matrix were rebuilt on this mesh.

Magnitudes below are per unit native F3. Absolute section rates include the
complex sum of frame and elastic angular velocity, expressed along body z;
they are not sums of their magnitudes.

| Measurement | 1 Hz | 1.1573777 Hz, drawing's yaw minimum |
| --- | ---: | ---: |
| Frame yaw rate, deg/s | 0.0748817 | 0.0738485 |
| Frame heading rate, deg/s | 0.0749905 | 0.0739558 |
| Frame heading amplitude, deg | 0.0119351 | 0.0101699 |
| Pilot-attachment absolute z rate, deg/s | 0.0776474 | 0.0790016 |
| Wing-root absolute z rate, deg/s | 0.102004 | 0.0896334 |
| Fin-root absolute z rate, deg/s | 1.17945 | 1.36622 |

At 1 Hz, the fin-root rate is about **15.75 times** the frame yaw rate. Visible
boom bending can therefore dominate while the cabin's yaw angle remains small.
For nearly level motion, angular amplitude is approximately rate amplitude
divided by `2πf`; the full Euler relation was used for the table. For example,
unit-input cabin heading of 0.01194° becomes 0.1194° at animation amplitude 10.

At the drawing's minimum the recorded reference is **0.0339862 deg/s/F3**,
versus **0.0738485** here (**+117.29%**). The frame, pilot and wing-root checks
do not uncover a mistaken output location that explains it. That is not proof
of the historical model's exact frame definition: the original operating
point/model revision remains unavailable. No sensor location was fitted to
the curve and no production output or physical parameter was changed.

The other freshly solved anchors are 0.119910 deg/s at 0.1 Hz and 0.0939661 at
1.5 Hz. Relative to the previous 107-interval app mesh, yaw changes by +0.721%,
+0.0698%, and +0.173% at 0.1, 1.1573777, and 1.5 Hz respectively. These four
samples do not locate the new mesh's exact minimum or constitute a complete
Bode curve or mesh-convergence study.

## Independent verification

- Three complete-residual derivative directions check the assembled A and M;
  maximum relative errors are **1.281e-11** and **2.292e-11** respectively.
- At both 1 Hz and the drawing's dip, production `output_perturbation` agrees
  with the directly selected frame coordinate and the operating-rate output.
- Independently differentiating the actual body-to-Earth orientation recovers
  that complex angular velocity within **1.80e-14 rad/s/F3**.
- Every Earth-view beam axis and surface point equals its body deformation
  plus the same frame rotation and translation, within **1.06e-9 ft/F3**.
- Four complete nonlinear harmonic-residual probes, using two widths at each
  frequency, have maximum scaled defect **5.249e-12**.
- The actual JavaScript `frequencyGeometry`, `modeGeometry` and
  `trajectoryGeometry` functions were evaluated in isolated V8 against saved
  physical output at each component's ends: **6,624 coordinate checks**,
  four phases, amplitudes 0/1/10, both views, zero disagreement, immutable input.
  This is not a browser rendering test; attachments were excluded from that
  JavaScript subset. Browser/build/WASM checks remain held.

All numerical jobs were serial, one BLAS thread, bounded and reaped. The
planned full frequency sweep was deferred to answer the output-location
question. No solver is left running. No ISAE completion fraction, comparison
scope or progress observation changed.

[1 Hz evidence](../../artifacts/daedalus-yaw-output-20261114/one-hz/result.json),
[dip-frequency evidence](../../artifacts/daedalus-yaw-output-20261114/reference-dip/result.json),
[JavaScript check](../../artifacts/daedalus-yaw-output-20261114/javascript-checks.json),
[new matrix check](../../artifacts/daedalus-regular-mesh-response-20261114/assembled/result.json),
[four response samples](../../artifacts/daedalus-regular-mesh-response-20261114/response/result.json),
[output audit driver](../../scripts/check_daedalus_yaw_output.py),
[assembly driver](../../scripts/check_daedalus_regular_mesh_response.py).

## Follow-up: gyro at the origin or center of mass

The **0.01194°** quoted above is angular displacement amplitude, not angular
rate. At 1 Hz its derivative has amplitude **0.07499°/s**. The comparison is
between our animated orientation and our **0.07488°/s body rate**, with the
small Euler projection accounted for. It does not assert agreement with
Drela's **0.03399°/s** rate at the different, 1.1573777 Hz dip frequency.

The unsteady description, §10.3, Eqs. 99–102, explicitly defines a sensor fixed
in the aircraft frame by anchoring its pylon at the ground point. Its specified
position can be the reference origin, the CG, or another point. Eq. 108 shows
why a gyro depends on attachment rotation and axes, not the pylon tip position.
A point called the center of mass does not by itself define a unique local
orientation on a flexible aircraft.

The original manual's **Bode response selection and plotting** section also
separates these choices: the ordinary response menu includes **73 Wz rot.rate**;
if sensors exist, a second sensor-response menu follows. Thus a native Bode
rotation-rate curve need not represent a separately placed gyro. This supports
the frame-rate interpretation of the published Ωz label without proving which
menu selection was used for its undocumented operating point.

An additional check uses the actual production `measure_sensor` implementation
at **(0,0,0)** and at the loaded CG **(0.202315, 0.004863, -2.870272) ft**.
Each location was checked with three explicit attachments and standard sensor
axes, without modifying the dynamic model or the already-solved response.

| Sensor attachment | Rate at origin, 1.1573777 Hz | Rate at CG, 1.1573777 Hz |
| --- | ---: | ---: |
| Aircraft frame / fairing ground point | 0.0738485 | 0.0738485 |
| Pilot attachment, beam 5 at t=-13.2 | 0.0790400 | 0.0790400 |
| Wing root, beam 1 at t=0 | 0.0894418 | 0.0894418 |

Units are deg/s per native F3. Unlike the earlier absolute-body-z table, these
are the gyro's actual rotated sensor-z components. Moving the sensor tip from
origin to CG produces identical complex angular outputs for each attachment;
the same equality holds at 1 Hz. This does not establish the sensor definition
used for the historical plot. It rules out a mere change in measurement
position, with attachment/orientation held fixed, as the source of this gap.

[Gyro check](../../artifacts/daedalus-reference-gyro-20261114/audit/result.json),
[bounded driver](../../scripts/check_daedalus_reference_gyro.py).

The frequency sweep subsequently completed **103 unique points**, including
the app's 41-point log grid and extra samples around both low- and high-frequency
features. Maximum scaled matrix residual is 6.388e-17; minimum estimated
reciprocal condition is 1.453e-8. The sampled yaw minimum in 0.8–2 Hz is
0.0733738 deg/s/F3 at 1.08 Hz. A complete comparison plot and further feature
refinement were still pending at that observation; this discrete minimum is
not a continuous optimum.
See the [sweep observation](../../artifacts/daedalus-regular-mesh-response-20261114/curve-observation.json).

Subsequent bounded frequency refinement, with the same saved full matrices and
no fitted physical parameters, locates the yaw minimum at **1.09941677 Hz,
0.0733135922 deg/s/F3**. The [new-mesh four-output comparison](daedalus-current-bode-20261114.md)
is now available from the app, with 162 saved frequencies and separate
feature-to-feature and identical-frequency comparisons.
See the [refined minimum](../../artifacts/daedalus-regular-mesh-response-20261114/refine-yaw-low-min/result.json)
and [playback-clock follow-up](daedalus-playback-clock-20261114.md). The latter
fixes a display-time ambiguity; it does not change the physical response.
