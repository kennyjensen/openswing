# Sharp winglet: independent finite-chord comparison

2026-11-07. Six small serial independent vortex-lattice solves, followed by
six prescribed-circulation field evaluations, extend the
[unswept junction control](unswept-winglet-junction-20261107.md). The one-row
reference matches OpenSwing's lifting-line calculation to roundoff. Resolving
the chord reduces the sampled quarter-chord spike, but the actual vortex-edge
speed maxima still grow. No ASWING-compatible repair or continuum convergence
has been established. Production equations and ISAE counts are unchanged.

## Documentation check

Drela's [steady technical description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf)
defines local velocity including induced flow in equations 64–65, uses that
velocity at the bound vortex for lift in equation 67, and uses local
perpendicular Mach for the section moment in equation 73. Equations 150–157
define sampled horseshoes, force points and downstream controls. Equation 161
introduces a core for other surfaces. These passages support the current
distinction between force-point velocity and tangency velocity; they do not
authorize substituting freestream velocity or a same-surface core to suppress
the observed local-Mach failures. The public documentation does not establish
the missing native implementation detail at sharp or swept connections.

## Reference and geometry

The finite-segment, ray, ring, boundary-solve and canonical-edge load kernels
are unmodified copies from the previously reviewed
[finite-chord evidence archive](swept-finite-chord-evidence.zip). Their hashes
and the archive hash are verified before importing. The new solver driver has
**no OpenSwing imports** and does not introduce a production dependency.

The geometry retains the earlier unswept control's 1 m main span, 0.2 m upward
winglets, 0.1 m chord and incidence expression 1/(2π) radians. Three conforming
zero-thickness sheets meet at sharp right-angle corners. Chord edges run along
x; incidence is imposed through the boundary-condition normals. This matches
the earlier ASWING lifting geometry at one chord row, but is not an exact
finite-angle intersection of physically twisted plates. The incidence and
benchmark qualifications in the [earlier report](unswept-winglet-junction-20261107.md)
remain in force.

Main-wing span counts are 50 and 100; each winglet has N/5 intervals. Arithmetic
span samples are used throughout this comparison. Chordwise row counts are
1, 2 and 4, for at most 560 panels. The reference retains its documented
quarter-panel rear extension beyond the physical trailing edge, with straight
x-aligned semi-infinite wakes. Every shared vertex follows explicit connectivity;
no distance-based merging is applied. There is no core, stall, PG correction,
body or structural deformation. Freestream speed is 1 m/s and density 1.225 kg/m³.

## The one-row bridge agrees

For each span grid, compare the one-row reference against the saved
arithmetic-sample OpenSwing calculation. The largest absolute differences are:

| Compared quantity | Maximum absolute difference over both grids |
|---|---:|
| Circulation | 5.56e-17 m²/s |
| Quarter-chord receiver coordinates | 1.39e-16 m |
| Quarter-chord relative velocity | 8.99e-16 m/s |
| Integrated front-bound force | 4.86e-17 N |
| Integrated front-bound moment | 7.65e-18 N·m |

This agreement checks the boundary equations, signed induction and bound-line
force path with an independent implementation. It does not assert equivalence
between the full finite-chord force definition and ASWING's single bound line.

The full reference force includes **every canonical finite edge**, including
chordwise edges; wake rays carry no body force. At one row and N100, the
front-bound CL is 0.997702, matching OpenSwing. Chordwise edges contribute
CL = −0.015113, so the full reference CL is 0.982590. That difference is an
explicit difference in load definition, not a failed one-row bridge. With
multiple rows, all spanwise rows and chordwise edges are retained separately.

## Solved-circulation results

Speeds are divided by freestream; full CL uses Sref = 0.1 m². Quarter-chord
probes remain at x=0, whereas the individual bound rows move chordwise as the
chord is refined. With two or four rows those probes lie between vortex rows.

| Chord rows | Main span intervals | Total panels | Quarter-chord peak speed | Actual finite-edge peak speed | Full CL | Full CD |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 50 | 70 | 1.424025 | 1.424025 | 0.976951 | 0.02674318 |
| 1 | 100 | 140 | 1.849900 | 1.849900 | 0.982590 | 0.02675727 |
| 2 | 50 | 140 | 1.213054 | 1.320021 | 0.964288 | 0.02640201 |
| 2 | 100 | 280 | 1.218634 | 1.638806 | 0.967633 | 0.02642730 |
| 4 | 50 | 280 | 1.132803 | 1.244507 | 0.959124 | 0.02626519 |
| 4 | 100 | 560 | 1.129010 | 1.470078 | 0.960936 | 0.02630802 |

When span resolution doubles, the one-row quarter-chord maximum grows 29.91%.
It changes +0.460% with two rows and −0.335% with four rows. However, actual
finite-edge maxima grow **24.15%** and **18.13%** for two and four rows.
Stable quarter-chord probes therefore do not prove a converged force-point
field. Finite chord also retains ideal sheet-edge and sharp-corner limitations.

## Prescribed circulation isolates chordwise concentration

An additional field-only control uses the saved lifting-line Gamma(s) on each
span grid and assigns cumulative ring circulation `(i+1)/Nc * Gamma(s)`.
Every chordwise bound increment is consequently Gamma(s)/Nc; total section
circulation and trailing-wake strengths are preserved. This deliberately
uniform distribution is **not** a thin-airfoil pressure model or a solved
finite-chord state.

| Chord rows | Quarter-chord peak, N50 | Quarter-chord peak, N100 |
|---:|---:|---:|
| 1 | 1.424025 | 1.849900 |
| 2 | 1.124409 | 1.131654 |
| 4 | 1.140970 | 1.135506 |

The large reduction persists without changing the total section circulation.
This isolates a contribution from concentrating the bound vorticity onto one
line. The multirow prescribed fields have unsatisfied boundary residuals of
0.148–0.227 m/s, deliberately retained in the artifacts. They cannot be used as
accepted aerodynamic solutions or scored against reference data.

![Finite-chord and fixed-circulation controls](../../artifacts/isae/winglet-finite-chord-20261107-review/finite-chord-comparison.png)

## Consequence and remaining work

The independent one-row agreement gives no evidence of a basic kernel/sign
bug in this unswept control. The fixed-circulation control identifies the
importance of finite chord in the local field. The continuing edge-velocity
growth prevents treating the multirow calculation as a finished remedy.

The remaining comparison should identify a documented section-velocity
definition or connected-surface treatment and test its local fields and load
closure. ASWING's published bound-point force law remains the implementation
target. Selecting a different probe, replacing total drag, or changing a core
without such a derivation would not demonstrate parity. SA-11's swept wake
and offset-root mechanisms remain separate unresolved effects.

## Reproduction and audit

Both commands require fresh output directories. The solver uses six serial
linear systems; the analysis performs no new solves. Use one BLAS thread:

```sh
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 timeout 60s prlimit --as=805306368 .venv/bin/python scripts/verify-winglet-finite-chord.py --output artifacts/isae/winglet-finite-chord-new
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 timeout 60s prlimit --as=805306368 .venv/bin/python scripts/analyze-winglet-finite-chord.py --study artifacts/isae/winglet-finite-chord-new --analysis-output artifacts/isae/winglet-finite-chord-new-review
```

The six solve/field/save stages total 4.286 seconds, excluding startup and the
separate analysis. Saved operator residuals are at most 7.92e-15 m/s; an
independent compensated scalar matrix product gives at most 3.67e-15 m/s.
The audit reconstructs forces/moments componentwise, verifies every coefficient
column's endpoint flux balance including rays, checks retained load sums,
checks the one-row bridge and verifies prescribed trailing strengths. All
141 production-module hashes and status/scope hashes remain unchanged.

- [Plan and reference pins](../../artifacts/isae/winglet-finite-chord-20261107/plan.json)
- [Solved results](../../artifacts/isae/winglet-finite-chord-20261107/results.json)
- [Prescribed-field plan](../../artifacts/isae/winglet-finite-chord-20261107-review/plan.json)
- [Audit and field results](../../artifacts/isae/winglet-finite-chord-20261107-review/analysis.json)
- [Plot as SVG](../../artifacts/isae/winglet-finite-chord-20261107-review/finite-chord-comparison.svg)
