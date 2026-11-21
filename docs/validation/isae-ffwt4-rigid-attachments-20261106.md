# FFWT-4 rigid-tip attachment preflight

The two rejected weight attachments in each driver-selected PM2 model belong
to **perfectly rigid tip beams**. This opens a possible physical treatment of
the attachment issue; the current OpenSwing rejection and 4,800 uncomputed
reference values remain unchanged.

All scaled table values were inspected for `EIcc`, `EInn`, `GJ`, `EA`, `GKc`
and `GKn`, along with all bending/torsion coupling tables. The diagonal
stiffnesses are either omitted (infinite defaults) or identically zero input
tables. The [ASWING guide](../../.reference/aswing_doc.txt), near lines
1143–1151 and 1200–1204, defines those zero inputs as infinite stiffness.
All coupling tables are absent or identically zero. This certifies rigidity
over each entire tip, rather than merely sampling a few sections.

## What the rigid-body identity proves

Let the fixed jig position of a point object be `p₀`, and let `a` be a pylon
anchor on a rigid body. Under a common rigid rotation `R` and translation `c`,

```text
p = (c + R a) + R (p₀ − a) = c + R p₀.
```

Changing the representation anchor while retaining the object's physical
position changes neither `p` nor its first and second time derivatives.
Transferring an arbitrary point force `F` and point couple `C` through the
anchor also preserves the total moment about a fixed origin:

```text
(c + R a) × F + R (p₀ − a) × F + C = (c + R p₀) × F + C.
```

These are direct rigid-body consequences of the pylon kinematics in
[Technical Description §3.3, equations 87–92](../../.reference/asw_theory.txt).
The numerical probe uses all six offending original point records, 64
general finite rotations/motions per record, and four representation anchors:
the literal out-of-range position plus both endpoints and the midpoint.
All **1,536 kinematic/wrench checks** agree to roundoff; maximum scaled
difference is **7.08e-16**. No production transformation or force routine is
used as the comparison oracle. A flexible-beam counterexample produces a
0.548 mm point-position difference, confirming that the identity cannot
justify the same operation on a deformable beam.

## What remains unproved

This is a representation preflight, not a native comparison or a production
fix. Equal rigid-body motion and total wrench do **not** by themselves prove
equal internal section loads: relocating a load to an interior anchor can
change the load distribution within a rigid beam. A possible endpoint
treatment must be derived as condensation of an outboard rigid extension
and checked for every retained in-domain force/moment trace, as well as
point mass, rotational inertia, drag, volume, gyroscopic terms and tangents.
Attachment display and source serialization must preserve the original data.

The native executable's handling of out-of-range attachment stations remains
unknown. Even an independently verified physical extension would not prove
that it reproduces that historical input convention. No source model, mass,
physical point position, production equation, mesher or acceptance rule was
changed, and no additional native pass is claimed.

The reproducible probe and its pinned results are
`artifacts/isae/ffwt4-source-audit-20261106/rigid-tip-preflight.py` and
`rigid-tip-preflight.json`. The complete source scope remains documented in
[the source audit](isae-ffwt4-sources-20261106.md).
