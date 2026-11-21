# Additional force and adjacent-vortex references

2026-10-31. Selected PteraSoftware and pySailingVLM sources have been retained
under `third_party`, with their upstream licenses, exact revisions, download
URLs and SHA-256 hashes. These are vortex-lattice references for specific
operators, rather than equivalent implementations of ASWING's nonlinear
lifting-line equations. This review is source inspection only: neither solver
was installed or executed, and it adds no ISAE passes or production changes.

| Reference | Retained revision | Useful question |
|---|---|---|
| [PteraSoftware](https://github.com/camUrban/PteraSoftware/tree/ba09159f987ac71e57a9192145bfbf906bc5b265) | `ba09159f987ac71e57a9192145bfbf906bc5b265` | Are force-sampling positions and shared-edge load accounting consistent? |
| [pySailingVLM](https://github.com/orgSailingVLM/pySailingVLM/tree/99d53f4833d903e3d1c2d01197efcb33fca8d4b3) | `99d53f4833d903e3d1c2d01197efcb33fca8d4b3` | Are circulation differences, control/force points and trailing-leg origins handled consistently? |

## What the source actually shows

PteraSoftware's
[horseshoe load routine](../../reference/third_party/pterasoftware/pterasoftware/_steady_horseshoe_vortex_lattice_method.py)
evaluates velocity at each bound-segment center (lines 682–687), then computes
`rho * Gamma * cross(velocity, bound_vector)` (699–706). Its velocity routine
sums all horseshoes (622–633), subject to the kernel's core/singularity
treatment. It does not remove sources merely because they belong to adjacent
strips. This also differs from the previously inspected AeroFuse routine,
which uses trailing-only velocity for force recovery. Agreement on the word
"VLM" therefore does not establish an identical force convention.

PteraSoftware's separate
[ring load routine](../../reference/third_party/pterasoftware/pterasoftware/_steady_ring_vortex_lattice_method.py)
explicitly documents an earlier shared-side load double count and omitted
back-edge forces (868–874). The current code assigns half of the circulation
difference to each panel sharing an edge (914–959); the two panel allocations
together represent that edge's full load. This factor of one half allocates
loads between panels. It is not permission to halve neighboring-vortex
induction or apply an extra half factor to a lifting-line force. The trailing
back edge is canceled by its wake horseshoe (961 onward).

pySailingVLM's
[geometry and influence assembly](../../reference/third_party/pysailingvlm/pySailingVLM/solver/coefs.py)
distinguishes three-quarter-chord collocation points from quarter-chord force
points (93–94). Its influence assembly loops over every source ring or
trailing horseshoe (21–48), without an adjacent-strip omission. Its
[force routine](../../reference/third_party/pysailingvlm/pySailingVLM/solver/forces.py)
reevaluates velocity at the supplied force points (82–83) and uses the
chordwise circulation difference for non-leading panels (101–109). This
chordwise ring accounting must not be confused with spanwise cancellation
of the wake legs of adjacent lifting-line strips.

Its [trailing horseshoe](../../reference/third_party/pysailingvlm/pySailingVLM/solver/velocity.py)
includes three finite segments and two semi-infinite legs rooted at the rear
vertices A and D (127–136). Comparing only those rear origins with ASWING's
origins would omit the connecting segments and compare different vortex
systems. The semi-infinite kernel also has an unguarded singular denominator
(75–81), so singular cases need qualification before treating it as a
numerical reference.

## Implication for OpenSwing

These sources strengthen the distinction between **velocity influence** and
**force allocation**. Neither supports deleting adjacent-strip influences.
They suggest checking a complete connected vortex system at identical receiver
positions, then independently checking how its force is integrated or assigned
to strips. No OpenSwing defect was demonstrated in this inspection.

For the remaining SA-4/5 geometry issue, the already retained MachUpX, DUST
and Glidersim implementations remain stronger lifting-line references.
XFLR5 remains useful for straight-wing nonlinear polar closure, although its
stall treatment does not authenticate Drela's leakage law. The
[reference index](lifting-line-reference-index.md) separates those source
reviews from comparisons that have actually been executed. Drela's published
equations remain the implementation target; a different code's correction
requires a mathematical justification before adoption.

The retained selections contain 7 files / 202,263 bytes for PteraSoftware and
7 files / 77,987 bytes for pySailingVLM, excluding the generated manifests.
Their hashes were verified after retrieval. Runtime packages and registered
ISAE results are unchanged.
