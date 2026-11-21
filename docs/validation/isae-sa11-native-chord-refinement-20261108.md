# SA-11: native AVL chord/span refinement retains the junction problem

2026-11-08 UTC. Six native AVL runs refine the actual upper-winglet conversion
in both chord and span at the archived 1°/240 m/s condition. With the
report-derived −4° upper twist, lift differs from archived ASWING by at most
**0.369%** and Trefftz induced drag by **1.345%**. Large local velocities
persist and increase with span refinement. Thus the earlier junction problem
is not confined to OpenSwing or the matched one-row native model.

This is a linear native reference diagnostic. It does not establish the
original ASWING producing setup, a production repair, or an accepted subsonic
solution. **SA-11 remains 163/4,592 at 5%.** No production solve or equation,
original model, Mach guard, tracked fraction or comparison scope changes.

## Why this check differs from the previous controls

The official AVL manual, **Vortex Lattice Spacing Distributions, rule 4**,
warns that span-only refinement can leave incorrect local results at dihedral
breaks and swept-wing centers. It recommends refining chordwise resolution
as well. The [matched native comparison](isae-sa11-winglet-polar-20261108.md)
used one chordwise row to reproduce ASWING's lifting-line geometry; agreement
there does not establish finite-chord convergence.
[Retained AVL manual](../../reference/avl-native-20261108/source/AVL3.52rel09032025/avl_doc-AVL350-04242025.txt:1166).

The earlier [finite-chord study](isae-sa11-finite-chord-20261107.md) used an
independent ring model and all-edge force recovery at 30 m/s. This check uses
the retained native AVL 3.52 executable and its own force law, at nonzero
archived PG Mach. Those are different reference models and conditions.

All six cases retain the supplied beam geometry, normal-to-streamwise chord
conversion, reference dimensions, physical component 1, section slope/CLAF,
and converted twist-plus-zero-lift incidence. The −4° sign is the explicit
report-derived alternative, not a change to the original +4° model. Frozen
body-x wakes and PG Mach `240/340.21` are fixed. The predeclared grid comprises
2/4/8 cosine chord rows and 64/128 total span strips: 128–1,024 vortices.

Native `CSPACER` creates its own cosine chordwise force/control locations and
applies `CLAF` through control-point displacement. The saved one-row uniform
case is retained as context, not treated as the same chord distribution.
Native cosine force points are not generally the ASWING quarter-chord receivers.

## Results

Errors are signed percentages against the archived 1° row, whose CL is
0.336959 and CDi is 0.00445428. Near-field CD below contains vortex force
only; it must not be compared directly with archived total CD, which includes
profile drag.

| Chord rows | Span strips | Vortices | CL error | CDi error | Near-field vortex CD | Peak normal Mach at native force points | Force points at/above Mach 1 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 64 | 128 | −0.369% | −1.344% | 0.00480919 | 1.22390 | 2 |
| 2 | 128 | 256 | −0.317% | −0.876% | 0.00516716 | 5.42770 | 2 |
| 4 | 64 | 256 | −0.280% | −1.045% | 0.00500095 | 2.49142 | 4 |
| 4 | 128 | 512 | −0.123% | −0.143% | 0.00531584 | 10.30082 | 6 |
| 8 | 64 | 512 | −0.320% | −1.189% | 0.00459501 | 0.83934 | 0 |
| 8 | 128 | 1,024 | −0.118% | −0.212% | 0.00517188 | 6.50257 | 8 |

The velocity diagnostic scales native normalized velocities to 240 m/s and
projects them perpendicular to the corresponding ASW beam tangent. It is
not a native AVL acceptance test or a production ASWING Mach check. Its
receiver locations move with chord and span refinement.

At each fixed chord count, doubling span resolution changes CL by
**0.052–0.202%**, CDi by **0.475–0.989%**, and near-field vortex drag by
**6.30–12.55%**. Peak normal Mach grows by factors **4.13–7.75**. Selecting
the eight-row coarse grid merely because its sampled Mach stays below unity
would conceal that unresolved refinement behavior.

![Native AVL chord/span refinement](../../artifacts/isae/sa11-native-chord-refinement-20261108/native-chord-refinement.png)

[Exportable SVG](../../artifacts/isae/sa11-native-chord-refinement-20261108/native-chord-refinement.svg).
The plot uses the application's VibeLattice color order and was visually reviewed.

## Independent field and force checks

Every native process exits successfully. Reconstructing native Kutta–Joukowski
forces from saved circulation, bound vectors and velocities reproduces CL and
near-field drag within **5.0e−16**. Moments reconstructed about the native
reference point agree within 1e−10. Origin moments are retained separately;
they omit ASWING's section profile-moment law and are not compared as full CM.

At each case's worst force point, direct 96-point Gauss integration of finite
bound filaments plus analytic semi-infinite rays reproduces native induced
velocity within **1.07e−4 m/s**. Increasing bound quadrature to 192 points
changes it by at most **2.42e−11 m/s**. These checks use zero core and native
AVL's rounded `1/(4*pi)` constant; native AVL retains its tiny numerical core.
The comparison is therefore approximate, not a roundoff-equality claim.

A separate closed-segment/ray evaluator checks every control point in small
blocks. Maximum normal residual is **4.81e−7 times freestream**, including
that same zero-core versus native-core distinction. No production vortex
kernel is called for these independent evaluations.

All maxima occur near an upper-winglet root. Independent wake-vector norms
range from **230 to 3,496 m/s**, versus **10.7 to 286 m/s** for the bound
contribution. These norms do not add to total speed; vector summation and
beam-normal projection determine Mach. The root interaction persists in the
finite-chord native model despite close integrated lift/CDi agreement.

## Source follow-up and implications

The earlier repository-history check covered only baseline and extension.
This turn extends it to **all 65 SA-11 files**, including winglet inputs,
drivers, output and geometry drawings. All have identical Git blob hashes
in the seven retained snapshots containing SA-11; the other two snapshots
contain no SA-11 files. No older winglet input resolves the sign or junction
conflict within that retained public history.

Jan's existing 289-page thesis was located and checked against its retained
SHA-256 receipt. Its SA-11 discussion on printed pp. 93 and 96 repeats the MSES
input qualification and enabled-PG statement; it supplies no recovered native
junction rule or run mesh. The comparison already maps archived CM to the
origin aerodynamic moment (Drela equations 221/225), so the input's distant
moment reference is not a newly discovered mapping error.
[Source follow-up evidence](../../artifacts/isae/sa11-native-chord-refinement-20261108/source-followup.json).

The next investigation should examine junction mesh conformity and how the
archived ASWING setup handled the overlapping root chord/wake geometry.
AVL's spacing rules and ASWING's zero-core warning are relevant evidence.
Changing the elementary kernel, merging Fourier domains, or accepting a
coarse successful sample is not supported by these results. The native
finite-chord checks strengthen confidence in the integrated loading comparison
while leaving local flow, total drag and moments unresolved.

## Reproduction

The [driver](../../scripts/verify-sa11-native-chord-refinement.py) runs one
native process per `--case 0` through `--case 5`, after `--prepare` with a fresh
`--output` directory. Jobs use one BLAS thread, a 45-second outer limit and
768 MiB address-space limit; native subprocesses have a 30-second limit.
The six native calls total **4.10 seconds**, excluding startup/provenance work.
All jobs are serial and terminal. No background solver or agent is started.

[Predeclared plan](../../artifacts/isae/sa11-native-chord-refinement-20261108/plan.json),
[analyzer](../../scripts/analyze-sa11-native-chord-refinement.py),
[complete results](../../artifacts/isae/sa11-native-chord-refinement-20261108/analysis.json).
