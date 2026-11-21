# SA-11: the upper-winglet twist sign conflicts with the report

2026-11-08 UTC. **ISAE Figure 40 specifies −4° upper-winglet root and tip
twist; the supplied `.asw` specifies +4°.** Changing only that sign in a
temporary native AVL comparison reduces the archived 1° lift discrepancy
from **+4.12% to +0.53%**, and Trefftz induced-drag discrepancy from
**+12.17% to −0.31%**. This is evidence of an input mismatch, not proof of
which input produced the archived result.

The local junction problem remains: both native AVL and OpenSwing produce
fields that exceed OpenSwing's section-normal Mach limit. Neither production
case is accepted. **SA-11 remains 163/4,592 at 5%.** No original or bundled
model, production equation, Mach guard, registered fraction or scope changes.

## Source conflict and angle conventions

- ISAE **Part I, I.4.0, Appendix D, Figure 40, p. 68** labels upper-winglet
  root and tip twist −4°. This was visually checked in the
  [original PDF](../../reference/aswing-authoritative-20261108/isae-part-1-aerodynamics.pdf)
  and the [retained page image](../../artifacts/isae/sa11-winglet-incidence-20261108/isae-figure40-p68.png).
  The archived `KC-135A_geometry.svg` has the same labels. These drawings
  contain geometry dimensions, but no identifiable computational-node markers;
  they do not recover the original discretization.
- Original `Wing_tip_up/wingtip_up.asw` and the
  [bundled inspection example](../../examples/isae-sa11-wingtip-up.asw)
  both specify +4° on beams 2 and 3. The bundled example's previously disclosed
  joint-station repair does not change the surface geometry or properties.
- **NASA TN D-8473, printed pp. 3–4 (PDF pp. 5–6)** defines incidence signs
  and states that the upper winglet toes outward by 4°, with its leading edge
  outboard and its upper surface inboard. This independently establishes the
  physical direction, although the validation target remains the archived
  ASWING result, not the NASA experimental curve.
  [NASA report](https://ntrs.nasa.gov/api/citations/19780012121/downloads/19780012121.pdf),
  [retained page image](../../artifacts/isae/sa11-winglet-incidence-20261108/nasa-incidence-p6.png).

The sign conclusion was checked geometrically, rather than equating two
angle names. Let `s=(sx,sy,sz)` be the unit beam tangent and
`a=sqrt(sy²+sz²)`. The independent section-plane construction is
`c0=(a,-sx*sy/a,-sx*sz/a)`, `n0=(0,-sz/a,sy/a)`, and
`n=sin(theta)*c0+cos(theta)*n0`. It agrees with the production section normal
within **1.11e-16** for both mirrored winglets. A horizontal cut through this
plane has chord direction `(1,-nx/ny,0)`.

| ASW beam-normal twist | Horizontal-cut trailing-edge angle, positive outboard | Physical direction |
|---|---:|---|
| Literal +4° | +3.27155° | Leading edge inward / toe-in |
| Figure-derived −4° | −3.34603° | Leading edge outward / toe-out |

Consequently the sign conflict is real under the documented ASW section
convention. However, **−4° beam-normal twist is not exactly 4° toe-out measured
from the body axis**. This diagnostic checks the figure's sign only; it does
not reconstruct every NASA dimension or resolve that angle conversion.
The main-wing incidence, winglet cant, chord, zero-lift offset and all section
properties remain unchanged. In particular, the upper-winglet `alpha=4.5°`
zero-lift offset is retained and included separately in the AVL conversion.

## Controlled comparison

Two cases were declared before execution: literal +4° and figure-derived −4°.
Both use aircraft incidence 1°, speed 240 m/s, density 1.2256, PG Mach
`240/340.21 = 0.7054466359`, a body-x frozen wake, and 64 one-row native AVL
vortices. Production uses the exact native endpoints and bound/control
receivers, with the normal stall law and local Mach guard enabled.

The [earlier conversion audit](isae-sa11-avl-conversion-20261108.md) supplies
normal-to-streamwise chord conversion and the zero-lift incidence projection.
The two native input files differ in **only four winglet SECTION incidence
entries**. Native endpoints and receivers are bit-for-bit identical across
the two sign choices; OpenSwing/native geometry differs by at most 6.94e-16 m.

The unchanged archived `wingtip_up_Ma_0_70.txt` row at 1° gives
`CL=0.336959`, `CDi=0.00445428`, and total `CD=0.0103591`.

| Upper twist | Native AVL CL | CL error | Native AVL Trefftz CDi | CDi error |
|---|---:|---:|---:|---:|
| +4° | 0.35085378 | +4.1236% | 0.0049964284 | +12.1714% |
| −4° | 0.33873840 | +0.5281% | 0.0044406940 | −0.3050% |

Native AVL has no profile drag in this comparison; its CL is vortex lift,
whereas the archived CL includes profile-force contributions. Native near-field
vortex CD is 0.00509702 / 0.00518370. These are not total-CD predictions and
must not be scored against archived total CD. The two accepted native outputs
also do not establish that their local fields satisfy ASWING's section model.

## The local-flow failure is separate from the twist sign

| Upper twist | OpenSwing/native circulation difference, relative L∞ | Maximum local Mach, OpenSwing | Same diagnostic applied to native AVL field | OpenSwing circulation residual |
|---|---:|---:|---:|---:|
| +4° | 0.12256% | 1.75875 | 1.76171 | 2.15e-15 |
| −4° | 0.07462% | 1.57365 | 1.57574 | 3.68e-15 |

Native velocity is projected perpendicular to the **same ASW beam tangent**
before computing the Mach diagnostic. Thus this is a comparison of retained
fields, not a claim that AVL applies ASWING's local-Mach acceptance rule.
The same excessive root velocity is present in both methods.

Both production circulation solutions are well converged and no sampled
section exceeds its declared lift limit; the closest margins are 12.05 and
25.00 stall-transition widths. Nevertheless, the local Mach guard correctly
rejects both states before reporting physical section loads. Rejected states
are retained only for circulation/field diagnostics. No accepted OpenSwing
CL, total CD or moment is fabricated from them.

The result supports a report/file discrepancy as an explanation for part of
the archived global-load mismatch. It does not resolve the junction velocity,
original mesh, total drag or moment, and it covers one operating point. The
next checks are the remaining pre-stall archived upper-winglet rows and the
ASWING local section-velocity/load convention at the offset junction. The
separate Mach 0.75/0.78 normalization conflicts also remain open.

## Reproduction and verification

- [Fixed-case driver](../../scripts/verify-sa11-winglet-incidence.py) and
  [saved-evidence analyzer](../../scripts/analyze-sa11-winglet-incidence.py).
- [Predeclared cases, angle audit and 156 unchanged input/production/status pins](../../artifacts/isae/sa11-winglet-incidence-20261108/plan.json).
- [Checked results](../../artifacts/isae/sa11-winglet-incidence-20261108/analysis.json).

Two native and two production calls ran serially with one BLAS thread, a
45-second outer timeout and a 768 MiB address-space limit. Native solves
totaled 0.590 s; production calls totaled 0.158 s, excluding setup/import time.
The analyzer runs no new solves. It checks artifact hashes, native process
completion, the input-only incidence difference, identical geometry, the
Mach calculation, stalled-section margins and retained circulation comparison.
Independent reconstruction of native force from the exported vortex fields
matches native CL/near-field CD within **5.56e-17**.
