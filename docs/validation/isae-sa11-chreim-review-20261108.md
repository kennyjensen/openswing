# SA-11: reconcile the wake criticism cited by ISAE

2026-11-08 UTC. The additional source review supports investigating local
winglet-junction velocity, but provides **no verified ASWING correction**.
SA-11 remains **163/9,184 at 5%**. No solver was run for this review, and no
production equations, original inputs or comparison scopes were changed.
SA-2 stall-region work remains deferred.

## Sources and the limit of the criticism

ISAE Part I, **p. 17, §3.4**, cites Chreim's 2019 thesis when discussing
ASWING's quarter-chord, wind-aligned wake. Crucially, Jan also says that this
instability was **not observed in his validation work**. That passage does not
establish that OpenSwing's SA-11 rejection reproduces a native ASWING failure.
The separate junction/circulation discussion on p. 35 must not be substituted
for this qualification.

The original thesis is identified by the
[USP record](https://teses.usp.br/teses/disponiveis/3/3150/tde-05102021-091707/fr.html),
DOI 10.11606/D.3.2019.tde-05102021-091707. Both the landing-page request and a
subsequent direct PDF request timed out. Its full text has **not** been used
as evidence in this review.

The later paper by Chreim et al., **Verification & validation of lifting line
α- and Γ-formulations for 3-D planforms under viscous flows** (2023), was
downloaded from the [University of Strathclyde repository](https://strathprints.strath.ac.uk/83793/).
This is the 23-page accepted manuscript, DOI
[10.1017/aer.2023.9](https://doi.org/10.1017/aer.2023.9), rather than the thesis
cited by ISAE. Page references below are to that manuscript. The PDF is
image-only for our extractor; it was read as rendered pages. The retained
`.txt` contains page markers only and is **not searchable full text**.

## Formulations compared

| Item | Drela's steady ASWING description | Chreim et al.'s α-method |
|---|---|---|
| Wake path | Wind-directed rays from quarter chord, §4.2, pp. 31–33 | Attached legs to trailing edge, then free wake, p. 7, Fig. 2/Eq. 10 |
| Control point | Wind-directed offset from bound point, Eqs. 155–157 | Adjusted point on wing, pp. 8–9, Table 1 |
| Slope factor | `h = (dcl/dalpha)/(4*pi)` | The same factor in Table 1, step 5 |
| Section lift velocity | Full induced field at bound point, pp. 15–16, Eqs. 64–67 | Trailing-vortex field plus freestream at control point, p. 8, Eq. 15 |

The paper's poorly converging Γ-method uses coincident bound/control points
(p. 4), unlike ASWING. Its α-method changes several coupled ingredients;
substituting only its wake or section velocity does not implement that method.
Its convergence examples include sweep and mild dihedral, not the SA-11
offset/forked junction. It reports no native SA-11/AVL comparison. Thus its
convergence results cannot establish either an ASWING defect or an SA-11 fix.

The slope expression was checked in a magnified Table 1 image: it is
`(1/2)*(dcl/dalpha)/(2*pi)`, **not its reciprocal**. This eliminates a possible
transcription ambiguity without changing OpenSwing's existing expression.

## Check against the current implementation and evidence

[Frozen lifting geometry](../../openswing/frozen_influence.py) uses the stated
`dCLda/(4*pi)` offset. [Aerodynamic evaluation](../../openswing/aero.py) keeps
separate control- and force-point fields. Its force velocity contains the
ambient field, all trailing legs and other bound segments; only the receiving
strip's own bound segment is excluded. Lift, section speed and the local-Mach
check use that force-point velocity. These inspected choices agree with the
cited Drela equations; this source review is not a complete implementation
validation.

Drela's user guide explicitly requires zero mutual core for beams with a
shared physical index, giving wing plus winglet as its example. It also warns
about nearby trailing legs and control points. Nothing in the newly read paper
changes that native ASWING prescription or authorizes dropping adjacent sources.

The [matched .70 upper-winglet diagnostic](isae-sa11-winglet-polar-20261108.md)
already obtains native AVL lift/CDi agreement within 0.561%/0.332% using the
report's −4° twist. OpenSwing circulation differs from native AVL by at most
0.082%, yet the production states reject local Mach. These are previously
measured results, not fresh passes. The distinction between integrated loading
and local force-point velocity remains the immediate issue.

Previous [section-velocity replays](isae-sa11-section-velocity-20261108.md)
already show that changing only the bound contribution leaves the offending
wake peaks. The [attached-wake control](attached-wake-forces-20261108.md)
also requires consistent force definitions and is not an SA-11 solution.
The new paper supplies context for those results, not grounds to repeat them.

Continue auditing the actual source/receiver geometry and force interpretation
against native AVL and Drela. The known curved-extension export mismatch is
a concrete remaining conversion defect to address before comparing that
configuration. Recovering undocumented ASWING startup or node settings remains
unresolved; this paper supplies neither. Preserve both these setup uncertainties
and the winglet local-flow failure in the primary comparison.

Provenance: [checksummed source supplement](sa11-chreim-sources-20261108.json),
[local paper](../../reference/sa11-chreim-20261108/chreim-2023-lifting-line-formulations.pdf),
and the [authoritative reference index](aswing-authoritative-references.md).
