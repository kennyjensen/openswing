# Native Daedalus GIF: one camera across a complete cycle

**The native GIF still does not provide a reliable way to choose between the
published and current OpenSwing yaw-rate magnitudes.** This follow-up removes
the independent per-frame camera freedom from the earlier image study. With
one camera across 18 unique phases of the 1 Hz movie, constraining both roll
and yaw to the two Bode alternatives changes the predicted outlines by only
**0.0361 pixels RMS**, at a background outline-fit RMS of roughly 0.4 pixels.

This is an ambiguity diagnostic under a disclosed image model. It does not
validate either complete physical response, establish a statistical confidence
interval, or identify Drela's operating point. No production equation, aircraft
parameter, default, Bode value or ISAE count changed.

![Shared-camera comparison](../../artifacts/daedalus-shared-camera-20261114/report/comparison.png)

[SVG](../../artifacts/daedalus-shared-camera-20261114/report/comparison.svg),
[complete results and receipts](../../artifacts/daedalus-shared-camera-20261114/report/result.json).

## Evidence and motivation

The [authoritative index](aswing-authoritative-references.md), catalog and
[animation supplement](daedalus-animation-sources-20261113.json) were reviewed.
The retained official GIF has an annotated frequency of **1 Hz** and display
forcing amplitude **F3=40**. Its fairing and propeller outlines come from the
previous checksummed pixel extraction, with literal fairing geometry and a
5.5 ft propeller radius.

The [earlier image comparison](daedalus-animation-20261113.md) supports local
boom curvature but does not reliably measure frame yaw. The
[previous uncertainty study](daedalus-camera-uncertainty-20261113.md) showed
that independent camera-pose changes at five phases could absorb small fin
motion differences. It left open whether one fixed camera over the entire
cycle could remove that ambiguity. This study addresses that narrower gap.

## Model and constraints

- Frames 0, 5, ..., 85 provide 18 uniformly spaced phases. The repeated endpoint
  at frame 90 is excluded to avoid counting the same observation twice.
- One camera orientation, image scale, offset, perspective distance and pair
  of raster-padding parameters apply to the whole cycle. Their bounds are the
  same as the earlier calibration.
- The fairing and propeller disk share a linear harmonic rigid rotation and
  translation. The rotation pivot is the fairing-bottom frame anchor. No wing,
  fin, aerodynamic load or computed elastic response is fitted.
- The free image fit has 21 parameters: nine camera/padding parameters and
  six cosine/sine coefficients each for rotation and translation.
- In the constrained fits, a prescribed rotation-rate magnitude fixes the
  corresponding rotation amplitude using `angle = rate * 40 / (2*pi*1 Hz)`.
  Its phase remains free. Pitch and translation remain free even when roll
  and yaw magnitudes are both fixed. These are therefore **magnitude feasibility
  checks**, not reproductions of either complete complex response.
- The literal rigid calibration objects neglect small fore-boom/fairing
  deformation, possible display conventions and correlated raster errors.
  The fitted propeller raster padding reaches its lower bound in every fit.

## Results at 1 Hz

Rates below are deg/s per unit native F3. These are **1 Hz** values, not the
different 1.15738 Hz frequency of the published yaw minimum.

| Constraint | Roll magnitude | Yaw magnitude | Outline RMS, px | Largest directional error, px |
| --- | ---: | ---: | ---: | ---: |
| Unconstrained image fit | 0.15191 | 0.10728 | 0.390310 | 2.2762 |
| OpenSwing yaw only; roll free | 0.14117 | 0.074882 | 0.395638 | 2.2884 |
| Published yaw only; roll free | 0.13610 | 0.058746 | 0.402169 | 2.2942 |
| OpenSwing roll and yaw | 0.033021 | 0.074882 | 0.403699 | 2.2027 |
| Published roll and yaw | 0.049911 | 0.058746 | 0.407217 | 2.2254 |

The unconstrained image optimum must not be treated as a newly recovered native
gyro measurement. Its inferred roll magnitude is about three times the published
value, and the physical/raster assumptions have not been established to the
required subpixel accuracy.

Switching the constrained roll/yaw pair changes outline predictions by
**0.03610 px RMS / 0.10098 px maximum**, and changes overall fit RMS by only
**0.00352 px**. Constraining yaw alone gives a similar ambiguity:
0.03225 px RMS / 0.11890 px maximum prediction change. These are descriptive
image differences, not independent statistical errors or acceptance bands.

Consequently, even this shared-camera test supplies no defensible reason to
replace the current omega_z output, average sensors as the default, or alter
boom stiffness/damping to match the GIF. The numerical Bode discrepancy and
the user's uncaptured loaded-result mismatch remain open. Investigation should
return to the coupled load/motion equations and reference setup evidence.

## Verification

All five native-image fits report convergence. A separate noiseless synthetic
test generates outlines from a known camera/motion tuple and starts from the
different free-fit tuple. It recovers all three rate amplitudes with maximum
relative error **1.193e-7** and outline RMS **9.38e-7 pixels**. This tests the
parameterization and inversion; it does not validate the real-image assumptions.

The report checks **78 source-pin occurrences**, using the actual saved runner
for each job. Earlier jobs retain their script versions before optional
synthetic and roll constraints were added. The six fit/check jobs and one plot
job were small, serial, one-BLAS-thread processes under the existing 512 MiB,
15 CPU-second and 25 wall-second limits. All completed and were reaped. Maximum
fit use was **5.145 CPU seconds / 99,644 KiB peak RSS**. No aerodynamic/structural
solve, Node, browser, build or WASM job ran. The final plot was visually checked.

[Fit driver](../../scripts/check_daedalus_shared_camera.py),
[report driver](../../scripts/report_daedalus_shared_camera.py),
[verification receipt](../../artifacts/daedalus-shared-camera-20261114/verification.json).
