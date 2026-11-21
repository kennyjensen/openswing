# SA-11 finite-chord control: isolate wake direction

2026-11-07. Rotating only the trailing wake into the freestream removes the
negative drag in the preceding independent finite-chord controls. It does not
resolve their large local velocities or establish force convergence. The
upper/lower two-row integrated coefficients become substantially steadier,
but body-edge peak speed still doubles under span refinement, and additional
chordwise resolution changes drag by about 20.6% on the coarse grid.

All ten numerical solutions and their diagnostic fields are retained. This
changes no production equations, defaults, example inputs or validation scope.
SA-11 remains **163/4,592 at 5%**; the new results are not ASWING-reference passes.

The subsequent [force-quadrature audit](isae-sa11-force-quadrature-20261107.md)
shows that this control's all-edge force integrals have nonzero logarithmic
endpoint terms. It also identifies two exact interior wake/body crossings
in the upper/lower geometry. Thus the positive drag reported here is not
evidence that ordinary integration can converge this particular force model.

## Controlled change

The [previous study](isae-sa11-finite-chord-20261107.md) supplies the complete
geometry, original section normals, frozen PG map, body-force coefficient
ledger and force probes. Every one of those arrays is unchanged here. The
sole physical change is the direction of the semi-infinite trailing rays:
from the x axis to the freestream direction at 5 degrees angle of attack.
Circulation is then solved again under the same linear tangency law.

This is **not the complete ASWING K/F-off operation**. The bound geometry and
PG transform remain frozen deliberately. ASWING's wind-dependent lifting
geometry is described in equations 155–157 and its frozen approximation in
section 4.6 of the [steady technical description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf).
The earlier [production current-wind comparisons](isae-sa11-winglet-junction-20261107.md)
remain separate observations.

The original 30 m/s, alpha 5 degrees, density, reference quantities, 1/2/4
chord rows at N48 and 1/2 rows at N96 remain fixed. The control still omits
stall, profile drag and section moment and retains the quarter-panel rear
extension of the reference ring geometry. All qualifications of the previous
finite-chord study remain applicable.

The wake starts at each ring lattice's original rear edge. This differs from
rotating a lifting-line horseshoe leg directly at its quarter-chord origin.
The finite chordwise body vortices ahead of those rear edges remain fixed.
Thus a small change in quarter-chord velocity does not imply that a full
ASWING wake/geometry update would also have a small effect.

## Reuse of the influence matrix

The new matrix is the saved matrix plus the exact normal-projected difference
between the two ray fields. All finite-vortex influence is reused. The
retained zero-core kernels evaluate directions and coordinates in the same
PG-transformed space.

The preceding collinear subdivision had represented some x-aligned rays by
finite pieces and a shared downstream origin. Those artificial subdivision
pieces must not rotate as body geometry. This study restores the rays' original
rear-edge origins, keeps the exact finite body-edge subdivision, and rotates
only the rays. Every source's finite-vertex circulation balance remains exactly
zero. Reconstructing the original frozen-wake field from that representation
agrees within **3.42e−12 m/s**.

An independently assembled complete ring influence checks representative
matrix rows and all their source columns; the maximum matrix difference is
**1.82e−12**. A separate all-control-point field reconstruction verifies each
solved residual. No geometry displacement, coordinate-merging tolerance,
finite core or changed self-velocity rule is introduced.

## Solved results

Speeds below are divided by freestream. Coefficients use the independent full
finite-body-edge force rule, rather than ASWING's single-bound-line force law.

| Model | Intervals/beam | Chord rows | Quarter-chord peak | Body-edge peak | Full-edge CL | Full-edge CD |
|---|---:|---:|---:|---:|---:|---:|
| Upper | 48 | 1 | 40.595 | 20.252 | 0.645259 | 0.011784 |
| Upper | 48 | 2 | 1.583 | 27.787 | 0.670334 | 0.015651 |
| Upper | 48 | 4 | 1.168 | 48.378 | 0.646357 | 0.016379 |
| Upper | 96 | 1 | 160.956 | 80.390 | 0.646006 | 0.012119 |
| Upper | 96 | 2 | 2.518 | 106.646 | 0.726225 | 0.020571 |
| Upper/lower | 48 | 1 | 171.876 | 303.151 | 3.636780 | 0.287640 |
| Upper/lower | 48 | 2 | 23.492 | 49.134 | 0.737882 | 0.021448 |
| Upper/lower | 48 | 4 | 23.058 | 123.441 | 0.750172 | 0.025873 |
| Upper/lower | 96 | 1 | 354.724 | 558.723 | 4.885896 | 0.396553 |
| Upper/lower | 96 | 2 | 18.372 | 98.671 | 0.746885 | 0.021405 |

All drag values are now positive. In particular, upper/lower with two rows
changes from the prior frozen values −0.010083/−0.006828 to
+0.021448/+0.021405 on N48/N96. This isolates wake direction as a cause of
that negative-drag symptom in this independent model. Positivity alone is
not proof of physical accuracy.

For upper/lower with two rows, N48→N96 changes CL by **+1.220%** and CD by
**−0.200%**. However, the body-edge peak grows **+100.821%**. Its quarter-chord
normal Mach is approximately **2.062** and **1.460**, outside the subsonic
model's domain. At N48, changing from two to four rows changes CD by about
**+20.6%**. These are not validated results despite the favorable two-grid
integrated coefficient differences.

The upper-only two-row result remains sensitive: span refinement changes CL
by **+8.338%**, CD by **+31.438%**, and body-edge peak speed by **+283.791%**.
No mesh-converged solution or production replacement is established for either
configuration.

![Wake-direction comparison](../../artifacts/isae/sa11-wake-direction-20261107-review/wake-direction-comparison.png)

## Fixed-circulation fields and location of the remaining peaks

Ten additional evaluations keep the previous finite-chord circulation fixed
while changing wake direction. These are deliberately unsolved states. The
held circulation is the previous *finite-chord* solution, not the original
nonlinear OpenSwing circulation. Their boundary residuals are retained.

Changing the wake at fixed circulation barely changes the largest
quarter-chord speeds in the sampled cases. For example, upper/lower N48 with
two rows changes from 24.16715 to 24.16789 times freestream before circulation
adjusts. The solved result is 23.49245. This is consistent with the component
decomposition: that solved peak has finite-body-induced speed 23.5661 and
wake-induced speed only 0.00109, both normalized by freestream. These vector
magnitudes do not add directly to the total.

There is also a different failure mechanism. Upper-only N48 with four rows
has a body-edge peak of 48.378 times freestream. At that point the finite-body
contribution has magnitude 0.1305, while the wake contribution is 48.4985.
The dominant trailing leg passes only **0.2077 mm** from the probe, which lies
downstream of its origin. Wake alignment introduces a close wake/body
encounter there. It cannot be assumed to reduce every local peak.

Both mechanisms are present: large fields near the sharp root body vortices,
and close interactions between a departing wake and another body edge. A
single integrated coefficient or a selected smooth probe cannot certify the
velocity field used for forces.

## Verification and remaining work

All ten solves pass the declared numerical residual gates. Independent
compensated scalar residuals are at most **1.60e−12** for unit freestream.
All unit-source fields at three off-sheet probes agree with complete ring
formulas within **4.61e−15** in influence units. The analysis verifies the
unchanged arrays, held circulation, exact matrix increment, force and moment
sums, peak decompositions, source hashes and all 143 production/status/scope
pins. These checks establish the numerical comparison, not physical validity.

The linear solves total 0.354 s; recorded numerical stages including fields,
loads and saving total 32.44 s, excluding startup and the later audit. Four
foreground batches contain at most three serial solves each, with one BLAS
thread and the same 60-second/768 MiB limits as before. No background solver
workers or production changes are introduced.

The result separates wake alignment from local force evaluation. Further work
must resolve the near-root force treatment and distinguish local singular
fields from errors in integrated load quadrature. The finite-chord controls
remain diagnostic evidence, not replacement reference data. No native ASWING
operating point or undocumented junction rule has been recovered.

Reproduce each batch using a fresh directory:

```sh
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 timeout 60s prlimit --as=805306368 .venv/bin/python scripts/verify-sa11-wake-direction.py --baseline artifacts/isae/sa11-finite-chord-20261107-up48-canonical --output artifacts/isae/sa11-wake-direction-new-up48
```

Repeat sequentially for the retained `up96`, `both48` and `both96` finite-chord
baseline directories. Analyze their four output directories with
`scripts/analyze-sa11-wake-direction.py --batches ... --output ...`, under the
same limits. The analysis performs no new circulation solves.

- [Upper N48 results](../../artifacts/isae/sa11-wake-direction-20261107-up48/results.json)
- [Upper N96 results](../../artifacts/isae/sa11-wake-direction-20261107-up96/results.json)
- [Upper/lower N48 results](../../artifacts/isae/sa11-wake-direction-20261107-both48/results.json)
- [Upper/lower N96 results](../../artifacts/isae/sa11-wake-direction-20261107-both96/results.json)
- [Independent audit and field decompositions](../../artifacts/isae/sa11-wake-direction-20261107-review/analysis.json)
- [Plot as SVG](../../artifacts/isae/sa11-wake-direction-20261107-review/wake-direction-comparison.svg)
