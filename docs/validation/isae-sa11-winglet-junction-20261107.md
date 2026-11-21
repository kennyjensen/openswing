# SA-11 winglet junction: placement, wake cancellation and frozen influences

2026-11-07. Ten small serial native calls and five saved-field analyses narrow
the winglet Mach failure. No production aerodynamic rule, input geometry, ISAE
comparison scope or pass count changes. The full application remains incomplete.

## The endpoint construction agrees with an independent reconstruction

For the five rejected frozen-influence states, the driver reconstructs all bound
endpoints, force points and control points using independently transcribed
straight-beam endpoint coordinates, linear chord distributions, the analytic
Glauert midpoint and steady equations 155–157. It does not use the production
interpolation or geometry helpers for these predictions. The maximum coordinate
difference is **1.416e-15 m**.

At each upper-winglet root, its bound endpoint is **53.210964 mm downstream** of
the main-wing endpoint, with identical y and z. At each lower-winglet root, the
bound endpoint is **25.901302 mm upstream** and **0.070 mm lower** than the main
wing's endpoint. These offsets follow from the supplied coordinates, chords and
the published quarter-chord placement; they are not a rendering discrepancy.
Agreement with these formulas does not establish unreported native ASWING
junction treatment or physical fidelity of the idealized sharp junction.

## Nearly continuous circulation does not cancel the whole root field

The upper model's two root trailing legs are collinear under zero-angle frozen
influences, but start at different x positions. Their sum can be written exactly
as a finite streamwise segment between those origins plus a downstream ray
carrying the difference in circulation. This is an identity for the existing
wake field, **not an extra vortex added to the model**.

At the worst upper-winglet force point:

| Requested intervals/beam | Main-wing root circulation, m²/s | Winglet root circulation, m²/s | Equivalent finite-segment speed, m/s | Circulation-difference ray speed, m/s |
|---:|---:|---:|---:|---:|
| 48 | 1.88935209 | 1.88434737 | 1213.72788 | 10.92855 |
| 96 | 1.88152547 | 1.87967403 | 4834.48204 | 16.17051 |

The relative circulation jump decreases from about 0.265% to 0.0984%, while
the finite-segment contribution grows roughly fourfold. Thus imposing equal
root circulations alone would retain the dominant term. The independent
finite-line expression agrees with the difference of the two root rays.
Other wake and bound contributions remain in the actual total field.

## Frozen/current-wind comparison

All calls use 30 m/s, alpha 5 degrees, beta zero, automatic PG Mach, default
stall properties and core ratio 0.25. Requested interval counts apply per beam;
mandatory breaks may increase actual counts. No parameters are fitted to a
reference curve.

| Model | Intervals/beam | Frozen influences: maximum local Mach | Current-wind influences: maximum local Mach |
|---|---:|---:|---:|
| Upper winglets | 24 | 0.919871, computed | Not requested |
| Upper winglets | 48 | 3.593822, rejected | 0.181903, computed |
| Upper winglets | 96 | 14.249293, rejected | 0.353519, computed |
| Upper and lower winglets | 24 | 4.484723, rejected | Not requested |
| Upper and lower winglets | 48 | 10.357742, rejected | 3.048750, rejected |
| Upper and lower winglets | 96 | 21.318853, rejected | 3.469369, rejected |

The [ASWING User Guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt),
**Fast,Slow Vortex-Lattice Model — F**, recommends considering current-wind
influences for close surface/wake interactions. This is an existing documented
option, available by clearing **Freeze aerodynamic influences (K/F)** under
**Circulation representation**.

For the two computed current-wind upper-winglet states, N48→N96 changes CL by
0.156%, CD by -1.617%, CDi by 0.0300%, and Cm by 0.145%. The largest local
velocity moves to the winglet tip and nearly doubles. Integrated coefficient
stability and successful execution therefore do not establish local-flow
convergence. These low-speed checks also do not establish the 240–272 m/s
archived SA-11 comparisons. No workaround is established for the upper/lower
model.

## The small core actually present in AVL

The AVL primer describes no finite core within a component. The retained
official **AVL 3.52** source has an additional numerical-scale detail:
[`aic.f:99`](../../reference/third_party/avl/src/aic.f) sets a default radius of
`0.0001 * projected_strip_width` before choosing a larger core for other
components. Its active `VORVELC` wake formula uses the Leishman fourth-power
radial factor. The retained file was verified against its official-archive
manifest.

Applying that radius and wake factor to each original source leg, at the same
saved circulation and rejected receiver, changes total wake velocity by at
most **1.127e-9 relative** across the five saved states. The original wake
sum is independently reconstructed first. This is a prescribed-field check,
not a full AVL solve, a bound-core comparison or a new equilibrium. It shows
that AVL's tiny numerical core would not materially soften the observed wake
spikes. A chord-scale core within this shared physical surface would be a
different modeling choice, contrary to ASWING's documented physical-index rule.

## Remaining work

The simple endpoint-construction and failed-circulation-carryover explanations
are not supported by these checks. The upper model exposes a near-singular
force field from longitudinally offset root legs in the frozen approximation;
unfreezing removes that particular maximum but retains the swept-tip refinement
problem. The lower model has an additional root-height mismatch and persistent
large root velocities. Before changing equations, resolve how native ASWING
treats force velocity at sharp connected surfaces and how its original NODE
distribution and influence setting differed. Check any proposed treatment
against the published force law and the unswept, swept and joined-surface
limits, and propagate justified changes through loads and derivatives.

The [subsequent root-height isolation](isae-sa11-winglet-root-height-20261107.md)
closes the lower attachment's 70-micrometre height gap in temporary copies only.
All four changed states still reject, with larger local velocities on both
meshes and with either influence setting. Closing this gap is not a sufficient
repair; the original geometry remains preserved.

Evidence:

- [Six-call plan](../../artifacts/isae/sa11-winglet-junction-20261107/plan.json),
  [driver](../../artifacts/isae/sa11-winglet-junction-20261107/run.py),
  [results](../../artifacts/isae/sa11-winglet-junction-20261107/results.json).
- [Saved-field analysis](../../artifacts/isae/sa11-winglet-junction-20261107/analysis.json)
  and [reproducer](../../artifacts/isae/sa11-winglet-junction-20261107/analyze.py).
- [Four-call current-wind plan](../../artifacts/isae/sa11-winglet-junction-20261107/unfrozen-plan.json),
  [driver](../../artifacts/isae/sa11-winglet-junction-20261107/unfrozen.py),
  [results](../../artifacts/isae/sa11-winglet-junction-20261107/unfrozen-results.json).
