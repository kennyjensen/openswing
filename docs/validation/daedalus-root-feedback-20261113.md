# Daedalus: coupled response to fin-root aerodynamic feedback

The current model contains a substantial motion-to-airload feedback through
the fin attachment. Removing that feedback increases yaw at the reference dip
from **0.074218 to 0.113364 deg/s/F3**. Thus the modeled tail motion already
suppresses the yaw response; an entirely missing feedback path is not the
explanation for the shallow dip. The reference drawing remains **0.033986**,
and no production equation or physical parameter was changed.

![Coupled response and individual motion sensitivities](../../artifacts/daedalus-root-feedback-20261113/report-v2/root-feedback.png)

[Vector figure](../../artifacts/daedalus-root-feedback-20261113/report-v2/root-feedback.svg),
[all four complex outputs](../../artifacts/daedalus-root-feedback-20261113/report-v2/outputs.csv),
[machine-readable report](../../artifacts/daedalus-root-feedback-20261113/report-v2/result.json).

## What is being tested

The preceding [motion-to-load decomposition](daedalus-motion-loads-20261113.md)
held the existing motion fixed. It showed that translation and rotation of the
fin root dominate the fin's motion-induced load. Here the complete aircraft
response is recomputed after removing those specified **aerodynamic tangent
terms**. This includes the resulting change in circulation, motion and loads
everywhere in the aircraft.

The unchanged base is the literal `dae.asw` at 6.7 m/s, with SEGSPL properties,
moving influences, circulation lag, engine plume and bilateral braces. All
2,044 coordinates remain: 108 nodes, 103 elements and 82 circulation unknowns.
The fin root is beam 3 at `t=0`, rigidly connected through its one-foot offset
to beam 4 at `t=20`.

For root coordinates `q = P z`, define a rigid fin transport `T(omega) q`:

```text
node displacement = root displacement + root spatial rotation × root-to-node offset
node velocity     = i*omega * node displacement
node angular rate = i*omega * root spatial rotation
```

All other beam motions, frame coordinates and circulation coordinates in this
prescribed transport are zero. Root translations use feet and rotations use
radians. `P T = I`; transport satisfies every local velocity definition.
The fin's actual relative deformation is `z_fin - T q`.

At zero circulation perturbation, differentiate the complete aerodynamic loads
and circulation residual along each of the six transport directions. These
columns form `U(omega)`. They include moving geometry, local velocities and
accelerations, profile and apparent loads, and tangency/stall terms. Real
mass, gravity, mechanical compatibility, joints and kinematic residuals are
excluded from `U`. Consequently, circulation remains an unknown when this
feedback is removed; it is not frozen or borrowed from the original solution.

With the original full harmonic pencil `K = i*omega*M - A`, the diagnostic is

```text
[K + (1-eta) U P] z_eta = B
eta = 1: unchanged full model
eta = 0: specified fin-root aerodynamic feedback removed
```

The positive sign follows from subtracting a contribution from the physical
residual `A*z - M*zdot + B`. Translation, rotation and their combination are
removed separately. All structural stiffness, real inertia, attachment
constraints, free-frame motion, relative fin deformation and remaining
aerodynamic feedback stay intact. The accepted equilibrium is preserved as
the base of an affine diagnostic. **This is not a rigid tail, a released
joint, a retrimmed aircraft, or a proposed physical model.**

The [authoritative reference index](aswing-authoritative-references.md) and
checksummed source catalog were consulted. The source equations remain
Drela's [unsteady description](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf),
especially Eqs. 29–36 (moving-point/circulation loads), 41–44 (apparent loads),
48–56 (circulation lag), and the complete descriptor formulation. This
diagnostic uses their implemented derivatives; it is not a separate independent
implementation of the physics.

## Results

Yaw magnitudes below are degrees/second per native F3:

| Feedback retained/removed | 0.2 Hz | 1.157378 Hz |
| --- | ---: | ---: |
| Full model | 0.172164 | 0.074218 |
| Root translation feedback removed | 0.169778 | 0.085095 |
| Root rotation feedback removed | 0.203633 | 0.096603 |
| Both removed | 0.199433 | 0.113364 |

Relative to the diagnostic with both terms removed, their combined effect
reduces yaw by **13.673% at 0.2 Hz** and **34.531% at 1.157378 Hz**. The
translation effect changes sign between these two frequencies. Two samples do
not establish a resonance frequency or an entire modified Bode curve.

The derivative at the unchanged full model is `dz/deta = K^-1 U P z`.
The following values mean percent change in yaw magnitude for a **+1%**
multiplier on the named feedback, locally at `eta=1`:

| Motion contribution | 0.2 Hz | 1.157378 Hz |
| --- | ---: | ---: |
| Lateral root translation | +0.01182 | −0.24589 |
| Root roll rotation | −0.00200 | −0.01282 |
| Root yaw rotation | −0.15356 | −0.22035 |
| All six root coordinates | −0.14371 | −0.47899 |

The other three coordinates have small contributions (each below 0.000064
in this table's units). Translation and yaw rotation are the principal paths
near the dip. These local derivatives are not a prescription for changing a
feedback multiplier, and must not be extrapolated to fit the reference.

Complete baseline root-motion and attachment-wrench phasors are retained in
the [dip solve](../../artifacts/daedalus-root-feedback-20261113/dip-solve-v2/result.json)
and [0.2 Hz solve](../../artifacts/daedalus-root-feedback-20261113/slow-solve/result.json).
The wrench is the boom's force/couple on the fin, about the fin root in body
axes; it is not the aerodynamic moment about the aircraft reference point.

## Verification and limits

Each of the twelve derivative columns uses fourth-order real/imaginary
directional stencils at widths 0.001 and 0.0005: **192 directional load
evaluations**, in addition to the usual base-construction checks. The largest
width difference is **4.506e−12** in scaled residual units, below the declared
2e−8 gate. The local kinematic error is at most **1.111e−16**.

The original full matrix is solved once per frequency with the control column
and six feedback columns as simultaneous right-hand sides. A six-coordinate
matrix identity then gives the feedback-deleted responses. **Six separate
full 2,044-coordinate solves** verify these results and apply the original
conditioning and residual gates to each modified pencil. Maximum state
difference is **3.456e−13**, below the declared 2e−10 gate. The largest modified
residual is 1.527e−16; no tolerance was relaxed. The unmodified responses
reproduce the prior accepted states within 5.052e−17.

Eliminating only the circulation block from the new columns also reconstructs
the previous root-translation and root-rotation load contributions within
**1.747e−14 / 4.793e−14**. This checks the selected-motion definition and its
circulation feedback independently of the new full response calculation.

All **17 small serial jobs** are terminal and reaped: 16 succeeded and one
adapter setup attempt failed because its reusable matrix factors correctly
require immutable input arrays. The corrected attempt marks those arrays
read-only; no physical calculation or numerical gate changed. The first
figure/report is retained; the second reads its drawing ordinate directly
from the pinned digitization CSV. Every job used one BLAS thread with 512 MiB
address space, 15 CPU seconds and 25 wall seconds. Observed maxima were
4.127 CPU seconds, 10.371 wall seconds and 157.56 MiB resident memory.
The [bounded driver](../../scripts/check_daedalus_root_feedback.py) retains
per-job source snapshots, input hashes, logs and terminal receipts.

The Bode discrepancy remains **+118% at the selected drawing minimum**.
This result supports an active, frequency-dependent tail-motion feedback path;
it does not identify the historical operating point or independently establish
its correct strength. The existing source-equation, continuum-mechanics and
mesh comparisons retain their separate scopes. No ISAE fraction, production
default, browser/build verification or native-reference pass was changed.

The next useful distinction is between fin-root motion driven by fin reaction,
other tail loads and aircraft-frame motion, rather than assuming the full
root-motion phasor measures isolated boom compliance. The existing wing-load
sensitivity likewise remains relevant to the coupled cancellation. Keep those
paths separate when investigating the remaining phase/response difference.

The subsequent [boom-load reconstruction](daedalus-boom-drivers-20261113.md)
makes this distinction and identifies fin reactions as the dominant driver.
It also resolves those reactions into circulation, circulation-rate, apparent
and real-inertia/gravity loads without changing the aircraft solution.
