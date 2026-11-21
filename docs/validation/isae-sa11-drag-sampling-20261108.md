# SA-11: separating endpoint placement from force sampling

2026-11-08 UTC. The large total-drag errors on the recent shared AVL mesh
come predominantly from near-field velocity sampling, not a changed solver
or a loss of circulation convergence. With identical vortex endpoints,
**93.45–93.95% of the change in near-field vortex drag** is attributable to
moving its sampling points while holding circulation fixed. Re-solving
circulation accounts for the remaining 6.05–6.55%.

This explains why the [native AVL baseline diagnostic](isae-sa11-avl-baseline-20261108.md)
had substantially higher total drag than the earlier default-grid comparison.
It does not identify the original ASWING mesh or fix the archived discrepancy.
No production equation, default, original input or acceptance target changes.
**SA-11 remains 163/4,592 at 5%.**

## Controlled comparison

The operating condition is 240 m/s, alpha 1°, dynamic PG Mach, frozen
body-x influence, and the original density. Two input sets are retained:
the original baseline and the independently sourced extension slope/drag
properties used in the [earlier diagnostic](isae-sa11-section-inputs-20261107.md).
Only the main wing's `dCLda`, `Cdf` and `Cdp` differ in that alternative;
neither geometry nor stall parameters are changed.

Three mesh/sampling combinations separate two effects:

| Label | Vortex endpoints | Bound/control receivers | Strips |
|---|---|---|---:|
| A | Default whole-beam cosine64 request, plus required property breaks | Whole-beam Glauert-angle midpoint | 70 |
| B | Converted AVL section-by-section cosine grid | Whole-beam Glauert-angle midpoint on those intervals | 64 |
| C | Same endpoints as B | Actual native AVL section-by-section Glauert receivers | 64 |

A→B changes endpoint placement and resulting count while retaining the
whole-beam sampling rule. B→C changes sampling with **identical endpoints,
interval lengths and beam span directions**. The largest B/C receiver
displacement is 4.9916 mm. The same material geometry, physical component,
wake direction, PG mapping and force equations remain in use.

Three previously completed states are reused: A original, A combined, and C
original. Two new solves supply B original/combined. C combined reuses the
previous native-mesh slope-only circulation, verifies its residual with the
new profile inputs, and evaluates its loads; no new circulation solve is
needed for that profile-property change.

## Results

All six states converge, remain below their local Mach limits, and have zero
stalled strips. The archived total CD at this condition is **0.0110238**.
`CDi_near` is near-field vortex drag; the separate Trefftz `CDi` is not an
additional term in total CD.

| Inputs | Sampling | CDi_near | Profile CD | Total CD | Total CD error | Trefftz CDi |
|---|---|---:|---:|---:|---:|---:|
| Original | A | 0.00409326 | 0.00922777 | 0.01332103 | +20.84% | 0.00584311 |
| Original | B | 0.00625926 | 0.00926991 | 0.01552917 | +40.87% | 0.00584706 |
| Original | C | 0.00900187 | 0.00940397 | 0.01840584 | +66.96% | 0.00583773 |
| Extension slope/drag | A | 0.00356941 | 0.00688288 | 0.01045229 | −5.18% | 0.00508851 |
| Extension slope/drag | B | 0.00545009 | 0.00689831 | 0.01234841 | +12.02% | 0.00509816 |
| Extension slope/drag | C | 0.00778116 | 0.00695544 | 0.01473660 | +33.68% | 0.00508295 |

Within each fixed input set, the Trefftz CDi range across A/B/C is below
0.30%. The much larger total-drag variation comes primarily from near-field
vortex drag. Profile drag changes modestly with sampled local velocity.
This is sensitivity evidence, not mesh convergence or a reason to select
whichever grid gives the nearest archived answer.

![Drag components and archived total](../../artifacts/isae/sa11-drag-sampling-r1-20261108/drag-components-v2.png)

Bar labels are total-CD errors; blue diamonds are separate Trefftz CDi values.
[Standalone SVG](../../artifacts/isae/sa11-drag-sampling-r1-20261108/drag-components-v2.svg).

## Fixed-circulation decomposition

For B and C the endpoint-based field operator is identical except for its
receiver coordinates. With C's solved circulation held fixed, the audit
evaluates both bound-point velocity fields and their Kutta–Joukowsky forces.
The subsequent change from C's circulation to B's circulation is accounted
for separately. These mixed fields are algebraic diagnostics; they are not
claimed to satisfy the mixed control-point equations.

| Inputs | Total B→C change in CDi_near | Receiver-only change | Circulation-resolve change | Receiver share |
|---|---:|---:|---:|---:|
| Original | +0.00274261 | +0.00256303 | +0.00017958 | 93.45% |
| Extension slope/drag | +0.00233106 | +0.00219004 | +0.00014103 | 93.95% |

The receiver-only term itself contains substantial cancellation:

| Inputs | Same-strip trailing-leg contribution | Other-strip contribution | Net receiver term |
|---|---:|---:|---:|
| Original | +0.02155853 | −0.01899550 | +0.00256303 |
| Extension slope/drag | +0.01857673 | −0.01638669 | +0.00219004 |

The self-bound segment is excluded consistently; the same-strip contribution
here is its trailing legs. Neither term is removable by this evidence.
Their large opposing values explain the sensitivity of the smaller net drag.
All decomposition identities close within 1e-12 in CD, and reconstructed
velocities agree with the saved production fields within 2e-9 m/s.

## Interpretation against the documentation

Drela's [steady technical description, equations 150–156, pp. 31–32](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf#page=31)
defines the circulation/receiver sampling through the Glauert angle and its
associated beam coordinate. The main wing here is one ASWING logical beam;
its property breaks do not independently declare new beam coordinates.
The current whole-beam rule is retained. Native AVL's separately declared
surfaces produce their own sample distributions, even when those surfaces
share a physical component and identical aerodynamic endpoints.

Thus matching native AVL by supplying its receiver coordinates to OpenSwing
is useful for testing the operator and force laws, but it also changes a
comparison input. Agreement under that explicit mapping does not establish
which receivers the archived ASWING calculation used.

The next relevant evidence is native node/sampling and load-recovery behavior
for the archived setup, alongside the independently identified section-input
conflict. This audit does not justify a tuned vortex core, deletion of self
wake, replacing near-field drag with Trefftz drag, or changing sampling merely
to improve a pass count. Post-stall repairs remain deferred.

## Reproduction

- [Serial driver](../../scripts/verify-sa11-drag-sampling.py),
  [saved-field analysis](../../scripts/analyze-sa11-drag-sampling.py),
  [plotter](../../scripts/plot-sa11-drag-sampling.py).
- [Original three-call plan](../../artifacts/isae/sa11-drag-sampling-20261108/plan.json),
  [continuation and reused-result pins](../../artifacts/isae/sa11-drag-sampling-r1-20261108/plan.json),
  [complete numerical analysis](../../artifacts/isae/sa11-drag-sampling-r1-20261108/analysis.json).

The first new solve completed and saved its full output before a recorder
assertion confused the strip's beam position with its separately exported
velocity receiver. The corrected checks verify both coordinates. That
completed solve was recovered without rerunning it; its elapsed solve time
was not retained. The two remaining calls completed serially with one BLAS
thread. The first plot is preserved; v2 improves annotation legibility.
