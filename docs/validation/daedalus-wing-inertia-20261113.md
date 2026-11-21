# Daedalus: independent current-wing inertia and gravity reconstruction

The wing's large yaw reaction is reproduced by an independent implementation
of Drela's real-mass equations. No missing or duplicated acceleration term was
found at the two checked frequencies. A separate distributed-mass integral
changes the complex yaw reaction by **0.221% at 0.2 Hz / 0.298% at 1.157378 Hz**
for the same supplied motion. These results weaken a wing mass-discretization
explanation; they do not validate the motion itself or resolve the Bode gap.

The accepted complete-aircraft yaw response remains **0.074218 versus 0.033986
deg/s per native F3** at the drawing's selected dip. No production equation,
property, operating condition, acceptance tolerance or ISAE fraction changed.

![Wing real-mass moment decomposition](../../artifacts/daedalus-wing-inertia-20261113/report/wing-inertia.png)

[Vector plot](../../artifacts/daedalus-wing-inertia-20261113/report/wing-inertia.svg)
and [complex load table](../../artifacts/daedalus-wing-inertia-20261113/report/wrenches.csv).
The two panels have different horizontal scales. Real and imaginary components
use the application's VibeLattice color sequence.

## Reference and scope

The [authoritative reference index](aswing-authoritative-references.md) and
checksummed catalog were consulted. The governing references are Drela's
[steady technical description](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf),
printed pp. 17–18, Eqs. 77–83, and
[unsteady extension](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf),
printed pp. 6–7 and 9, Eqs. 16–17, 23, 37–40. Their current SHA-256 hashes
were checked against the source catalog.

This uses the current literal `dae.asw`, 6.7 m/s, SEGSPL source-equation case:
108 nodes, 103 beam intervals, 82 circulation unknowns, 2,044 dynamic
coordinates. The previous [wing-mount reconstruction](daedalus-wing-mount-20261113.md)
identified the real-mass/gravity wing wrench as a major driver of forward-boom
yaw bending. The [older mixed-inertia audit](daedalus-mixed-inertia.md) used
a different midpoint/Gauss operator and is not substituted for this check.

The new [reference evaluator](../../scripts/wing_inertia_reference.py) imports
only NumPy. It does not call production inertial loads, motion interpolation,
gravity rotation or Euler-angle routines. The
[adapter](../../scripts/check_daedalus_wing_inertia.py) supplies loaded geometry,
input-property samples and saved full harmonic states. It reads the input
property tables directly rather than using the production mass-sample caches;
the parser/property interpolation itself remains an input to this comparison.

At the stationary base, with harmonic convention `exp(i omega t)`, it uses

```
a_origin = i omega U_hat + Omega_hat × U_0
alpha = i omega Omega_hat
a_cg = a_origin + alpha × (r + offset)
       + i omega u_hat + (i omega w_hat) × offset
delta_g = -(Omega_hat / (i omega)) × g_0
delta_f = mass * (delta_g - a_cg)
delta_m = offset × delta_f + delta_offset × f_0
          - I * i omega (Omega_hat + w_hat)
```

Mean frame/local rotation rates and accelerations are explicitly checked to be
zero. Centrifugal, Coriolis and precession products therefore have no first-order
contribution here. The source endpoint products and symmetric nodal transfer
are declared discretization conventions, not independently established native
ASWING implementation details. Steady Eq. 80's finite-segment term is included
once. The literal wing has zero intrinsic section rotary-inertia fields.

The reaction is summed about the **moving boom attachment** at beam 4, t=0.
Gravity's moving-CG and moving-reference moment arms are differentiated too.
The wing contains no point masses or custom applied loads; those exclusions
are asserted. Its endpoint-integrated weight is **38.53818323 lb**.

## What creates the reaction

Body-z moments below are lb ft per native F3. They are linear accounting terms
of one supplied coupled response, not separate physical aircraft responses.

| Term | 0.2 Hz | 1.157378 Hz |
| --- | ---: | ---: |
| Frame angular acceleration | −0.195313 − 2.961543i | −0.987154 − 7.345838i |
| Elastic translational acceleration | −0.351201 − 0.039826i | −9.645920 + 10.219811i |
| Finite-segment rotary inertia | −0.002711 − 0.014756i | −0.053178 + 0.015445i |
| Complete real-mass/gravity reaction | **−0.569252 − 3.023555i** | **−10.701344 + 2.907245i** |

The complete table retains frame velocity derivatives, convective acceleration,
CG-offset angular acceleration and gravity terms. Near the dip, much of the
elastic translational acceleration is motion associated with wing-root rotation.
An exact second decomposition gives:

| Supplied motion contribution | Body-z moment at 1.157378 Hz |
| --- | ---: |
| Aircraft frame | −1.011237 − 7.362907i |
| Wing-root translation | +0.006106 − 0.007047i |
| Wing-root rotation | −7.998330 + 8.164689i |
| Wing deformation relative to root | −1.698391 + 2.113040i |
| Moving boom moment reference | +0.000508 − 0.000529i |

This follows the actual complex phases. It does not establish that increasing
or decreasing a stiffness would improve agreement, and no parameter was fitted.

## Numerical checks and separate mass-integration diagnostic

| Independent replay check, maximum across both frequencies | Absolute error |
| --- | ---: |
| Base nodal gravity force | 2.665e−15 lb |
| Base nodal gravity couple | 7.772e−16 lb ft |
| Harmonic nodal force | 1.138e−11 lb/F3 |
| Harmonic nodal couple | 4.511e−12 lb ft/F3 |
| Complete wrench about moving boom attachment | 6.603e−10 native wrench units/F3 |
| Gravity orientation versus actual state mapping | 1.783e−11 ft/s²/F3 |

Translation/rotation kinematics and origin acceleration also agree; all
decomposition sums close at floating-point precision. Full receipts and arrays:
[slow](../../artifacts/daedalus-wing-inertia-20261113/slow/result.json),
[dip](../../artifacts/daedalus-wing-inertia-20261113/dip/result.json).

The separate [continuous integral](../../scripts/wing_mass_integral_reference.py)
uses linear endpoint property and centerline interpolation, geodesic section
frames and their exact rotation tangent. It integrates the physical mass-CG
force and moment directly along each interval. Line rotary inertia then comes
from that spatial integral, so **no second ds²/12 term is added**. This is a
disclosed quadrature diagnostic, not a replacement solver or an assertion of
historical ASWING behavior.

Two analytic controls, a uniform straight beam undergoing either frame rotation
or equivalent elastic rigid rotation, recover `m L²/12` with maximum absolute
error 5.685e−14. Both the endpoint rule and continuous integral pass; this checks
against missing, doubled or endpoint-lumped line inertia. Four- versus eight-point
Gauss integration changes the actual-wing wrench by at most 2.667e−15.

| Frequency | Complex yaw-moment difference | Complex roll-moment difference |
| --- | ---: | ---: |
| 0.2 Hz | 0.22110% | 0.24839% |
| 1.157378 Hz | 0.29779% | 0.37607% |

These percentages divide the magnitude of the complex wrench difference by the
endpoint result's magnitude. They are **not Bode-response errors or bounds**:
no modified aircraft was solved. The independent interpolation also does not
establish continuum accuracy for unspecified historical property sampling.
[Integral results and controls](../../artifacts/daedalus-wing-inertia-20261113/integral/result.json).

All four small jobs completed, ran serially and were reaped. Maximum CPU time
was **2.656 s**, wall time **7.243 s**, and peak RSS **89.911 MiB**, under the
one-thread/512 MiB/15 CPU-second/25 wall-second limits. Source pins, artifact
replays and local links are recorded in the
[verification receipt](../../artifacts/daedalus-wing-inertia-20261113/verification.json).
Browser, Node/Vite and build checks remain on hold; these are Python diagnostics.

## Next discriminating check

The current mass equations account for the observed reaction, and the previous
[complete mesh refinement](daedalus-structural-resolution-20261113.md) changed
dip-frequency yaw magnitude by only −0.217%. The next useful check is the
**predicted mechanical motion and phase**, including live brace prestress,
under prescribed wing-root motion on the current loaded source model. The
[older wing/brace continuum comparison](daedalus-wing-brace-dynamic.md) checked
the midpoint/natural formulation with tip loads and dead aerodynamic loads;
it does not establish this current source model's root-motion impedance.
Keep aerodynamic feedback separate during that comparison, then connect its
result back to the complete coupled response. Bode agreement remains open.

The subsequent [current wing/brace comparison](daedalus-wing-root-20261114.md)
now performs that check on 14/28/56 intervals. Its independent continuum
equilibrium and root-motion response show decreasing errors, with finest
maximum motion/reaction errors 1.107%/1.296%. Four of twelve cases remain above
the stricter 1% component target. For the supplied complex root trace at the
dip, the conditional yaw-reaction error is 0.052% and phase difference 0.00196°.
No production correction or complete-aircraft Bode validation follows.
