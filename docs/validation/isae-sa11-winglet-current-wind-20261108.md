# SA-11: current-wind influences retain two distinct local-flow failures

2026-11-08 UTC. The documented current-wind option does **not** resolve the
archived-speed upper-winglet case, including the report-derived −4° twist.
Sixteen fixed comparisons span 1°/5°, both twist signs, 64/128 vortices and
frozen/current-wind influences. All fail the local section-normal Mach check.
Twelve production calls are new; four frozen 64-vortex states are reused.

Independent Biot–Savart evaluation reproduces the worst-point fields within
**9.49e-10 m/s**. At 1°, the dominant source remains a root wake ray. At 5°
with current-wind influences and the finer mesh, the maximum moves to the
main-wing center and is dominated by the opposite half-wing's bound vortex.
The latter two cases also exceed section lift limits and are retained as
diagnostics; post-stall repairs remain deferred.

No production equations, defaults, original/bundled inputs, Mach guard,
registered fraction or scope changes. **SA-11 remains 163/4,592 at 5%.**
The complete ASWING/browser implementation remains unfinished.

## Why this option was checked

The [ASWING user guide](../../reference/aswing_doc.txt),
**Fast,Slow Vortex-Lattice Model — F**, recommends considering current-wind
influences for nearby surface/wake interactions. Drela's steady description,
**§4.6, p. 36**, distinguishes that treatment from the jig-geometry,
zero-wind-angle approximation. The earlier
[winglet checks](isae-sa11-winglet-junction-20261107.md) used the literal +4°
input at 30 m/s. They do not answer whether the report's −4° sign at the
archived 240 m/s removes the failure.

The new cases retain speed 240 m/s, density 1.2256, automatic PG Mach
`240/340.21`, the existing stall law and local Mach guard. Both grids use
retained native AVL node/receiver coordinates from the
[geometry conversion audit](isae-sa11-avl-conversion-20261108.md): 64 and 128
vortices, with one chord row. They are diagnostic discretizations, not a
recovered native ASWING mesh. These are production OpenSwing wake-option
comparisons; the current-wind cases are not native AVL solves.

## Maximum local Mach

| Aircraft angle | Upper twist | Frozen, 64 | Current-wind, 64 | Frozen, 128 | Current-wind, 128 |
|---|---:|---:|---:|---:|---:|
| 1° | +4° | 1.75875 | 2.79583 | 6.70431 | 5.27882 |
| 1° | −4° | 1.57365 | 2.06542 | 5.12656 | 3.96702 |
| 5° | +4° | 3.07025 | 1.50042 | 11.32307 | 1.51461 |
| 5° | −4° | 2.93188 | 1.32555 | 10.03496 | 1.51347 |

All circulation solves meet the existing 1e-8 residual gate before the Mach
rejection. The two 128-vortex, 5°, current-wind states each have two sections
outside their lift limits. The other fourteen states have no such sections.
Neither the source sign nor this documented option is a general repair.

## Root wake versus center bound-vortex contributions

For the report-derived −4° cases, the independently reconstructed terms at
the worst point are:

| Angle and current-wind mesh | Worst location | Magnitude of summed bound field | Magnitude of summed wake field |
|---|---|---:|---:|
| 1°, 64 vortices | Upper-winglet root | 4.023 m/s | 917.319 m/s |
| 1°, 128 vortices | Upper-winglet root | 3.721 m/s | 2,403.198 m/s |
| 5°, 128 vortices | Main-wing center | 459.894 m/s | 0.950 m/s |

These are magnitudes of separate vector sums, not additive scalar speeds.
The local Mach diagnostic projects the complete velocity perpendicular to
the beam before taking its magnitude.

At 1° on the finer grid, the dominant main-wing root ray passes **0.333 mm**
from the worst receiver and contributes 2,375.52 m/s before other sources
are added. The bound-vortex contribution is small there, so a correction
confined to bound curvature cannot resolve that wake encounter.

At 5° on the finer grid, the worst point lies at `t=0.00415038 m` on the
main wing. The opposite near-center bound segment contributes **445.823 m/s**
of the approximately 459.894 m/s summed bound field. This is a separate
mechanism from the winglet-root wake. It is consistent with the earlier
[curved-line velocity analysis](curved-section-velocity-20261107.md), now
identified in the actual geometry. The two stalled fine-grid cases do not
establish a pre-stall repair or a new comparison failure category.

## Independent numerical check

The saved-state analyzer constructs the PG transformation from freestream
Mach and wake direction. It integrates every other finite bound segment
directly using 96-point Gauss quadrature, repeats with 160 points, and uses
an independently transcribed analytical semi-infinite-ray expression for
the wakes. Only the receiver's own bound segment is omitted. It does not
call a production vortex kernel or influence operator.

The maximum 96→160 quadrature change is **1.90e-11 m/s**. Summed bound, wake,
and total velocities agree with the production diagnostics within
**9.49e-10 m/s** across all sixteen worst points. Thus the large fields are
reproduced by direct integration of the declared vortex geometry. This does
not authenticate native ASWING's undisclosed producing settings or establish
that the idealized local field is physically usable.

All beams share physical index 1. The user guide explicitly specifies zero
mutual core for that arrangement and warns about close trailing-leg/control-
point encounters. These checks therefore retain zero core. Drela's local
section moment still uses beam-normal velocity and its local Mach correction;
the new evidence does not justify bypassing that validity check.

## What the report says about excessive refinement

ISAE Part I, **§5, p. 21**, recommends about **20–40 circulation variables or
Fourier coefficients** based on its elliptical-wing comparison. It separately
reports velocity singularities at much higher cosine-clustered resolution,
after useful results have converged at a smaller node count. The page was
visually checked in the original PDF and retained
[here](../../artifacts/isae/sa11-winglet-current-wind-20261108/isae-p21.png).

This is specific evidence about the elliptical-wing study, not a demonstrated
SA-11 resolution choice. It does mean that ever finer local vortex samples
cannot automatically be treated as a better reference for this model.
The next check should establish whether a practical documented resolution
range gives stable SA-11 loads and valid section states, preserving the
distinction between structural nodes and circulation variables. Select that
range from the documentation, not by fitting the archived answer. A valid
coarse result alone would still be insufficient.

## Reproduction

- [Fixed-case driver](../../scripts/verify-sa11-winglet-current-wind.py).
- [Plan, reused outputs and source pins](../../artifacts/isae/sa11-winglet-current-wind-20261108/plan.json).
- [Independent saved-field analyzer](../../scripts/analyze-sa11-winglet-current-wind.py).
- [Full checked results](../../artifacts/isae/sa11-winglet-current-wind-20261108/analysis.json).

The twelve new aerodynamic calls ran serially with one BLAS thread and
totaled **2.156 s**, excluding import/setup/provenance overhead. Each group
was bounded by a 45-second outer timeout and 768 MiB address-space limit.
All completed without solver timeouts. Verification covers 163 unchanged
source/production/status pins, all sixteen retained reports and their
artifacts, both meshes, applied conditions, circulation residuals, local
Mach values, stall margins and the independent field integration.
