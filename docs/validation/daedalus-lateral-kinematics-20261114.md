# Daedalus lateral acceleration and animation amplitudes

The native sideslip, roll-rate and yaw-rate curves exclude **zero acceleration
in the mean sideslip direction**, subject to the stationary straight-flight
assumptions below. This narrows a possible constraint-setting explanation for
the unmatched Bode curves. It does not identify the original operating point
or turn the comparison into a pass.

The app also now shows **aircraft-frame yaw-rate amplitude and heading-angle
amplitude** beside the harmonic animation. Both use its selected frequency,
input and input amplitude. They are explicitly different quantities, with
deg/s versus degrees for Daedalus. Angular unit changes update this readout
without recalculating the solution.

## Independent kinematic bound

The [authoritative reference index](aswing-authoritative-references.md) and
source catalog were consulted. The current unsteady description, printed
pp. 6–7, Eqs. 16–21, distinguishes prescribed acceleration constraints from
free-flight net-load equations. Its translational kinematics are

`dU/dt + Omega × U = a_origin`.

For a stationary zero-rate base with airspeed V, angle of attack alpha and
sideslip beta, define the direction of aircraft motion and the sideslip unit
direction in the documented body axes:

```text
e = (-cos(alpha) cos(beta), sin(beta), -sin(alpha) cos(beta))
b = ( cos(alpha) sin(beta), cos(beta),  sin(alpha) sin(beta))
```

Then `e × b = (sin(alpha), 0, -cos(alpha))`. Projecting the linearized velocity
equation onto b gives the exact first-order relation

`a_side_hat/V = i*omega*beta_hat + sin(alpha)*p_hat - cos(alpha)*r_hat`.

Here `a_side` is inertial acceleration projected onto b; p and r are body-axis
roll and yaw rates. The literal model has coincident origin, velocity and
acceleration reference points. No gust input or nonzero base rotation is
assumed. The relation holds at nonzero mean sideslip too, but **a_side equals
body-y acceleration only at zero mean sideslip**. At nonzero mean sideslip,
axial and normal accelerations also enter the projection.

For every real alpha and every response phase, Cauchy–Schwarz bounds the
rotational term by `R = sqrt(abs(p_hat)^2 + abs(r_hat)^2)`. Consequently,

`max(0, omega*abs(beta_hat)-R) <= abs(a_side_hat)/V <= omega*abs(beta_hat)+R`.

A zero-side-acceleration condition therefore requires
`omega*abs(beta_hat)/R <= 1`. No speed, alpha, phase or physical coefficient
is fitted to test this necessary condition.

## Native drawing and current states

The reference comes from the same checksummed native PDF vertices as the
[current four-output comparison](daedalus-current-bode-20261114.md). The
existing conservative ±0.75 PDF-point allowance is retained: curve extrema
over x ±1.5 points and y ±0.75 points, plus frequency displacement of ±0.75
point. This is a graphic envelope, not a solver tolerance or physical error bar.

| Frequency | Central ratio omega·abs(beta)/R | Conservative lower ratio | Necessary abs(a_side)/V range, 1/s per F3 | OpenSwing, 1/s per F3 |
| --- | ---: | ---: | --- | ---: |
| 0.1 Hz | 2.20066 | 1.99561 | 0.00271265–0.00879353 | 0.00457971 |
| 1 Hz | 2.50112 | 2.14932 | 0.00166519–0.00508824 | 0.00270462 |

The lower ratios exceed one, so zero side acceleration cannot produce those
three plotted magnitudes under these assumptions. For zero mean sideslip this
also rules out prescribing zero body-y acceleration. Nonzero published p and r
likewise require nonzero harmonic angular accelerations under Eq. 17. These
facts support retaining lateral dynamics; they do not prove the precise native
load constraints, mean sideslip, nonzero acceleration prescription or controls.

All 162 current saved responses lie within the necessary lateral-acceleration
envelopes. That overlap is **not agreement or validation**: phases are missing,
the inequality is deliberately broad, and yaw/roll magnitudes remain unmatched.
The JSON retains every sampled bound, including the frequencies where zero
side acceleration is not excluded. Clustered refinement samples are not
independent validation cases.

The current full states independently reproduce the kinematic equations and
the sideslip output:

| Check over 162 saved states | Maximum absolute error |
| --- | ---: |
| Translational frame equation | 6.207e−17 ft/s²/F3 |
| Angular-acceleration equation | 1.388e−16 rad/s²/F3 |
| Sideslip output reconstructed from physical velocity | 8.674e−19 rad/F3 |
| Projected acceleration identity | 4.907e−18 1/s/F3 |

The check uses the saved states and layout/scales, independently constructed
unit vectors, and the literal input reference records. It does not call the
production dynamics functions or solve another aircraft. All earlier matrix
source hashes are checked against the current numerical files. One bounded
job completed and was reaped: 1.021 CPU seconds, 36,320 KiB peak RSS, under
the existing one-thread / 512 MiB / 15 CPU-second / 25 wall-second limits.

## Animation readout and verification

The new readout uses `rates_body.z` and `attitude_rad.z` from the same selected
saved response as the plot and geometry. It reports harmonic **amplitudes**,
not instantaneous values or the angular rate of a flexible section. No sensor
location or output convention changes. Missing frame data hides the readout.
The quantities remain physical when the optional phase-inspection clock slows
or speeds playback. Body view can remove frame rotation visually while these
physical amplitudes remain unchanged.

For the existing current-mesh 1 Hz case, it displays:

| Animation input amplitude | Body yaw-rate amplitude | Heading-angle amplitude |
| --- | ---: | ---: |
| 1 | 0.0748817 deg/s | 0.0119351 deg |
| 10 | 0.748817 deg/s | 0.119351 deg |

These agree with the saved physical output and the earlier independently
differentiated [Earth-orientation audit](daedalus-yaw-output-20261114.md).
Six repository test bodies pass **106 assertions** in isolated V8 using the
actual 35 dependency modules, with simulated selection events and animation
clock. They cover amplitude/unit changes and preservation of the saved solve.
The actual physical fixture separately checks the displayed values above.
Updated modules are served by the existing development server. Browser/Node,
build and WASM checks remain held; browser rendering is not claimed.

## Search limitation and evidence

A fresh archive-index search for Daedalus companion files and session
instructions did not complete: the broad query timed out; the narrower
Daedalus-prefix query returned HTTP 503 and the session-prefix query timed out.
The [receipts](../../reference/daedalus-archived-setup-20261114/) preserve those
outcomes. They are **not evidence that the files were never archived**. The
previous successful historical model/PDF downloads remain separate.

- [Bounded analysis driver](../../scripts/check_daedalus_lateral_kinematics.py)
- [Numerical result](../../artifacts/daedalus-lateral-kinematics-20261114/audit/result.json)
- [All reference bounds](../../artifacts/daedalus-lateral-kinematics-20261114/audit/bounds.csv)
- [Readout verification](../../artifacts/daedalus-motion-readout-20261114/verification.json)

No production physics, original model, ISAE fraction or comparison scope
changed. Native Bode agreement and the original operating point remain open.
