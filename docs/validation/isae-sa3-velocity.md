# SA-3: bound-vortex and trailing-wake diagnostic

The remaining drag discrepancy is concentrated in the bound-vortex contribution,
but the independent calculation finds no defect in the sampled velocity kernels.
The tested JVL curvature analogue is too small and has the wrong sign to explain
the difference. No production kernel, model properties or defaults changed.
The original archived ASWING comparison remains incomplete.

## One retained state

The diagnostic uses the existing 400-interval SA-3 solution at the exact command
alpha = 10.017391304347827°, U = 89.4 m/s, rho = 1.2256 kg/m³, updated influences
and fixed PG Mach zero. It reconstructs geometry and one force-point operator
with the original circulation, zero same-surface core and own-bound exclusion.
The sum of bound and trailing velocities reproduces every saved velocity exactly.
There are no new equilibrium solves or residual evaluations.

| Contribution | Entire wing CD | Inner 90% of semispan CD |
|---|---:|---:|
| Bound vortices | +0.000983078963 | +0.000696331333 |
| Trailing wake | +0.030824141051 | +0.030040937042 |
| Half the far-wake velocity, same force integration | +0.031112668754 | +0.030099253182 |
| Bound + trailing − half far wake | +0.000694551260 | +0.000638015193 |

The full archived CD discrepancy remains +0.000758381994. The table isolates
velocity contributions; profile drag and the small difference in endpoint force
integration remain accounted for in the [previous force diagnostic](isae-sa3-reference-forces.md).
Most inner-wing bound drag comes from interactions with other inner-wing segments:
0.00064534699, versus 0.00005098434 from the outer 10%. Removing tip contributions
or deleting the bound field would not be a supported correction.

## Independent check

A separate implementation evaluates six selected receivers—both center-adjacent
points, both 90%-span boundaries and both extreme tips—with 50-digit analytical
line-integral formulas. It evaluates 2,394 finite-segment and 2,406 semi-infinite
ray contributions, explicitly excluding the six own-bound segments. All 341
checks pass, including endpoint grouping, fields, regional sums and saved-source
identity. Bound-field errors are at most 7.11e−15 m/s at these points and the
largest trailing-field error is 6.04e−14 m/s. This supports the sampled kernels;
it does not independently reconstruct ASWING's historical geometry or mesh.

The tip remains difficult: bound and trailing speeds reach 266.93 and 355.97 m/s.
The force point lies off its own straight segment by up to 0.00014894 m, although
its projection lies between the endpoints. The maximum distance/segment-length
ratio is about 0.204. Interior points have much smaller offsets. No automatic
further mesh refinement or artificial-core change is justified by this check.

## Curvature hypothesis

Drela's JVL formulation describes a separate curvature-related self velocity.
It is an adjacent implementation, not evidence of historical ASWING behavior.
One saved-array calculation tests its published sign using actual bound-segment
vectors and the explicitly assumed patch area chord × arc interval. Only the
398 interior segments are evaluated; the two endpoint corrections remain undefined.

The resulting Kutta–Joukowski CD change is **+4.44757e−6** over those interior
segments, including only **+1.59940e−7** in the inner 90%. It would increase the
existing discrepancy, and is much smaller than the observed excess. Near the
tip, the shallow-curvature measure reaches 1.619 and force points are off the
bound segment, so the formula's applicability is also limited. Circulation,
profile loads and equilibrium were not recomputed; this is not a corrected
physical solution. See the [source review](isae-sa3-velocity-source.md).

ASWING's documented force/control-point separation is already present. Its exact
historical node array, spline endpoint conditions and circulation representation
remain unproved. The later geometry/accurate-arc work completed the independent
node-to-collocation reconstruction. A [current code-continuity review](../../artifacts/isae/sa3-collocation-audit-20261028/summary.json)
confirms that result still applies within its recorded scope; it identifies no
new geometry fix. Repeating arbitrary option or core sweeps is not supported
by the current evidence.

[Diagnostic figure](isae-sa3-velocity-diagnostic.png) ·
[Captured results](isae-sa3-velocity.json) ·
[Independent audit](isae-sa3-velocity-audit.json) ·
[Curvature analogue](isae-sa3-velocity-curvature.json) ·
[Raw evidence](isae-sa3-velocity-20261025-evidence.zip)
