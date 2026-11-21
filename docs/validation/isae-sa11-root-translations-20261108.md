# SA-11: root-position sensitivity on two meshes

2026-11-08 UTC. Twelve small serial production solves distinguish a streamwise
root offset from distance across the root wake. The unchanged diagnostic
control retains close lift and drag while peak normal Mach grows from
**1.534 to 2.668** under refinement. The section-moment calculation remains
locally undefined even where integrated force totals agree.

A prescribed 0.25 mm outward winglet translation gives finite moments on both
meshes, but drag errors are **+6.35% and +10.59%**. Aligning quarter-chord roots
instead raises local Mach to **2.250 and 3.733**, with the dominant contribution
switching from wake to bound vortices. None is a validated correction or new
primary pass. SA-11 remains **163/9,184 at 5%**.

## Sources, setup and controlled changes

The authoritative index and checksummed catalog were consulted. Drela's user
guide, **Joint block**, defines a rigid pylon retaining the offset between beam
attachments; it does not require coincident vortex endpoints. Its **Physical
index** section warns of close wake/control-point encounters when beams share
a physical index and hence zero mutual core. Steady **Eqs. 64–74** define
velocities, forces and moments; **Eqs. 150–161** define discrete geometry and
influences. The unchanged section-moment formula is undefined at normal Mach ≥ 1.

Use the disclosed report-minus4 upper-winglet alternative, alpha 1°, 240 m/s,
density 1.2256, sound speed 340.21, global PG 240/340.21, frozen influences and
original section properties. The prior Joint scaling correction is retained.
Physical index 1 and zero mutual core remain. No guard, stall or equation change.

The 64-interval grid uses retained native-AVL endpoints and production
whole-beam Glauert receivers. The 128-interval grid bisects each parameter
interval, preserving coarse nodes and section breaks. On these straight beams
this also bisects material length. Neither is an authenticated archived ASWING
grid or a new claim about the default discretization.

Six geometries and both meshes were declared before solving:

- Control: unchanged report-minus4 input.
- Forward/aft: translate both whole winglets by ∓1 mm along body x.
- Inward/outward: translate each whole winglet by ∓0.25 mm along its transverse
  span direction, with mirrored y and equal z changes. This deliberately adds
  a small transverse overlap or gap; it is not a reconstructed physical fillet.
- Aligned roots: translate both winglets forward 53.210964 mm to align their
  frozen quarter-chord roots with the main wing. This larger edit isolates
  the offset mechanism and is separate from the small perturbations.

Local shapes, cant, incidence, chord, section data and Joint parameters remain
fixed. Source checks and the production parser verify each translation.
Maximum position error from rigid translation is 2.64e-16 m; frame changes are
below 3.34e-16. Exact input diffs are retained.

## Results

Cells report **64 → 128 intervals**. Signed errors use archived alpha-1°
CL = 0.336959 and raw CD = 0.0103591; neither includes the plotting allowance.

| Geometry | CL error, % | CD error, % | Maximum normal Mach | Rejected sections |
|---|---:|---:|---:|---:|
| Control | −0.692 → −0.323 | +0.065 → +2.053 | 1.534 → 2.668 | 2 → 2 |
| Forward 1 mm | −0.651 → −0.290 | −0.002 → +2.016 | 1.540 → 2.676 | 2 → 2 |
| Aft 1 mm | −0.734 → −0.356 | +0.135 → +2.092 | 1.528 → 2.660 | 2 → 2 |
| Inward 0.25 mm | +3.642 → −5.704 | −53.924 → −43.116 | 4.939 → 11.529 | 2 → 4 |
| Outward 0.25 mm | −1.648 → −1.836 | +6.348 → +10.591 | 0.838 → 0.722 | 0 → 0 |
| Aligned quarter-chord roots | +0.733 → +1.046 | +2.629 → +5.226 | 2.250 → 3.733 | 2 → 4 |

Rejected rows contain **formal surface-force sums**, not valid complete
solutions; their intrinsic section moments are unavailable. The outward
alternative produces complete rigid-aerodynamic results under the unchanged
guard: `Cm_origin = −0.45727730 / −0.45475224`. It remains an altered input,
with drag outside 5%; two meshes do not establish convergence. No original
target is discarded or counted as passing.

The fresh 64-interval control exactly reproduces saved circulation, velocity
and section CL. All twelve circulation residuals are below 1.80e-14. Every
section remains at least 18.71 configured stall widths inside its lift limits.
Incomplete circulation convergence and stall do not explain this sensitivity.

## What the changes isolate

**Along the wake:** ±1 mm preserves perpendicular receiver/ray distance.
Results change modestly, and both variants retain the control's strong
peak-velocity increase with refinement.

**Across the wake:** the control root receiver is 0.506492 / 0.252940 mm from
the main-wing ray. The inward shift reduces this to 0.256492 / **0.002940 mm**,
explaining the stronger fine-grid encounter. The outward shift instead gives
0.756492 / 0.502940 mm. Avoiding the close encounter permits finite moments
here but also changes circulation and drag. Selecting a convenient gap would
not recover the physical geometry or native ASWING algorithm.

**Offset versus sharp corner:** the control's worst receiver has summed
wake-induced speeds 488.0 / 889.3 m/s and bound-induced speeds about 4.5 m/s.
After alignment, wake contributions fall to 71.5 / 79.4 m/s, while bound
contributions rise to **568.0 / 1072.8 m/s**. These are vector norms, not scalar
speeds to add. The sharp bound-line turn becomes dominant, consistent with
the [ideal shared-corner audit](isae-sa11-shared-bound-corner-20261108.md), now
on the actual translated SA-11 geometry.

After decimal ASW parsing the aligned roots differ by 2.22e-16 m. A separate
saved-circulation replay makes those endpoints exactly equal; the maximum
velocity change is only 1.29e-9 m/s. Roundoff coincidence and wake grouping
therefore do not explain the failure. No endpoint is snapped in production.

## Next decision

Close force totals are useful evidence but cannot validate missing moments or
local mesh behavior. Translations and simple root alignment do not supply a
correction. The next geometry experiment should separate a **smooth
quarter-chord transition** from changes in root chord and incidence, retaining
each fixed physical blend on multiple meshes. NASA's documented fillets
motivate this without establishing their radius or ASWING's representation.

Preserve the archived case and explicitly labeled alternative inputs. Require
finite, stable local flow and moments alongside the paper's ASWING force
curves. Do not fit a gap, core, blend length or receiver location to force
errors. Successful native Figure 22 curves remain a constraint; this study
establishes sensitivity in our representation, not native ASWING's behavior.

## Evidence and execution

- [Preparation, single-case execution and verification driver](../../scripts/verify-sa11-root-translations.py).
- [Predeclared geometries, grids and source hashes](../../artifacts/isae/sa11-root-translations-20261108/plan.json).
- [Twelve checked reports and refinement changes](../../artifacts/isae/sa11-root-translations-20261108/analysis.json).
- [Exact-coincidence rounding replay](../../artifacts/isae/sa11-root-translations-20261108/roundoff-check.json).

Each case retains geometry, circulation, local velocity, bound/wake fields,
forces and its accepted result or full rejection. Hash verification covers
current modules/inputs and case artifacts. Field reconstruction agrees within
1.03e-12 m/s; scalar force projections and reflected root values also pass.

All twelve processes completed normally with one BLAS thread, 512 MiB address
space, 15-second CPU and 25-second wall limits. Processes took 1.69–2.71 seconds
each, actual solves 0.012–0.043 seconds, reported peak RSS 220.5–238.6 MiB.
No browser, Vite or build job was launched; the earlier crash cause is unresolved.
