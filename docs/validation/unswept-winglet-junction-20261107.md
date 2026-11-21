# Unswept winglet control: topology and sharp-junction velocity

2026-11-07. Eight small serial aerodynamic evaluations and eight independent
prescribed-field checks distinguish connectivity from the sharp-corner field.
No production solver, default, bundled example, ISAE scope or pass count changed.

## Findings

- Dividing a straight lifting line into three logical beams, while preserving
  exactly the same physical intervals and sample positions, gives **identical**
  circulation, strip velocities/forces, integrated forces/moments and coefficients.
  This checks logical ownership, not independent remeshing or Fourier equivalence.
- Eight three-branch field checks agree with independent, directly integrated
  Biot–Savart filaments within **1.11e-16 m/s**. They include a reversed lower
  branch, balanced/unbalanced circulation and a 0.05 m longitudinal offset.
  Coincident origins combine signed circulation correctly; offset rays remain
  distinct. No missing sign or cancellation error is exposed by these controls.
- An **unswept**, sharp 90-degree winglet junction still develops growing local
  speed as the mesh is refined. Here the growth is entirely in the streamwise
  velocity induced by the **adjoining bound vortex**, not the trailing legs.
  The small circulation jump at the junction decreases with refinement.
- Total drag agrees with Trefftz induced drag to within **2.9e-16** in this
  ideal unswept, zero-profile-drag control. The near-/far-field mismatch seen
  elsewhere is therefore not universal to joined surfaces.

The topology checks do not impose equal circulation on branches. A discrete
horseshoe junction with unequal incoming/outgoing bound circulation emits the
signed remainder into a trailing ray. Conservation includes that ray. DLR's
additional continuous-element coupling conditions are a separate formulation,
not a constraint silently added to OpenSwing.

## Setup and relation to the literature

[Kleine, Hanifi & Henningson (2023)](https://arxiv.org/html/2209.00096v2),
Table 1 and §III, supplies the main span 1 m, winglet height 0.2 m, chord 0.1 m,
section slope 2π, zero profile drag, unit freestream speed, and geometric
incidence 1/(2π) rad. The radian expression converts to **9.1189065 degrees**;
the table's printed 9.189 degrees is inconsistent. This diagnostic explicitly
uses the radian expression and makes no claim to have resolved the authors'
actual numerical input. All three sections have positive local incidence,
giving inward lift on the winglets. The section twist supplies incidence;
the freestream is along body x.

The beam axis is the quarter-chord line (`Xax=.25`), so all bound endpoints at
each junction coincide exactly. Both winglets extend upward; their circulation
orientation follows the continuous path from the left tip, through the main
wing, to the right tip. Every beam has physical index 1. PG Mach is explicitly
zero, stall is disabled, and influences use the current wind. Local Mach still
uses the actual atmospheric sound speed. No core acts within this common
physical surface, in accordance with the existing ASWING physical-index rule.

The paper uses uniformly spaced controls at 0.02 m on its reported grid.
OpenSwing's production Glauert samples are not uniform even with uniform panel
endpoints. Both sample choices are therefore recorded separately: the ordinary
Glauert construction and a **diagnostic-only** arithmetic-midpoint override.
There is no new production sampling option. Main-wing intervals are 50, 100,
and 200; each winglet has 10, 20, and 40 intervals respectively.

This is a mechanism control, **not a scored reproduction** of the paper or an
original ASWING case. ASWING's downstream tangency equation is different from
the paper's nonlinear sectional lifting-line closure. No curve digitization,
experimental match, native ASWING result or validation pass is claimed.

## Refinement results

Reference area is 0.1 m²; peak speed is divided by the unit freestream speed.

| Sampling | Main-wing intervals | Total intervals | CL | CD | Peak speed / freestream | Peak bound-induced streamwise speed / freestream |
|---|---:|---:|---:|---:|---:|---:|
| Glauert | 50 | 70 | 1.021164 | 0.02661432 | 1.871447 | 0.870436 |
| Glauert | 100 | 140 | 1.021615 | 0.02662282 | 2.726030 | 1.725203 |
| Glauert | 200 | 280 | 1.024703 | 0.02666735 | 4.424747 | 3.424162 |
| Arithmetic control | 50 | 70 | 0.992083 | 0.02674318 | 1.424025 | 0.423215 |
| Arithmetic control | 100 | 140 | 0.997702 | 0.02675727 | 1.849900 | 0.849187 |
| Arithmetic control | 200 | 280 | 1.003556 | 0.02675503 | 2.699538 | 1.699017 |

Across the three production-sample grids, CL changes **0.347%**, CD **0.199%**,
and Cm **3.00%**, while peak speed increases **136.4%**. Arithmetic controls
also show growing velocity, with CL changing 1.156% and CD 0.0443%. Successful
execution and comparatively stable total loads do not prove a converged local
flow field or an asymptotic integrated solution.

At the finest Glauert-grid peak, the bound contribution is
`[3.424162, 0, 0]` times freestream. The wake contributes approximately
`[0, 0.058878, -0.041368]`; adding the freestream gives the reported peak.
The peak's distance from the corner halves with each refinement, and its bound
contribution approximately doubles. Meanwhile the root-ray magnitude decreases
from 0.0006691 to 0.0002482 m²/s. Arithmetic controls produce the same qualitative
behavior; moving the receiver farther from the corner reduces the sampled peak
but does not remove the singularity.

![Saved circulation, velocity, refinement and lift diagnostics](../../artifacts/isae/unswept-winglet-junction-20261107/junction-refinement.png)

The paper itself explicitly identifies the sharp intersection as singular in
§III (PDF p.12), recommending desingularization and a smooth transition if the
spanwise grid is refined. Our isolated result is consistent with that warning.
It does **not** justify introducing a same-surface core into ASWING, suppressing
the Mach guard, or claiming that the SA-11 failures are now repaired.

## Consequence for SA-11

There are now three distinct mechanisms to keep separate:

1. Sharp-corner bound induction, isolated here with coincident origins and no sweep.
2. Finite streamwise connector fields between longitudinally offset root rays,
   established in the [SA-11 junction study](isae-sa11-winglet-junction-20261107.md).
3. The swept lifting line's wake-induced force-point singularity, established
   in the [prescribed-circulation study](swept-lifting-line-limit.md).

The present controls weaken the hypothesis of a basic incidence-sign or
logical-beam ownership bug. They leave the native ASWING treatment of force
velocity, sharp connections and connected-surface sampling unresolved. The next
useful comparison is a controlled finite-chord or documented generalized
lifting-line force field, with geometry and load definitions stated explicitly;
another arbitrary core or mode sweep would not distinguish these mechanisms.

The subsequent [finite-chord comparison](winglet-finite-chord-20261107.md)
establishes an independent one-row match and separates chordwise circulation
concentration from changes in solved loading. It reduces quarter-chord probe
peaks with added chord rows, but actual finite-edge peaks still grow. The
finite-chord force definition and remaining singularities are retained explicitly.

## Reproduction and verification

Run the driver in a **fresh** output directory; it rejects overwriting a prior
observation. Use one BLAS thread and a foreground job, for example:

```sh
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 timeout 60s prlimit --as=805306368 .venv/bin/python scripts/verify-unswept-winglet-junction.py --output artifacts/isae/unswept-winglet-junction-new
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 timeout 60s prlimit --as=805306368 .venv/bin/python scripts/analyze-unswept-winglet-junction.py --study artifacts/isae/unswept-winglet-junction-new
```

The six winglet solves total **0.659 seconds** (excluding startup, independent
quadrature, recording and plotting); the maximum normalized circulation
residual is **4.05e-15**. Raw results, full applied conditions, source copies,
141 production-module hashes, status/scope hashes, the executed driver, and
artifact hashes are retained. The separate analysis verifies these pins,
request coverage, root incidence from strip ownership, force-field decomposition,
sample spacing and reported metrics without rerunning the aerodynamic solver.

- [Plan](../../artifacts/isae/unswept-winglet-junction-20261107/plan.json)
- [Raw winglet results](../../artifacts/isae/unswept-winglet-junction-20261107/results.json)
- [Same-mesh logical partition](../../artifacts/isae/unswept-winglet-junction-20261107/partition-check.json)
- [Independent fork quadrature](../../artifacts/isae/unswept-winglet-junction-20261107/fork-checks.json)
- [Audited analysis](../../artifacts/isae/unswept-winglet-junction-20261107/analysis.json)
- [Plot as SVG](../../artifacts/isae/unswept-winglet-junction-20261107/junction-refinement.svg)
