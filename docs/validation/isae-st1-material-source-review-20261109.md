# ST-1: original material properties and remaining input conflicts

**Follow-up:** the [identical cross-ply retry](isae-st1-cross-modal-20261109.md)
now completes on both meshes and supplies four accepted frequency matches.
The subsequent [thin-blade study](isae-st1-thin-modal-20261109.md) adds nine
more matches, bringing current modal coverage to **20/22**. The original source-review and stopped
attempt record below are preserved.

The existing mechanics evidence remains **201/201 static coordinates and
7/22 named modal frequencies**. This source review adds no accepted comparison
and changes no solver equation. It makes a physical cross-ply reconstruction
explicit and narrows the thin-blade setup uncertainties.

## Primary source

ISAE Part III's appendix, p. 51, specifically cites Tables 5.1 (p. 100) and
5.2(a) (p. 124) of Pierre J. A. Minguet's 1989 MIT thesis, *Static and Dynamic
Behavior of Composite Helicopter Rotor Blades under Large Deflections*.

The thesis is now in the visible reference library:
[PDF](../../reference/st1-minguet-1989/minguet-1989-thesis.pdf),
[text](../../reference/st1-minguet-1989/minguet-1989-thesis.txt),
[download provenance and checksum](../../reference/st1-minguet-1989/source.json),
[text extraction checksum](../../reference/st1-minguet-1989/extraction.json).
Publisher: [MIT DSpace](https://dspace.mit.edu/entities/publication/1cc60ddd-d47e-41f8-8aaf-fa49d041f6d9).
SHA-256: `4ee59d32409a3becc9f7ffa0efc2fede65c03c079c8770084296ce8a7cdc9349`.

Both table images were inspected:
[p. 100](../../reference/st1-minguet-1989/page-100.png) and
[p. 124](../../reference/st1-minguet-1989/page-124.png).
In particular, the thin-blade E22 entry is **3.0 × 10⁵ N**, not 10⁶ N;
the scan resolves an ambiguous text extraction. This thesis supports material
and setup interpretation; its numerical predictions and experiments are not
substituted for ASWING validation targets.

## Property conflicts

| Property | Original modal ASW file | ISAE Part III, p. 52 | Minguet | Interpretation |
|---|---|---|---|---|
| Cross-ply normal shear stiffness | Raw 2.9×10⁵ N with multiplier 10⁻⁵, giving 2.9 N | 2.9×10⁵ N, Table 7 | 2.9×10⁵ N, pp. 100/124 | The report/theoretical specimen differs materially from the altered file. |
| Cross-ply chordwise shear stiffness | 8.7×10⁶ N | 2.6×10⁵ N, Table 7 | 8.7×10⁶ N, pp. 100/124 | Original raw file agrees with the thesis; retain the conflicting ISAE value. |
| Cross-ply mass per length | 0.0683 kg/m | 0.0795 kg/m, Table 9 | 0.0683 kg/m, p. 124 | Original raw file agrees with the thesis. |
| Cross-ply chord-axis inertia per length | Raw 1.31×10⁻⁸ with weight multiplier 1 | 1.31×10⁻⁸ kg m, Table 9 | Polar inertia only | Physical mass inertia requires the gravity conversion in the weight-based ASW column. |
| Cross-ply normal-axis inertia per length | 5.13×10⁻⁶ kg m | 5.3×10⁻⁶ kg m, Table 9 | Polar inertia 5.13×10⁻⁶ kg m | Axis inertia and polar inertia are not exactly interchangeable. Preserve the original raw ASW entries. |
| Thin-blade mass per length | Raw 0.0238, with negative gravity multiplier | Positive 0.0238 kg/m, Table 9 | Positive 0.0238 kg/m, p. 124 | Negative inertia is not the physical specimen; generating up/down inputs remain unavailable. |
| Thin-blade bend–twist coupling magnitude | 0.00632 N m² | 0.632 N m², Table 8 | 0.00632 N m², p. 124 | Thesis and raw file agree; report entry differs by 100. File coupling sign still needs orientation interpretation. |
| Thin-blade chordwise shear stiffness | 2.7×10⁵ N | 2.7×10⁵ N, Table 7 | 3.0×10⁵ N, p. 124 | Preserve the documented ASW value when comparing with ASWING. |
| Thin-blade inertia | Axis entries 6.22×10⁻¹⁰ and 1.91×10⁻⁶ kg m | Same, Table 9 | Polar inertia 1.66×10⁻⁶ kg m | Do not replace the ISAE inputs with thesis values to improve a frequency match. |

The cross-ply scale row additionally has an unnamed sixteenth value for fifteen
named columns. A derived input removes that surplus value, restores the
documented normal shear stiffness, and converts the chord-axis inertia from
mass to weight units. All raw tabulated property numbers remain unchanged.
This is a declared reconstruction, not evidence of the exact historical input
or executable behavior. The original archive remains unchanged.

## Bounded reconstruction attempt

[The new runner](../../scripts/verify_st1_cross_modal.py) reuses the prior
modal solver request, physical checks, mode classifier and saved matrix
residual checks. Its [plan](../../artifacts/isae/st1-cross-modal-reconstruction-20261109/plan.json)
pins the sources, derived input and all production modules before execution.
It declares the same four published cross-ply frequency targets on 40/80
cosine meshes, count 12, fixed-frame vacuum and self-weight equilibrium.
No frequency was used to select a material parameter.

The first attempt reached the 25-second wall limit during startup/input
preparation, **before the modal dispatch**: it wrote `model.asw`, but no request,
matrix or result. Its [terminal record](../../artifacts/isae/st1-cross-modal-reconstruction-20261109/job-0/terminal.json)
preserves exit 142. The exact startup substep was not instrumented. This is
neither a frequency mismatch nor measured solver time. No refinement job was
started, and no process remains running. These four targets remain pending;
the reconstruction has not earned any pass.

## What this means for the tests

The strongest result remains the nine complete static curves across four
layouts. The 201 displacement coordinates sample those curves; they are not
201 independent structural experiments. The pooled 208/223 count is a progress
measure, not a percentage probability that the mechanics is correct. Read the
static and modal components separately.

For modes, a family-activity cutoff is a diagnostic convention, not an ASWING
definition. Mixed modes can carry substantial torsion without being
torsion-dominant. Minguet discusses this issue on pp. 127–128. The existing
95 Hz label conflict should therefore remain an unresolved correspondence,
not be interpreted alone as proof of a 44% structural-model error. The 5%
frequency allowance, mesh/shape checks and eigen-equation residuals continue
to serve different purposes; loosening numerical checks would not resolve a
missing setup or mode identity.
