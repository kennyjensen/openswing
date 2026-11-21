# Daedalus: lagged Newton influence coefficients versus dynamic derivatives

Omitting the pose derivatives of vortex and volume influence coefficients at
the loaded equilibrium changes yaw by only **-0.00773% at the published dip**.
The converged conditional result is **0.0742120 deg/s per F3**, versus
**0.0339862** in Drela's drawing. This does not explain the discrepancy, and
no production derivative or parameter was changed.

## What the sources establish

The [authoritative reference index](aswing-authoritative-references.md) and
[checksummed catalog](aswing-authoritative-sources.json) were consulted.

* The [steady description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
  section 4.6, Eq. 176 and the following discussion on printed p. 36, allows
  geometry-dependent influence coefficients to lag during Newton iteration.
  The multi-surface compromise retains circulation and freestream speed/angle
  dependence. This describes how the nonlinear solve is accelerated.
* The [unsteady extension](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf),
  section 11.3, Eq. 122 on p. 24 and section 13.1, Eqs. 130-134 on p. 26,
  defines the dynamic matrices as partial derivatives of the residual and
  states that these matrices are already available from Newton iteration.
* The [1999 integrated-model paper](https://web.mit.edu/drela/Public/web/aswing/asw_aiaa.pdf),
  printed pp. 10-11, Eqs. 30-32, similarly describes the residual derivatives
  and their reuse in frequency response. Its [retained source record](daedalus-historical-lag-sources-20261113.json)
  distinguishes this paper from the later undocumented Daedalus run.
* The manual's OPER K/F description separately freezes coefficients at the
  **undeformed, zero-wind-angle geometry**. That approximation is different
  from retaining coefficients at the **loaded equilibrium while taking a
  derivative**. The preceding [K/F study](daedalus-frozen-source-20261114.md)
  already tested the former with a fresh trim.

The statements about matrix reuse do not identify which approximate Jacobian,
if any, the historical Bode calculation used. Nor does reuse by itself require
dropping a physical derivative. The conditional calculation below measures the
consequence of one explicit interpretation; it does not authenticate an ASWING
implementation or replace the derivative definitions in Eq. 132.

## Diagnostic definition

The accepted live-influence source/SEGSPL equilibrium at 6.7 m/s and Mach 0.1
is unchanged: 108 nodes, 103 intervals, 82 circulation states and 2,044 total
coordinates. Vortex and volume coefficients are captured at this loaded
geometry. All 18 named receiver/operator combinations used by the static
residual are included: control points, lift receivers, the engine, the body
and five point weights.

Only when differentiating the first 648 pose coordinates are these captured
coefficients substituted. Local aerodynamic frames, force directions, moment
arms, relative-velocity kinematics, plume calculations and load transfer stay
live. All non-pose columns, including circulation, freestream, local velocity,
local rate and frame motion, remain those of the full original descriptor.
Engine response to the changed induced inflow remains coupled.

Let `P` select only pose coordinates and let `DeltaA` be the derivative of the
held-coefficient residual minus the original residual along `P*z`. Then:

```text
K0 = i*omega*M0 - A0
(K0 - DeltaA) * z = B0
```

The two residual evaluations are identical at the base state; the measured
base difference is exactly zero. No artificial preload or mean-load offset is
needed. The resulting derivative-omission model is still conditional; it is
not a new fully nonlinear aircraft formulation.

Fourth-order complete residual stencils evaluate `DeltaA*z` without building
a dense matrix. Each correction solves the complete original descriptor with
exact beam/velocity elimination to a 748-dimensional factor. Repeating this
correction converges the changed feedback. No structural modes are truncated
and no aircraft property, control gain or source coefficient is fitted.

## Results

Changes below are relative to the original full-derivative response, not
percent errors against ASWING.

| Frequency, cycles/s | Yaw change | Roll change | Sideslip change | Bank change |
| --- | ---: | ---: | ---: | ---: |
| 0.1 | -0.17548% | -0.26527% | -0.10936% | -0.26475% |
| 1.157378 | -0.00773% | -0.99449% | +0.16058% | -1.18246% |
| 1.5 | +0.24365% | +0.20078% | +0.19880% | +1.17027% |

| Frequency, cycles/s | Original yaw | Diagnostic yaw | Published yaw |
| --- | ---: | ---: | ---: |
| 0.1 | 0.1217626 | 0.1215490 | 0.1182382 |
| 1.157378 | 0.0742178 | 0.0742120 | 0.0339862 |
| 1.5 | 0.0943162 | 0.0945460 | 0.0818181 |

Yaw units are deg/s per native F3 unit. The yaw error at the dip remains
**+118.36%**. The [complete comparison](../../artifacts/daedalus-lagged-influence-20261114/report-v2/comparison.csv)
retains all twelve output comparisons. Published magnitudes use the existing
log-frequency/log-magnitude interpolation of the digitized drawing; no new
reference values or native passes are inferred.

The result weakens omitted influence-geometry derivatives as an explanation
for the dip. It covers this particular omission at three frequencies and
does not establish the historical dynamic Jacobian in general. Production
continues to differentiate the configured physical residual.

## Acceptance and evidence

The evaluated candidate must satisfy all three unchanged gates: maximum
scaled modified harmonic residual below 2e-11, relative residual below 2e-8,
and the next relative output correction below 2e-7. The accepted dip and roll
candidates take four corrections; the low-frequency candidate takes five.

Each accepted state is checked at stencil widths 0.0005 and 0.001. Maximum
accepted residual across both widths is **1.615e-11**. The largest difference
between the two derivative actions is **1.892e-11**, and the largest relative
difference between their next output corrections is **3.530e-9**. The first
wide check at 0.1 Hz gave 2.453e-11 and was not accepted; one additional
correction resolved that failure without relaxing a gate.

The first report assumed that 1.5 Hz was one of the earlier 65 sweep samples
and stopped on a missing-row assertion. The corrected report uses the same
original digitized curves and interpolation as the prior source comparison.
Both reporting attempts remain in the evidence; no numerical response changed.

The [bounded driver](../../scripts/check_daedalus_lagged_influence.py) retains
22 job receipts: 21 successful jobs and the initial reporting failure. The
20 numerical jobs perform 360 complete residual evaluations. Every child is
reaped, with one BLAS thread and unchanged caps of 15 CPU s, 25 wall s and
512 MiB address space. Maximum observed CPU is 2.6424 s, wall time 4.8804 s and
RSS 134.46 MiB. The [verification receipt](../../artifacts/daedalus-lagged-influence-20261114/verification.json)
checks job inputs, saved states, acceptance gates and unchanged production.

All 142 production modules match the preceding plume-fix receipt. The literal
aircraft, source catalog, ISAE fractions and comparison scopes are unchanged.
No browser or build job was run. The larger ASWING-equivalence goal and the
native Daedalus Bode comparison remain open. Next compare Figure 7's published
wing stiffness and mass distributions with the public input, preserving the
historical setup distinction identified in the [wing-paper review](daedalus-wing-paper-20261113.md).
