# Daedalus: full-descriptor cancellation zeros and mounting-path sensitivity

The current rudder-to-yaw response has a verified cancellation zero at
**−2.868194 + 7.418277i s⁻¹**, with imaginary frequency **1.180655 Hz**.
The corresponding selected roll zero is **+1.045600 + 9.076432i s⁻¹**, or
**1.444559 Hz**. Separate full-system solves reproduce zero output within
**1.914e−12 deg/s/F3**. These are current-model results; the published
magnitude-only drawing does not establish native ASWING zero locations.

The **2.5 ft boom span between the wing and fairing attachments** dominates
the tested stiffness sensitivity of these zeros. Its yaw-bending stiffness
has **52.25 times** the local effect on the yaw zero's real part as the aft
boom's. The wing's ordinary-lift term is the largest tested aerodynamic
contribution to that real-part sensitivity. This sharpens the coupling to
investigate; it supplies no justification for changing literal stiffness or
lift coefficients to fit the drawing.

The sinusoidal Bode discrepancy is unchanged: **0.074218 versus 0.033986
deg/s/F3** at 1.157378 Hz. No production correction or new reference pass
follows from this study.

![Verified zeros and conditional sensitivities](../../artifacts/daedalus-transmission-zeros-20261114/report/transmission-zeros.png)

## Definition, references and search

The [authoritative reference index](aswing-authoritative-references.md) and
[source catalog](aswing-authoritative-sources.json) were consulted. Drela's
[unsteady description](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf),
printed pp. 26–27, Eqs. 131–136, supplies

`(s*M-A)*z = B*u`, with body-rate output `y = C*z`.

For these outputs there is no direct control or state-rate term in the output
map. Setting `y=0` yields the augmented generalized eigenproblem

```text
[ A   B ] [z]       [ M  0 ] [z]
[-C   0 ] [u] = s * [ 0  0 ] [u].
```

The accepted literal `dae.asw`, 6.7 m/s, Mach 0.1, source-equation/SEGSPL
model is unchanged. The prior exact elimination of three Earth positions and
heading rate reduces 2,044 coordinates to 2,040 before the query. The new
forcing coordinate makes the augmented dimension 2,041. No elastic or
circulation mode is truncated.

Both eight-candidate queries use the predetermined shift
`−0.1 + i*2*pi*1.15737773741517`. Real Arnoldi acts on the real part of the
complex shifted inverse. Its eigenvalues are recovered from the original
augmented pencil and checked there. A scalar Schur complement enforces the
output constraint using the existing exact beam elimination. Direct
factorization of the augmented matrix exceeded the host's allocation limit;
the structured method succeeds with the same 512 MiB address-space cap.

The two zeros discussed here are the closest returned candidates to the query
shift, each with substantial forcing coordinate. All candidates remain in the
saved results. Neither the query nor the figure proves completeness of the
finite zero spectrum or excludes additional nearly cancelled poles/zeros.

## Direct verification and interpretation

Each selected candidate receives a separate complete **2,044-coordinate**
solve at its complex `s`. Moving `Re(s)*M` into a real `A` matrix permits use
of the production harmonic solver with all its conditioning and full-equation
checks intact. The removed cyclic coordinates are also recovered independently
from the query vector before comparison.

| Check | Yaw zero | Roll zero |
| --- | ---: | ---: |
| Real part, s⁻¹ | −2.868194 | +1.045600 |
| Imaginary frequency, Hz | 1.180655 | 1.444559 |
| Target output magnitude, deg/s/F3 | 1.913e−12 | 1.793e−13 |
| Complete state difference from augmented query | 2.063e−12 | 1.127e−12 |
| Full-pencil reciprocal-condition estimate | 1.151e−8 | 2.285e−8 |
| Smaller-width relative transfer-derivative error | 6.717e−8 | 1.051e−8 |

Four additional direct solves per zero check its analytic transfer derivative
at two centered widths. The expected fourfold reduction in error is observed.
The original full-equation residual checks pass in all ten direct solves.
Two-width nonlinear load evaluations also close the network rows within
**1.448e−11** scaled units and the net physical wrench within **1.168e−9**
in its respective force/moment units.

A transmission zero describes cancellation for an input proportional to
`exp(s*t)`. It is **not a natural eigenmode** or an actual sinusoidal input at
`Im(s)/(2*pi)`. The roll zero's positive real part is a nonminimum-phase
input/output property, not evidence of an unstable aircraft pole. The distance
from the imaginary axis helps characterize a notch, but its depth also depends
on the other zeros, poles and gain. The current yaw-zero frequency being near
the drawing's dip therefore does not validate its damping or recover the
historical operating point.

## What moves the cancellations

For the transpose adjoint `K.T*l=C.T`, the zero derivative is

`ds/d(epsilon) = l.T*delta_R(z,s*z,u)/(l.T*M*z)`.

The load multipliers preserve the accepted base through an affine offset and
include the corresponding input derivative. They are not aerodynamic material
coefficients, retrimmed aircraft changes or additive damping fractions.

Selected changes in the **yaw zero** for a +1% incremental-load multiplier:

| Component | Real-part change, s⁻¹ | Imaginary-frequency change, Hz |
| --- | ---: | ---: |
| Wing ordinary circulation lift | −0.095533 | +0.0081435 |
| Wing apparent loads | +0.028594 | +0.0014306 |
| Wing circulation-rate lift | +0.021010 | −0.0071513 |
| Wing circulation lag | −0.004515 | +0.0093625 |
| Fin ordinary circulation lift | −0.000137 | −0.0000719 |

Thus the zero-location sensitivity differs from the previously studied
[natural-mode decay sensitivity](daedalus-modal-loads-20261114.md), where
ordinary fin lift strongly influences the boom-dominated pole. A strong
effect on a pole is not necessarily a strong effect on a zero.

The structural check independently forms stiffness derivatives from the
published beam compatibility equations. For this file, the material law has
zero cross-coupling and axis offsets. Scaling one finite stiffness by
`1+epsilon` changes its compliance by `1/(1+epsilon)`, giving exactly
`A(epsilon)=A+epsilon/(1+epsilon)*D` at the fixed base. Node-frame changes
acting on the loaded internal moments are included in `D`.

Local changes per **+1% stiffness**, in the zero's real part:

| Region/property | Yaw zero, s⁻¹ | Roll zero, s⁻¹ |
| --- | ---: | ---: |
| Wing–fairing boom span, t=0…2.5, EInn | +0.030234 | +0.017851 |
| Nose boom, t=−6.5…0, EInn | −0.00000116 | −0.00000108 |
| Aft boom, t=2.5…20, EInn | −0.000579 | −0.001721 |
| Wing torsion, GJ | +0.002469 | +0.012023 |
| Wing bending, EIcc | −0.004903 | +0.002918 |

At the current zeros, the mounting-span change moves yaw's zero toward the
imaginary axis and roll's away from it. This is consistent with the opposite
notch-depth discrepancies, but it does not predict a corrected full Bode
curve or establish a wrong stiffness. All declared derivatives remain local.

Four small perturbations each of **forward-boom and aft-boom EInn**, for both
zeros, give **16 fresh transfer zeros**. These use ±0.1% and ±0.05%, exact
compliance scaling and the unchanged full-pencil conditioning gates. The
maximum normalized centered-derivative error decreases from **4.373e−6** to
**1.092e−6** on step halving. Forward-boom derivatives include the nose and
mounting span; a separately checked exact matrix partition identifies the
negligible nose contribution above. No tolerance was relaxed.

The aft boom still contains **65.99% / 72.41%** of the yaw/roll zero states'
positive material-strain quadratic. This excludes brace, geometric/prestress,
fluid and kinetic terms. It is not total energy or a modal participation
fraction. Large visible aft-boom deformation and strong sensitivity to the
short mounting span can coexist in a coupled system.

## Literal input check and documentation correction

The short mounting span's `EIcc` and `EInn` vary linearly from **80,952.38 to
92,857.14 lb ft²**; `GJ` is **25,000 lb ft²**. Direct interpolation of the
literal table agrees with the parser and saved full-model endpoint fixture.
The earlier [mounting-path note](daedalus-wing-mount-20261113.md) incorrectly
summarized bending stiffness as a constant 100,000; that Markdown table is now
corrected. Its numerical artifacts already contained the varying values.
This correction changes neither the model nor any solved response.

The earlier mounting-path, inertia and independent compatibility checks remain
valid within their disclosed scope. A new stiffness sensitivity is not evidence
that their literal-file mechanics were wrong. The unresolved issue is how this
wing/mounting-path feedback compares with the unknown historical ASWING setup
and its aerodynamic coupling.

## Evidence and execution

- [Combined results](../../artifacts/daedalus-transmission-zeros-20261114/report/result.json),
  [stiffness CSV](../../artifacts/daedalus-transmission-zeros-20261114/report/stiffness.csv),
  [load sensitivity CSV](../../artifacts/daedalus-transmission-zeros-20261114/report/load-sensitivities.csv),
  [SVG plot](../../artifacts/daedalus-transmission-zeros-20261114/report/transmission-zeros.svg).
- [Yaw verification](../../artifacts/daedalus-transmission-zeros-20261114/yaw-verify/result.json),
  [roll verification](../../artifacts/daedalus-transmission-zeros-20261114/roll-verify/result.json),
  [literal mounting values](../../artifacts/daedalus-transmission-zeros-20261114/literal-mount/result.json).
- [Zero driver](../../scripts/check_daedalus_transmission_zeros.py),
  [stiffness driver](../../scripts/check_daedalus_zero_stiffness.py),
  [report generator](../../scripts/report_daedalus_transmission_zeros.py).

Fifteen serial jobs are terminal and reaped: **12 successful and three retained
allocation failures**. The failures all occur in direct augmented sparse
factorization, including its real initialization; changing only the Arnoldi
arithmetic did not fix that. Exact existing beam elimination plus the scalar
output Schur complement does. The successful method retains all matrix
entries and original-equation checks.

Every child used one BLAS thread, 512 MiB address space, 15 CPU seconds and
25 wall seconds. The figure was visually inspected. Production code, literal
inputs, source catalog, ISAE fractions and progress history are unchanged.
Browser/build jobs remain held. The previous goal turn added the
[axis-invariant reference check](daedalus-reference-kinematics-20261114.md);
this turn adds verified current-model zeros and a more specific mechanical
coupling to investigate, without claiming Bode agreement.
