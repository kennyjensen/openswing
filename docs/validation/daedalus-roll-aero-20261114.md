# Daedalus: aerodynamic refinement at the roll cancellation

At **1.5 Hz**, refining only the lifting aerodynamic mesh gives roll-amplitude
first variations of **−5.474% for 164 panels** and **−6.489% for 328 panels**,
relative to the original 82-panel aircraft. The wing supplies the dominant
load correction. This is appreciable, but smaller than the **−15.915% actual
amplitude change** from refining the complete aircraft and retrimming it.
The remaining difference cannot yet be assigned solely to the structure:
changed aerodynamic feedback beyond first order and retrim are still mixed in.

Yaw-amplitude first variations are **+0.623% / +0.703%** at this frequency.
Together with the earlier [dip-frequency calculation](daedalus-aero-feedback-20261113.md),
this does not support aerodynamic panel resolution as the explanation for
the much deeper published yaw dip. Native ASWING agreement remains open.

![First-order aerodynamic changes versus the full mesh change](../../artifacts/daedalus-roll-aero-20261114/report/roll-aero-refinement.png)

## What is held fixed

The accepted literal `dae.asw` case remains at **6.7 m/s**, with the same
physical properties, loaded structure, frame attitude, control settings,
live vortex influence, circulation lag and propeller plume. The original
108-node, 2,044-coordinate descriptor supplies its saved 1.5 Hz state.
The full descriptor equation is checked again before reusing that state.

Only lifting aerodynamic intervals are subdivided, at the same whole-beam
Glauert-angle sampling used in the
[earlier resolution check](daedalus-aero-resolution-20261113.md).
All grids sample the original position, rotation and local-motion
interpolants. Body panels and point attachments remain unchanged. The existing
spacing-dependent vortex-core rule is used without changing its parameter.
Accepted steady circulation is verified on each grid; the oscillatory
circulation is solved anew at 1.5 Hz with that prescribed aircraft motion.

The [authoritative index](aswing-authoritative-references.md) and its source
catalog were consulted. The sampling and vortex system follow the steady
description's Eqs. 150–161; circulation lag and unsteady loads follow the
unsteady description's Eqs. 33–49. Its Eqs. 135–136 define the frequency-domain
state and output equations. The fixed-shape refinement is a diagnostic use of
those equations, not a claim that ASWING normally uses an independent fine
aerodynamic mesh on coarse structural intervals.

## Loads and coupled first variation

Fine-strip forces and intrinsic moments are summed about each original
interval's receiver, including their moving moment arms. The existing
symmetric endpoint transfer then applies the wrench to the original
structural equations. Point, body-shoulder and engine loads use their actual
moving attachment positions. Both nodal equations and global force/moment
rows are included; total force and moment are conserved.

With `K0 = i*omega*M0 - A0`, the complete original aircraft response satisfies
`K0*z0 = B0`. Let `dL` be the fine-minus-coarse load derivative at that motion
and input, after fine circulation has been eliminated. The calculation is

```text
K0 * dz = dL
dH = C * dz
amplitude first variation / baseline amplitude = real(dH / H0)
```

These are derivatives at zero of an affine interpolation between the coarse
and fine aerodynamic operators. The complete original aircraft inverse retains
its coupled structural and aerodynamic response. A constant residual offset
implicitly holds the original equilibrium, since the fine mean aerodynamic
loads differ. No physical preload or fitted parameter is proposed.

Higher orders of the changed aerodynamic feedback and structural retrim are
omitted. In particular, `H0+dH` is not a new fully recoupled fine-grid Bode
solution. The first variations cannot be subtracted from the full-mesh result
to produce an exact structural contribution.

## Results

All percentages below use the original amplitude as denominator. The first
two columns are amplitude derivatives; the last is an actual amplitude change
from the existing 211-node / 164-panel, independently trimmed aircraft.

| Output | Aero 82→164: first variation | Aero 82→328: first variation | Whole mesh + retrim: actual change |
| --- | ---: | ---: | ---: |
| Yaw rate | +0.6228% | +0.7027% | +0.1056% |
| Roll rate | −5.4740% | −6.4894% | −15.9151% |
| Sideslip | +0.3314% | +0.3693% | −0.2580% |
| Bank | −4.4987% | −5.7905% | −13.6354% |

Original amplitudes are **0.09431625 deg/s/F3** yaw,
**0.01145170 deg/s/F3** roll, **0.02435373 deg/F3** sideslip and
**0.001122757 deg/F3** bank. The roll first variations' complex magnitudes
are **5.7197% / 6.6061%**, with phase first variations **−0.9502° / −0.7083°**.
The first-order roll change projects **34.87% / 40.40%** onto the observed
complex whole-mesh change. These projections are diagnostic scalars, not
independent fractions of the physical causes.

For consistency with this table, the whole-mesh **complex** roll change is
**16.3476% of the original amplitude**. The preceding
[zero analysis](daedalus-mesh-zeros-20261114.md) reported **19.4418% of the
refined amplitude**. These are the same complex difference with different
denominators; neither is the −15.9151% signed amplitude change.

| Load group | 164-panel roll first variation, percentage points | 328-panel roll first variation, percentage points |
| --- | ---: | ---: |
| Wing | −5.77250 | −7.25049 |
| Stabilizer | +0.03405 | +0.43630 |
| Fin | +0.22811 | +0.33060 |
| Boom | +0.00010 | +0.00011 |
| Fairing | +0.03639 | −0.00565 |
| Points, shoulders and engines | −0.00014 | −0.00025 |

The relatively small net difference between 164 and 328 panels is not a
convergence proof. Individual wing and stabilizer corrections still change.
The [CSV](../../artifacts/daedalus-roll-aero-20261114/report/comparison.csv)
and [component CSV](../../artifacts/daedalus-roll-aero-20261114/report/roll-components.csv)
retain the complete values.

## Verification and execution

| Check | Largest observed difference or residual |
| --- | ---: |
| Reused full 2,044-coordinate state | 2.636e−17 |
| Steady circulation on the three grids | 7.816e−11 |
| Fresh analytic circulation Jacobian / lag versus saved matrices | exactly zero |
| Independent circulation-Jacobian directional probe | 3.649e−11 |
| Harmonic circulation equations | 3.436e−16 |
| 82-panel harmonic circulation versus saved full state | 9.193e−10 relative |
| 17 coarse load transfers versus native network evaluations | 5.552e−17 in scaled residual units |
| Total force/moment transfer closure | 1.490e−12 in the relevant physical units |
| Motion-source stencil change when width is halved | 1.283e−9 |
| Complete load-derivative stencil change | 5.856e−14 in scaled residual units |
| Corresponding wrench stencil change | 2.744e−9 |
| Complete perturbed circulation derivative | 1.455e−11 |
| Full descriptor correction-solve scaled residual | 8.069e−20 |
| Sum of component corrections versus separate total solve | 2.333e−16 in scaled state units |

The unchanged gates are 1e−10 for solved circulation, 2e−8 for motion-source
and scaled load derivatives, and 2e−6 for wrench derivatives. Both fourth-order
stencil widths, **1e−3 and 5e−4**, are retained. The report also verifies exact
replay of all three steady mean wrenches from the earlier dip-frequency study;
frequency has not accidentally changed the baseline geometry or loads.

There are **20 terminal jobs: 17 successful and three unsuccessful**, all
reaped. `shape-1` exposed a diagnostic list/array conversion error, corrected
in `shape-1-v2`. `shape-4` and `shape-4-real` reached the 25-second wall cap
and were killed and reaped. Their evidence is retained. Subsequent fine-grid
stencils were divided by real/imaginary direction and stencil width, then
combined and checked before projection. No limit was increased.

Every numerical job uses one BLAS thread, **512 MiB address space,
15 CPU seconds and 25 wall seconds**. Successful jobs used at most
**5.579 CPU seconds, 20.010 wall seconds and 165.50 MiB resident memory**.
The largest failed job used 175.25 MiB resident memory. Parent sessions are
closed; there are no background jobs from this study. Browser/build work
remains held. Production physics, the `.asw` file and ISAE fractions are
unchanged; this adds no native-reference passes or progress event.

Use [the bounded calculation driver](../../scripts/check_daedalus_roll_aero.py)
and [report driver](../../scripts/report_daedalus_roll_aero.py), one fresh tag
at a time. Each folder contains its archived runner, hashed input plan and
terminal receipt. Accepted circulation results are `shape-1-v2`, `shape-2`
and `shape-4-joined`; accepted loads are `loads-1`, `loads-2` and `loads-4`.
The [projection](../../artifacts/daedalus-roll-aero-20261114/project/result.json),
[report](../../artifacts/daedalus-roll-aero-20261114/report/result.json) and
[verification receipt](../../artifacts/daedalus-roll-aero-20261114/verification.json)
provide the numerical evidence.

Next, close the higher-order aerodynamic-feedback qualification at 164 panels
while holding this same structural equilibrium fixed. That establishes whether
the remaining roll mesh difference should be pursued mainly through structural
discretization and retrim. It does not replace the separate effort to match
the published yaw curve.
