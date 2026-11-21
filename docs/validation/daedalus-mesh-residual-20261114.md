# Daedalus: exact equation accounting for the mesh response change

The saved coarse and refined aircraft responses now have an exact residual
accounting at **1.5 Hz**, for yaw, roll, sideslip and bank. The maximum closure
error is **3.745e−16** in the respective output units. This localizes which
equations reject a carefully mapped coarse motion, without another aircraft
assembly or a fitted parameter.

Wing position compatibility is a useful lead, but its apparent contribution
depends on the interpolation at newly inserted nodes. Its signed projection
onto the net complex roll change is **34.39%** with rigid-section transport,
**39.44%** with direct material interpolation, and **14.16%** after completing
the attainable inserted-node position constraints. The completion leaves all
108 retained-node motions unchanged. The last result prevents treating the
initial 34–39% as an isolated physical cause.

All percentages here account for the difference between **two OpenSwing
meshes**. Native ASWING agreement remains unresolved, and no production
physics or ISAE fraction changed.

![Equation accounts for three motion mappings](../../artifacts/daedalus-mesh-residual-20261114/report/mesh-residual-accounting.png)

## Comparison and identity

The original 108-node / 82-panel aircraft and refined 211-node / 164-panel
aircraft retain the same literal `dae.asw` and 6.7 m/s flight speed, but have
separate steady trims. Their full descriptors have 2,044 and 3,980 coordinates.
The [previous mesh study](daedalus-mesh-zeros-20261114.md) supplies both saved
responses. The [aerodynamic recoupling check](daedalus-aero-recoupling-20261114.md)
already closed the repeated-feedback qualification of the fixed-equilibrium
aerodynamic-only comparison.

Let `zmap` be a stated mapping of the coarse response into the fine state,
and `Kf*zf = Bf` the fine harmonic equations. For each fine output row `Cf`,
solve the full adjoint equation and form

```text
Kf^H * lambda = Cf^H
rmap = Kf*zmap - Bf
Hfine - Hcoarse = -lambda^H*rmap + (Cf*zmap - Hcoarse)
```

Partitioning the residual rows gives an exact sum of complex output
contributions. The last term is the output-conversion change. No residual
rows are omitted; the plots omit only numerical remainder bars, retained in
the CSV. Exact beam/velocity elimination factors 1,448 equations and recovers
the complete fine adjoint. The full-pencil condition estimate is **7.300603e−9**.

For each contribution `h`, the displayed percentage is
`100*real(h*conj(Hfine-Hcoarse))/abs(Hfine-Hcoarse)^2`. These signed projections
sum to 100%; cancellation can make individual values negative or above 100%.
They are not signed amplitude changes or unique fractions of physical causes.
At this frequency, the whole-mesh complex roll change is **16.3476% of the
original amplitude**, while its signed amplitude change is **−15.9151%**.

## Motion mappings and checks

All original material stations and attachments are retained in the refined
mesh. At inserted stations, position increments initially use the coarse
linear centerline interpolant, and spatial rotation increments use the exact
tangent of its SO(3) rotation arc. An independent call through the native
motion sampler agrees within **6.939e−18**. Zero beam-axis offsets are checked
before using this position mapping.

The primary mapping transports that section motion to the actual fine mean
position: `dr_f = dr_sample + dtheta_sample cross (r_f-r_sample)`.
It preserves a uniform rigid rotation about the fine mean geometry, with
maximum patch error **4.236e−22 ft**. The maximum mean-position transport is
**0.073914 ft**. Direct material interpolation is retained as an explicit
alternative; it preserves the original displacement increments but does not
apply this change of section origin.

The fine frame-acceleration, Earth-position and Euler-angle equations are
then solved with the mapped frame velocity and rate. Local velocities satisfy
the fine position/rate definitions. Fine circulation is solved on the actual
fine equilibrium. The remaining residual therefore lies in the beam/joint
and global force/moment equations, up to numerical error. The primary mapping
also satisfies fine rigid-joint constraints within **1.624e−15**.

Internal forces and moments initially repeat their parent coarse-interval
values; joint reactions retain the coarse values. A second mapping replaces
these with the already computed **fine OpenSwing solution's** values. The
archived case name `objective-reference` refers to that fine solution, not
native ASWING. The broad position/remaining-structure/global accounts change
by at most **2.491e−17** in output units. Detailed force-versus-moment or
individual-beam accounts do change, so those subdivisions must not be read
as unique causal partitions.

## Inserted-node compatibility completion

The [authoritative reference index](aswing-authoritative-references.md) and
checksummed catalog govern this comparison. The steady description's **Eq. 48,
PDF page 12**, relates endpoint position differences to the average endpoint
section frames and strain. Its implementation is in
[source_discrete.py](../../openswing/source_discrete.py). The unsteady
description's Eqs. 135–136 define the harmonic equations used above.

For this literal aircraft, the position rows have **zero dependence on
internal-force/reaction variables**. At each inserted node, six position rows
from its two adjacent fine intervals act on six node-pose increments. Their
physical rank is five: three translations and two bending rotations can
remove five residual directions; the torsional null component stays fixed.
One compatibility direction remains when both retained endpoint motions are
held fixed.

An SVD of every local block identifies those five directions. A least-squares
correction minimizes the local position defect using only the inserted-node
pose, then the fine kinematic and circulation equations are completed again.
The fine matrices, inputs, saved solution and physical parameters remain
unchanged. This constructs another trial mapping; it is not a modified
aircraft solution or a proposed solver correction.

All **103 inserted nodes** are completed. Maximum changes from the transported
mapping are **0.00018834 ft** in translation and **1.188e−6 rad** in rotation.
Every retained-node pose remains bitwise identical. The maximum condition
number of a retained five-direction local block is **8,593.1**.

## Roll account and next investigation

| Equation group | Rigid-section transport | Material interpolation | Inserted-node completion |
| --- | ---: | ---: | ---: |
| Wing position compatibility | +34.388% | +39.437% | +14.165% |
| Other position compatibility | +0.070% | +0.041% | +0.002% |
| Remaining beam/joint equations | +117.393% | +109.591% | +120.699% |
| Global force balance | −2.327% | −2.053% | −0.812% |
| Global moment balance | −49.524% | −47.015% | −34.054% |
| Output conversion | 0% | 0% | 0% |

The beam force/moment rows contain aerodynamic, inertial and gravity loads.
Thus “remaining beam/joint equations” is an equation grouping, **not a purely
structural-physics contribution**. Both the changed equilibrium and the
changed discretization enter these matrices. The identity has not separated
those two causes.

After inserted-node completion, the largest individual wing position accounts
are the material-coordinate intervals **−21.4303…−14** and **14…21.4303**,
centered near loaded span positions **−17.73 and +17.73 ft**. They contribute
**3.929% and 3.892%** of the net complex roll change. This gives a concrete
location for the next Eq. 48 audit: separate the effects of changed mean
section rotations from subdivision within these inboard wing intervals.
The accounting does not yet establish a production bug, mesh convergence,
or a resolution of the published yaw discrepancy.

All four outputs and all row groups are in the
[broad CSV](../../artifacts/daedalus-mesh-residual-20261114/report/broad-accounting.csv),
[detailed CSV](../../artifacts/daedalus-mesh-residual-20261114/report/row-accounting.csv)
and [spanwise CSV](../../artifacts/daedalus-mesh-residual-20261114/report/wing-position-accounting.csv).
The bank output-conversion contribution reproduces the earlier signed
projection of **−2.3332%** onto its net complex mesh change. The raw projection
uses the same saved full-pencil adjoints and exactly replays all original
three-map accounts before evaluating the fourth map.

## Execution and evidence

There are **13 terminal jobs: 12 successful and one unsuccessful**, all reaped.
The first inserted-node completion used an overly strict **1e−12** relative
cutoff for identifying a zero singular value. The retained
[rank audit](../../artifacts/daedalus-mesh-residual-20261114/rank-probe/result.json)
finds a maximum sixth singular-value ratio of **1.866e−12**, while the fifth
ratio is at least **1.164e−4**. A **1e−10** cutoff therefore cleanly selects the
five physical directions. This changes only the diagnostic mapping's numerical
rank identification. The aircraft matrices and response/residual acceptance
gates are unchanged. The unsuccessful folder is preserved.

Each numerical child uses one BLAS thread and limits of **512 MiB address
space, 15 CPU seconds and 25 wall seconds**. Maximum recorded use is
**3.484 CPU seconds, 12.338 wall seconds and 215.305 MiB resident memory**.
All parent sessions are closed. Browser/build work remains held. ISAE fractions
and progress scopes are unchanged, so no progress event is added.

The [calculation driver](../../scripts/check_daedalus_mesh_residual.py) and
[report driver](../../scripts/report_daedalus_mesh_residual.py) retain input
hashes, runner snapshots, arrays and terminal receipts. The
[projection result](../../artifacts/daedalus-mesh-residual-20261114/projection/result.json),
[report](../../artifacts/daedalus-mesh-residual-20261114/report/result.json) and
[verification receipt](../../artifacts/daedalus-mesh-residual-20261114/verification.json)
contain the numerical evidence.
