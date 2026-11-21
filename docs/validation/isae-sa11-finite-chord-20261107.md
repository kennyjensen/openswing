# SA-11 winglet roots: finite-chord comparison

2026-11-07. Ten independent linear finite-chord solutions extend the actual
saved SA-11 frozen lifting geometry. Their numerical residuals are small, but
their loads and local velocities do not establish a physically acceptable or
mesh-converged replacement for ASWING. The upper/lower configuration remains
especially problematic, including negative drag in several linear controls.

The new work establishes an exact treatment of overlapping root-boundary
filaments for the independent diagnostic, and verifies the one-row field
against both a direct horseshoe calculation and saved production extrema.
No production aerodynamic rule changes. SA-11 remains **163/4,592 at 5%**.

## Geometry and scope

This follows the [grouping and root-field audit](isae-sa11-generalized-topology-20261107.md).
Both bundled winglet variants retain their original saved N48/N96 spanwise
endpoints and Glauert samples. The upper root remains 53.210964 mm downstream
of the main-wing quarter-chord endpoint; the lower root remains 25.901302 mm
upstream and 0.070 mm lower. No endpoint is moved and no near-neighbor core is
introduced.

Chordwise rows are constructed along the frozen x direction using the original
normal-section chord divided by the beam tangent's projection into the y-z
plane. Quarter-chord locations are the saved frozen lifting-line positions.
This is a finite-chord extension of that aerodynamic geometry, not an exact
intersection of physically twisted plates or a new rendering convention.
The literal straight-beam coordinates, chords, twist and zero-lift parameters
are independently transcribed from the pinned examples and checked against
the saved quarter-chord and ASWING control-point coordinates.

The linear control uses speed 30 m/s, angle of attack 5 degrees, density
1.2256 kg/m³ and the same frozen PG transform at Mach `30/340.21`. The wake
remains x-aligned. Boundary normals include the original section twist and
zero-lift parameter, held constant along each chord. There is no stall,
profile drag or section moment in this independent model. Controls are at
three-quarter panel chord; ASWING's `dCLda/(4*pi)` displacement is therefore
not the finite-chord control rule. The original nonlinear circulation is used
only in a separately labeled prescribed-field comparison.

There are 1, 2 and 4 chordwise rows at N48 and 1 and 2 at N96, with 150–984
panels per case. Four rows at N96 were not run; the declared reference limit
is 1,200 panels. Each foreground batch contains at most three serial solves,
with one BLAS thread, a 60-second limit and a 768 MiB address-space limit.

The reference retains the previously reviewed quarter-panel extension of the
last vortex row beyond the physical trailing edge. Forces use the vector
Kutta–Joukowski rule at finite body-edge midpoints. This full-edge force
definition differs from ASWING's single-bound-line force law. None of these
linear results bypasses or changes the production local-Mach guard, and none
is accepted as a subsonic physical solution merely because its equations solve.

## Exact overlapping-boundary treatment

The first attempt stopped during finite-edge load evaluation: a main-wing
chord boundary and an upper-winglet chord boundary overlap along the same
line with different endpoints. The zero-core kernel correctly refused to
evaluate another coincident filament at an edge midpoint. That failed attempt,
including its original driver and plan, is retained. It completed one linear
solve but saved no solved-state record before the load failure.

The diagnostic now partitions each exactly x-parallel boundary at every
existing endpoint. It combines all incident finite-edge and wake coefficients
on the resulting nonoverlapping segments. Rays with the same exact y and z
are represented by finite segments up to a common downstream origin and one
combined ray beyond it. **No tolerance merges coordinates, no origin moves,
and no core softens the field.** The lower root's 70-micrometre offset remains
distinct.

Two coefficient ledgers are retained. Velocity uses every original vortex
contribution, including wake segments. Body force uses only the original
finite body-edge contributions; wake-only pieces carry no body force. At each
body-edge midpoint, only its own combined straight filament is omitted under
the reference's existing self-velocity convention.

Every source has exactly zero discrete divergence at every finite vertex.
The independent analysis compares all unit-source fields with the original
unsplit ring formulas at three off-sheet probes. The largest difference is
**4.61e−15** in unit-circulation influence. This verifies field preservation;
it does not certify the midpoint load quadrature as a continuum force solution.

## Retained linear solutions

Both velocity columns below are divided by freestream speed. The first samples
the original quarter-chord locations; the second samples the actual finite
body edges used by the independent force calculation.

| Model | Intervals/beam | Chord rows | Quarter-chord peak | Body-edge peak | Full-edge CL | Full-edge CD |
|---|---:|---:|---:|---:|---:|---:|
| Upper | 48 | 1 | 40.371 | 20.138 | 0.581111 | 0.006409 |
| Upper | 48 | 2 | 1.580 | 27.601 | 0.608976 | 0.010542 |
| Upper | 48 | 4 | 1.168 | 19.378 | 0.580682 | 0.010881 |
| Upper | 96 | 1 | 160.046 | 79.933 | 0.581244 | 0.006690 |
| Upper | 96 | 2 | 2.511 | 105.957 | 0.664124 | 0.015399 |
| Upper/lower | 48 | 1 | 305.322 | 542.239 | −4.007730 | −0.380145 |
| Upper/lower | 48 | 2 | 24.167 | 50.496 | 0.379104 | −0.010083 |
| Upper/lower | 48 | 4 | 23.100 | 124.028 | 0.610142 | 0.013414 |
| Upper/lower | 96 | 1 | 602.932 | 816.258 | −4.885105 | −0.474384 |
| Upper/lower | 96 | 2 | 14.599 | 93.015 | 0.420416 | −0.006828 |

These large speeds and negative coefficients are retained as failures of the
physical comparison, not hidden behind the successful linear residual gate.
The one-row linear upper/lower circulation differs substantially from the
saved nonlinear/stall calculation; those are different section problems.

For the upper model with two rows, N48→N96 changes CL by **+9.06%**, CD by
**+46.07%**, and the body-edge peak by **+283.89%**. Its four-row coarse-grid
quarter-chord peak is much smaller, but that alone does not establish stable
forces. For upper/lower with two rows, CL changes **+10.90%**, drag remains
negative, and the body-edge peak grows **+84.20%**. The corresponding sampled
quarter-chord normal Mach remains above one, about 2.12 and 1.28. Thus added
chordwise resolution does not establish a reliable repair for this configuration.

![Finite-chord refinement](../../artifacts/isae/sa11-finite-chord-20261107-review/finite-chord-comparison.png)

## Prescribed-field comparison and numerical verification

Ten additional field evaluations distribute each saved total section
circulation uniformly over the chordwise bound increments. They preserve
section totals, while wake origins follow the finite-chord topology. Their
boundary residuals are saved and are generally nonzero. These evaluations
isolate representation effects; they are not additional solved states.

At one row the complete prescribed quarter-chord field agrees with an
independent direct horseshoe evaluation within **9.38e−12 m/s**. Comparison
with the previously saved production extrema agrees within **7.75e−8 m/s**.
The first error compares two independent representations of the same source
geometry; the second includes differences from the production kernel. Neither
is an accuracy comparison against native ASWING results.

All ten retained linear solutions satisfy the declared residual gates. The
independent compensated scalar residual is at most **1.06e−12** for unit
freestream. The analysis also reconstructs force and moment components from
the body coefficient ledger and verifies off-sheet fields, all unit-source
columns, input hashes and source hashes. The largest net symmetry sideforce
is 8.25e−10 N. Production modules, example inputs, ISAE status and scope remain
unchanged.

The retained linear solves total 0.165 s; full recorded numerical stages,
including fields, loads and artifact storage, total 20.75 s. Startup and the
first failed attempt are excluded. These are native diagnostic timings, not
browser or complete-ASWING performance claims. No solvers ran in the background.

## Implementation consequence

The exact overlap subdivision is a verified improvement to the independent
diagnostic representation. It supplies no basis for changing the production
ASWING vortex geometry or force law. In particular, selecting only the smoother
quarter-chord probes would discard the unresolved force-edge behavior.

The remaining investigation must address the documented velocity/force
treatment and its sharp-junction limits. The present finite-chord approximation
cannot serve as an authoritative replacement target. Native ASWING agreement,
physical convergence of these sharp intersecting surfaces, current-wind
sensitivity, and the roles of the omitted section nonlinearities remain
unresolved. No reference denominator or completion fraction is changed.

The [isolated wake-direction follow-up](isae-sa11-wake-direction-20261107.md)
now rotates only the trailing rays, preserving geometry, PG map and force
probes. It removes negative drag in the independent controls and improves
some integrated-coefficient refinement, but retains large body-edge fields
and also exposes a close wake/body encounter. It is not a production repair.

Reproduce each of the four batches sequentially, using a fresh output directory:

```sh
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 timeout 60s prlimit --as=805306368 .venv/bin/python scripts/verify-sa11-finite-chord.py --model up --span 48 --output artifacts/isae/sa11-finite-chord-new-up48
```

Use `--model up-and-down` for the second model and `--span 96` for the finer
grid. Then run `scripts/analyze-sa11-finite-chord.py` with `--batches` followed
by the four output directories and `--output` naming a fresh review directory,
under the same serial resource limits.

- [Upper N48](../../artifacts/isae/sa11-finite-chord-20261107-up48-canonical/results.json)
- [Upper N96](../../artifacts/isae/sa11-finite-chord-20261107-up96/results.json)
- [Upper/lower N48](../../artifacts/isae/sa11-finite-chord-20261107-both48/results.json)
- [Upper/lower N96](../../artifacts/isae/sa11-finite-chord-20261107-both96/results.json)
- [Independent audit and source pins](../../artifacts/isae/sa11-finite-chord-20261107-review/analysis.json)
- [Retained first failure](../../artifacts/isae/sa11-finite-chord-20261107-up48/failure.json)
- [Plot as SVG](../../artifacts/isae/sa11-finite-chord-20261107-review/finite-chord-comparison.svg)
