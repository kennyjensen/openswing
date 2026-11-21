# SA-11: explicit incidence conventions and prepared inputs

2026-11-08 UTC. Two new incidence-only ASW variants are prepared from the
literal upper-winglet input. Scalar geometry checks establish their intended
angles and mirrored normals; **the preparation itself launched no aerodynamic
run, production-parser test, browser or build**. A subsequent
[three-case production diagnostic](isae-sa11-angle-response-20261108.md)
now checks the parser, frames and aerodynamic effect: both alternatives retain
two rejected roots, with peak normal Mach about 1.51. These are explicit alternatives, not the
authenticated input that produced Figure 22. The primary SA-11 result remains
**163/9,184 at 5%** with no scope change.

This follows the [paper reassessment](isae-sa11-reassessment-20261108.md).
The authoritative reference index and source catalog were consulted again.
The NASA original, ISAE report and supplied input remain distinct sources.

## Why the angle names matter

Jan Part I, Figure 40, p. 68, labels the upper-winglet root and tip twist
−4°. NASA TN D-8473, printed p. 4 / PDF p. 6, describes 4° toe-out relative
to the fuselage centerline. Its Figure 2(b), printed p. 17 / PDF p. 19,
labels a typical winglet section with incidence −4°. Both pages and the
ISAE drawing were visually inspected. These statements establish the sign
and nominal angle but do not establish which conversion the ISAE ASW input
author used. The literal file gives +4° ASW beam twist.

An angle measured in a horizontal cut is different from incidence in the
unswept section plane when the winglet is canted. ASW twist is a third angle,
measured about the swept beam. With the literal upper-winglet axes:

| Input interpretation | ASW twist | Horizontal-cut toe angle | Unswept-section incidence |
|---|---:|---:|---:|
| Literal +4° | +4.000000° | +3.271551° | +3.195870° |
| Prior report-sign alternative | −4.000000° | −3.346032° | −3.195870° |
| 4° toe-out in a horizontal cut | **−4.770283°** | **−4.000000°** | −3.812248° |
| 4° negative unswept-section incidence | **−5.004796°** | −4.199757° | **−4.000000°** |

The horizontal angle is signed positive for the trailing edge outboard, with
the side sign reversed on the mirrored winglet. Negative means toe-out.
The last two rows are deliberately retained separately: neither is labeled
the recovered native producing input, and neither was selected by force error.

Drela's steady description §1.5, pp. 10–11, also distinguishes section
incidence, principal-axis twist and airfoil zero-lift-line angle. The variants
retain the file's `alpha=4.5°` zero-lift offset. Under the existing interpretation
of the c-axis as the section chord axis, these are real incidence changes,
not equivalent coordinate reparameterizations. No camber offset is fitted.

## Scalar construction and checks

For unit beam tangent `s=(sx,sy,sz)`, let `a=sqrt(sy²+sz²)`. The untwisted
local axes from the surface-beam frame are

```
c0 = (a, -sx*sy/a, -sx*sz/a)
n0 = (0, -sz/a, sy/a)
n(theta) = sin(theta)*c0 + cos(theta)*n0
```

For a requested horizontal direction `d`, requiring `n(theta)·d=0` gives

```
theta = atan2(-n0·d, c0·d).
```

For unswept-section incidence `i`, shearing the normal chord along the beam
into the plane perpendicular to its transverse projection gives

```
i = atan(a*tan(theta)),  theta = atan(tan(i)/a).
```

Here `a=0.7984973507003059`. The script independently constructs the normal
by crossing chord and span axes; maximum discrepancy is 1.11e-16. It verifies
the unswept relation using the actual sheared chord, verifies both target
angles to 1e-12 degrees, and checks mirrored normals. The two new twist values
are equal on both sides.

The strict scanner reads only this pinned fixture's two-station geometry
blocks; it is not a replacement ASW parser. A byte-level restoration check
shows that only the four winglet twist tokens differ from the joint-corrected
control. The separately disclosed Joint multiplier correction is retained in
every prepared variant. All axis positions, normal chords, section properties,
physical indices and reference quantities remain unchanged.

Consequently the body-x frozen quarter-chord offset at the upper root is
still **53.210964 mm**. This experiment can isolate incidence effects but
cannot remove the root-origin offset geometrically. It introduces no vortex
core, smooth transition, changed mesh or local-Mach exception.

## Another geometry interpretation to resolve

The retained upper-winglet endpoints give the following values independently
of the new twist choices:

| Quantity | Supplied ASW geometry | NASA description/drawing |
|---|---:|---:|
| Span transverse to body x | 0.210368825 m | Planform span 0.2032 m |
| Leading-edge sweep in the unswept winglet plane | 37.013151° | 38° |
| Aspect ratio using that span and normal-chord/beam area | 2.428319 | 2.33 |

NASA Figure 2(b) gives upper span equal to the 0.2032 m main-wing tip chord,
and the text's stated 2.33 aspect ratio supports a span in the winglet's
planform rather than its vertical projection. The ASW endpoints instead have
**vertical** difference 0.2032 m plus outboard difference 0.05445 m, giving
3.528% greater transverse span. The earlier source audit already flagged the
interpretation; this follow-up quantifies its effect in the supplied input.
The displayed ISAE drawing rounds some dimensions and does not settle the
generating model. These values motivate a separate planform reconstruction,
not combining an unreported geometry change with the incidence experiment.

The quoted area for this calculation is 0.0182245607 m² from the normal chord
integrated along the straight beam. It is not the aircraft reference area or
the full physical surface area of a reconstructed fillet.

## Reviewable files and remaining work

- [Horizontal-toe variant](../../artifacts/isae/sa11-angle-conventions-20261108/horizontal_toe_minus4.asw).
- [Unswept-incidence variant](../../artifacts/isae/sa11-angle-conventions-20261108/unswept_incidence_minus4.asw).
- [Prior −4° control](../../artifacts/isae/sa11-angle-conventions-20261108/report_minus4.asw).
- [Geometry audit, source pins and file hashes](../../artifacts/isae/sa11-angle-conventions-20261108/geometry-audit.json).
- [Preparation script](../../scripts/prepare-sa11-angle-conventions.py), using
  only Python's standard library. It preserves originals and refuses an
  existing destination. Per-variant diffs and the executed script are retained
  beside the files.

The source-only job completed in under one second. The files can be opened
through the workbench's normal file input, but browser import has not been
verified during the UserLAnd execution hold. No current example or default was
replaced. Their aerodynamic effects, residuals, local velocities and paper
comparison remain uncomputed; the prepared angles are not new passes.
