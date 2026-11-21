# Daedalus: can the animation identify fin-root motion?

**The existing image calibration is not a sufficiently robust basis for a
physical correction to the fin/boom response.** At five phases of the 1 Hz
movie, camera-pose changes absorb the observed two-coordinate fin-center
harmonic discrepancy while retaining subpixel calibration errors and changing
the centered fin outline by only **0.044–0.202 pixels RMS**. This measures
sensitivity of the image analysis; it is not a corrected native Bode match.

![Camera-profile diagnostics](../../artifacts/daedalus-camera-uncertainty-20261113/report/camera-profiles.png)

[Vector figure](../../artifacts/daedalus-camera-uncertainty-20261113/report/camera-profiles.svg),
[complete profiles](../../artifacts/daedalus-camera-uncertainty-20261113/report/result.json),
[bounded driver](../../scripts/check_daedalus_camera_uncertainty.py).

## Why this check was necessary

The [load decomposition](daedalus-motion-loads-20261113.md) identifies fin-root
translation and rotation as major sources of the fin's motion-induced load.
The [earlier image comparison](daedalus-animation-20261113.md) supports local
boom curvature at 1 Hz, but its projected fin-center vertical amplitude is
2.809 pixels against 3.647 pixels in the movie. Its mean position also differs.
Neither discrepancy had an established camera uncertainty.

The camera was inferred from the fairing outline and propeller disk, then
extrapolated to the tail. A small outline residual does not itself certify
the extrapolated fin-root position. The new finite-profile check tests that
inference with the native pixels and computed aircraft state held unchanged.

## Method and numerical checks

Two exploratory frame checks first allow all nine original camera parameters
to vary while imposing a ±1 pixel vertical shift of the projected model fin
root. At frame 0, calibration RMS changes from 0.33895 to 0.35878/0.35742 pixels.
Frame 45 gives a similar result. These profiles also change perspective distance;
they are retained separately from the stronger test below.

The stronger test **holds each frame's fitted scale and inverse perspective
distance exactly fixed**. Only orientation, image offset and the two original
bounded raster-padding parameters vary. All original bounds remain in force.
Frames **0, 20, 40, 60 and 80** span the first cycle of the 1 Hz movie.

The current fin's complete three-dimensional shape and motion are reconstructed
from the saved accepted equilibrium and harmonic state, at the same F3=40
display amplitude. The original center reproduces the earlier saved projection
within 1e−10 pixels. The target perturbation is the **oscillatory**
observed-minus-predicted center difference in both image axes. The constant mean
mismatch is left untouched. This deliberately imposed target tests
identifiability; it is not a newly accepted calibration or a physical fit.

Each trial camera reprojects the full fairing and disk. Its objective uses
their 360 original support-function residuals plus a penalty on the fin-center
coordinates. All five bounded optimizations converge. The largest center
constraint error is **0.001174 pixels**, below the predeclared 0.002-pixel gate.
The native fin outline is separately compared after removing its center
translation, so a center match cannot conceal a large shape distortion.

| Frame | Requested center shift x / y [px] | Original calibration RMS [px] | Profile calibration RMS [px] | Centered fin-shape change RMS [px] |
| --- | ---: | ---: | ---: | ---: |
| 0 | +1.1820 / −0.8352 | 0.33895 | 0.41059 | 0.10447 |
| 20 | +0.5750 / −0.4721 | 0.33926 | 0.35987 | 0.04432 |
| 40 | −0.9823 / +0.6712 | 0.35800 | 0.40323 | 0.18565 |
| 60 | −0.9162 / +0.7052 | 0.35660 | 0.39326 | 0.20167 |
| 80 | +0.6641 / −0.4263 | 0.38134 | 0.40211 | 0.09343 |

Maximum directional calibration errors in these profiles are **1.135–1.585
pixels**. RMS is not a worst-case pixel bound. The centered fin-outline fit
sometimes improves and sometimes worsens; the initial mean-position and shape
differences remain unresolved.

Local Jacobians, singular values and two-width differences are retained as
diagnostics. The support maximum is piecewise smooth, so changes of active
outline vertex can affect its derivatives. The conclusion uses actual finite
reprojections and residuals, not a covariance estimate. Support directions share
pixels and are correlated; **these RMS values are not statistical confidence
intervals or native validation tolerances**.

## Consequences and limits

The roughly 0.84-pixel vertical amplitude discrepancy cannot reliably identify
a correction to boom EI, fin stiffness, mass, damping or lag under the present
calibration. This does not prove the physical fin motion is correct, or show
that one globally consistent fixed camera and rigid-motion history reproduces
the whole movie: these are five separate frame profiles. Further image
identification would need a shared-camera constraint and better treatment of
rendering, fore-boom motion and the mean shape.

The local boom-curvature check remains separate because it measures departure
from the observed forward tangent. The GIF/Bode publication-date difference
also remains; no common historical operating point has been recovered.
Current Bode yaw is unchanged: approximately **0.074218 versus 0.033986
deg/s/F3** at the drawing's dip.

The next useful dynamics check should examine the coupled boom/fin aerodynamic
reaction and root-motion phase directly, keeping the already checked mechanical
and aerodynamic components distinct. These images do not justify a physical
correction. No aircraft setting or production equation changed.

## Historical lag-law cross-check

Drela's [1999 integrated-model paper](https://web.mit.edu/drela/Public/web/aswing/asw_aiaa.pdf)
already gives quarter-chord circulation/rate lift and moment in Eqs. 15–16,
and `b = 2/π`, `C(k) = (1 + 2ik)/(1 + 4ik)` in Eqs. 22–25. These agree with
the later documented lag approximation. Its preceding convected-wake discussion
does not establish that the 2008 Bode used another option. A fresh official
download matches the existing local PDF exactly; see the
[source supplement](daedalus-historical-lag-sources-20261113.json).

## Evidence and resources

All **nine numerical/image jobs** completed and were reaped with unchanged
inputs, under one BLAS thread, 512 MiB address space, 15 CPU seconds and
25 wall seconds. Maximum use is **2.637 CPU seconds, 8.143 wall seconds and
87.520 MiB RSS**. No equilibrium, aircraft linearization or harmonic solve ran.
The exploratory free-optics profiles remain alongside the five fixed-optics
profiles; their scopes are not merged. The final plot was visually checked.

The [evidence audit](../../artifacts/daedalus-camera-uncertainty-20261113/verification.json)
checks input hashes, runner snapshots, receipts, the source supplement and
report links without rerunning image fits. Browser/build jobs remain held.
ISAE fractions, denominators and progress history are unchanged.
