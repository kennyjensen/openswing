# SA-11 reassessment: paper targets and controlled geometry changes

2026-11-08 UTC. The user requested a literature-led reset of the SA-11
investigation. The most useful next direction is a report-consistent
upper-winglet reconstruction and controlled junction-geometry experiments,
with the published force curves as constraints. No solver, browser, Vite or
build was launched for this review. The UserLAnd crash cause remains unknown.

The [authoritative index](aswing-authoritative-references.md) and
[source catalog](aswing-authoritative-sources.json) were consulted first.
The original cases, validity checks, primary scope and **163/9,184** score are
unchanged. The work below is a source comparison, not a new validation pass.

## The paper does supply usable ASWING targets

Jan Part I, Figure 22, printed/PDF p. 39, distinguishes ASWING 5.96 lines from
experimental markers. I rendered and inspected the figure and extracted its
vector paths. Grid-line labels establish the coordinate calibration; no
transform was fitted to the archived values. The middle grid tick on each
axis supplies an additional calibration check. Eight original tables and
the plotting script were checked against their retained source hashes, and
the PDF against the authoritative catalog.

| Figure panel | Quantity | Configuration/sample coverage | Largest absolute figure/table difference |
|---|---|---|---:|
| 22(a), Mach label 0.7 | CL versus alpha | Four configurations at 1°, 3°, 5° | 0.000010405 |
| 22(b), Mach label 0.8 | CL versus alpha | Four configurations at 1°, 3°, 5° | 0.000002406 |
| 22(c), Mach label 0.7 | CD versus CL | Four configurations at CL 0.3, 0.5, 0.7 | 0.000000120 |
| 22(d), Mach label 0.8 | CD versus CL | Four configurations at CL 0.3, 0.5, 0.7 | 0.000000161 |

The samples are far closer than the plotted stroke thickness. The comparison
uses linear interpolation along both the PDF polylines and numerical tables;
it establishes agreement at these 48 samples, not every plotted point.
All 464 extracted vector vertices are retained separately.

All eight slopes computed from the 41-row archived CL(alpha) tables also
round to the figure's printed values:

| Configuration | Figure slope at 0.7, per radian | Figure slope at 0.8, per radian |
|---|---:|---:|
| Wing alone | 4.70 | 5.02 |
| Upper winglet | 4.94 | 5.16 |
| Planar extension | 4.95 | 5.19 |
| Upper/lower winglets | 5.34 | 5.74 |

`Post_traitement.m` adds **0.0064** to raw CD at the 0.7 label and **0.0075**
at 0.8, uniformly across configurations. These known transformations were
applied in the comparison above. The plot's experimental slope annotations
reuse the baseline CSV columns; they must not become additional independent
ASWING targets. The earlier [source audit](isae-sa11-sources.md) records this
and the experimental column-label ambiguity.

Therefore, the .70/.80 tables are useful numerical representatives of the
paper's ASWING curves. Substituting graph readings for those tables would not
remove the current solver discrepancy. The paper can instead constrain the
intended geometry, operating setup, and transformations. This check does not
authenticate the producing `.asw`, mesh, startup settings or extra .75/.78 runs.

Evidence:

- [Source-only audit script](../../scripts/audit-sa11-paper-curves.py).
- [Comparison, calibration and hashes](../../artifacts/isae/sa11-paper-curves-20261108/comparison.json).
- [Extracted paper curves](../../artifacts/isae/sa11-paper-curves-20261108/paper-vector-curves.csv).
- [Inspected Figure 22](../../reference/sa11-paper-review-20261108/isae-figure22-p39.png).

The audit imports only the standard library and PyMuPDF. It ran once and
terminated normally, without importing OpenSwing, NumPy or a solver.

## What the literature and existing evidence favor

1. **Some supplied inputs are inconsistent with the documented case.**
   Figure 40, p. 68, gives upper-winglet twist −4°, while the archived ASW file
   gives +4°. The baseline lift slope is 7.0/rad while the companion models
   use 6.34/rad. Earlier independently prescribed input changes substantially
   improve native AVL/OpenSwing agreement with the archived forces; they do
   not recover the historical input. See the
   [section-input study](isae-sa11-section-inputs-20261107.md) and
   [incidence study](isae-sa11-winglet-incidence-20261108.md).
2. **A sharp junction can have an ill-defined local lifting-line velocity.**
   Kleine, Hanifi and Henningson, §3, explicitly identify the singular ideal
   wing/winglet intersection and recommend a smooth transition with appropriate
   desingularization for finer grids
   ([primary paper](https://arxiv.org/html/2209.00096v2)). This supports a
   geometry experiment; it does not establish native ASWING treatment.
   Drela's [user guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt),
   “Physical index,” requires zero mutual core for a shared wing/winglet index
   and warns about close wake/control-point encounters. A different core
   cannot be introduced as if it were the documented same-surface default.
3. **The physical reference had smooth junction details.** Jacobs et al.,
   [NASA TN D-8473](https://ntrs.nasa.gov/api/citations/19780012121/downloads/19780012121.pdf),
   printed p. 4 / PDF p. 6, describes fillets at the inside junctions and
   rounded outside corners. The same page specifies 4° upper-winglet toe-out
   relative to the fuselage centerline. This is not exactly −4° twist about
   the swept ASW beam: the earlier sign-only conversion gives about 3.35°
   toe-out. Both the drawing interpretation and angle conversion need to be
   explicit. A fillet radius and native computational representation have
   not been established from this passage.
4. **Close integrated forces do not clear the local-flow failure.** The
   [whole-beam study](isae-sa11-whole-beam-polar-20261108.md) obtains formal
   CL/CD errors below 0.731%/0.241% on a disclosed alternative over 0–5°,
   but every state rejects at two winglet roots. These are diagnostic force
   sums, not accepted complete results. Matching the paper's integrated curves
   alone cannot validate the missing local moments or coupled equations.

Our leading inference is that input interpretation and local junction
representation deserve priority over more unconstrained changes to the basic
vortex kernel. Independent filament and native AVL comparisons constrain the
kernel strongly, but native ASWING's force-point treatment is still unverified.
Jan's reported SA-10 three-branch limitation is not evidence that SA-11 failed
in ASWING; Figure 22 contains successful native results that remain our target.

## Proposed next experiments

Start with the **upper-winglet-only .70 case**, at a pre-stall angle such as
1°, using one small serial job per comparison when numerical execution resumes.
The upper/lower fork and extra .75/.78 setup ambiguities remain required work
but need not be mixed into this first diagnosis. Reuse exact saved controls.

| Controlled change | Question it answers | Required distinction |
|---|---|---|
| Reconstruct section planes from the paper's dimensions and stated body-axis incidence; retain the sign-only −4° model as a separate variant | Does the remaining incidence/chord interpretation explain a force bias? | Check actual section planes and normal/streamwise chords; do not fit twist to CL. |
| Small symmetric perturbations of the upper-root attachment geometry at fixed discretization | Are force-point peaks and totals excessively sensitive to geometric proximity? | Keep geometry edits explicit and inspect bound/wake contributions separately. A small edit that merely happens to pass is not a correction. |
| A continuous, smooth upper-winglet transition with continuous quarter-chord position, tangent, chord and incidence | How much comes from the sharp corner versus the offset root legs? | Smoothing only the displayed leading edge is insufficient. A chosen blend length is a diagnostic parameter until supported by geometry evidence. |
| Two discretizations of each fixed transition geometry | Does a geometry change improve numerical stability, or just move the offending sample? | Keep the physical blend length fixed as the grid changes. Retain local speeds, circulation, CL/CD/CDi/CM and rejected outcomes. |

For the smooth transition, first isolate coincident versus original offset
quarter-chord roots so a rounding effect cannot be confused with removing the
53.211 mm offset. Both edits alter the diagnostic geometry. A smooth curved
lifting line can still have self-field convergence problems; this is not a
promise that a fillet alone fixes every swept-wing limit. Preserve the original
case and its failures throughout.

Do not repeat the already-tested 70-micrometre lower-root alignment as a likely
fix: it made the local velocity worse. Nor do prior broad mode/node sweeps,
arbitrary same-surface cores or removing the local-Mach guard have supporting
evidence as native-parity fixes.

## An additional comparison that isolates the winglet effect

Compare **CD(configuration) − CD(wing alone) at the same CL**, alongside the
absolute forces. The common plotting offset cancels exactly. For example,
linear interpolation of the archived curves at CL = 0.5 gives:

| Configuration | Delta CD at Mach label 0.7 | Delta CD at Mach label 0.8 |
|---|---:|---:|
| Upper winglet | −0.00276893 | −0.00288372 |
| Planar extension | −0.00072622 | −0.00069303 |
| Upper/lower winglets | −0.00306291 | −0.00327111 |

These are **ASWING reference increments**, not OpenSwing predictions or new
passes. Their inputs are the checked samples in `comparison.json`. This is a
useful additional constraint on the winglet effect and avoids confusing a
common plotted drag allowance with a solver defect. It does not eliminate
configuration-dependent profile drag or replace absolute-force, local-flow,
moment and original-case validation.

No comparison denominator is changed, and these derived quantities are not
counted again as independent primary passes.

The subsequent [incidence-convention preparation](isae-sa11-angle-conventions-20261108.md)
provides two explicit ASW inputs and scalar geometry verification for the first
proposed experiment. It resolves the angle conversions mathematically while
retaining the uncertainty in the native author's interpretation. The subsequent
[three-case production diagnostic](isae-sa11-angle-response-20261108.md)
reproduces the saved control and shows both incidence alternatives leave the
two rejected roots. Peak local Mach decreases only from 1.534 to about 1.51.
This makes the junction experiments the stronger next lead; it does not yet
establish a correct native treatment or a new primary pass.
