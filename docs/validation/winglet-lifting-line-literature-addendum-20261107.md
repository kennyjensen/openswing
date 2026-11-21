# Winglet lifting-line literature: further sources and implementation leads

2026-11-07 UTC. This extends the [earlier review](winglet-lifting-line-literature-20261107.md)
with direct winglet studies, curved-line formulations, distributed wake methods,
and two 2026 papers. The strongest new implementation lead concerns consistent
section velocities and forces. A second independent winglet study explicitly
describes the sharp-junction singularity. Neither establishes the missing native
ASWING treatment of the SA-11 roots.

## New sources inspected

| Source and access | Relevant evidence | Application and limits |
|---|---|---|
| **Chattot (2006), Low Speed Design and Analysis of Wing/Winglet Combinations Including Viscous Effects**, Journal of Aircraft 43(2), 386–389, [DOI](https://doi.org/10.2514/1.15349). Primary paper's full text inspected through its [ResearchGate copy](https://www.researchgate.net/publication/245430357_Low_Speed_Design_and_Analysis_of_WingWinglet_Combinations_Including_Viscous_Effects), especially p. 387. | For vertical winglets, the paper explicitly identifies singular normal velocity at the wing/winglet junction and uses cosine spacing on each element. It distinguishes the optimization solution's strong singularity from a rapid transition over five or six points in the analysis solution. | Direct evidence that a plausible integrated winglet result can coexist with problematic local junction behavior. Its zero winglet sidewash is an **optimal inviscid loading condition**, not a general boundary condition for SA-11. Cosine spacing is not proof that peak velocity converges. |
| **Li et al. (2020), The influence of the bound vortex on the aerodynamics of curved wind turbine blades**, [full paper](https://backend.orbit.dtu.dk/ws/portalfiles/portal/220872251/Li_2020_J._Phys._Conf._Ser._1618_052038.pdf), DOI 10.1088/1742-6596/1618/5/052038. §§2.1–2.4 and 4.1–4.2 inspected. | Evaluating a curved bound vortex on itself produces logarithmic mesh dependence. Their correction uses the three-dimensional bound field at three-quarter chord minus the corresponding infinite two-dimensional bound-line field. The same correction enters the quarter-chord force-direction velocity. They explicitly say this is not a full second-order asymptotic derivation. | A specified alternative to arbitrary core tuning or deleting bound induction. Straight/curved translating wings isolate the mechanism. Their control uses a small finite core and does not demonstrate a sharp three-branch winglet, so this is a comparison method rather than an established SA-11 repair. |
| **Gaunaa, Li & Pirrung (2026), From thin airfoil theory to finite wings: consistent implementation of Lifting Line-based models**, [full paper](https://backend.orbit.dtu.dk/ws/portalfiles/portal/446323265/Gaunaa_2026_J._Phys._Conf._Ser._3224_042030.pdf), DOI 10.1088/1742-6596/3224/4/042030. §§2–5, equations 1–4 and Figure 2 inspected. | Separates the section's loading magnitude at three-quarter chord from its force direction at quarter chord, after subtracting the local two-dimensional disturbance. It also includes Kutta–Joukowski forces on chordwise vortex segments attached to the wing. Their direction up to the trailing edge is explicitly a modeling choice. | Particularly relevant to the remaining force differences. It changes both vortex geometry and force accounting; it is not an extra force that can be appended unchanged to ASWING. Demonstrations use straight/curved finite wings, with 120 spanwise sections and 30 chordwise rows for the VLM reference. No sharp split-winglet reproduction is established. |
| **Bramesfeld & Maughmer (2008), Relaxed-wake vortex-lattice method using distributed vorticity elements**, DOI 10.2514/1.31665; [author-institution abstract](https://pure.psu.edu/en/publications/relaxed-wake-vortex-lattice-method-using-distributed-vorticity-el/) inspected. **Kody, Bramesfeld & Schmitz (2013), An Efficient Methodology for Using a Multi-Objective Evolutionary Algorithm for Winglet Design**, [full paper](https://ts.journals.publicknowledgeproject.org/ts/index.php/ts/article/download/452/425), printed pp. 46–47 inspected. | The first describes continuous distributed wake vorticity without a selectable filament cutoff/core. The winglet application uses quadratic spanwise bound circulation and a wake sheet with linearly varying vorticity. That application prescribes the wake along freestream to reduce cost. | A concrete winglet application of a higher-order lifting-surface method, beyond the DLR manual already reviewed. This motivates an independent continuous-sheet comparison. Robustness of its wake does not prove every bound-edge or sharp-corner singularity disappears. The 2008 full derivation was unavailable; the 2013 method description was accessible. |
| **Ward, De Alwis & Hinman (2026), Examination of flow field and force predictions for closely coupled wings using a lifting line approach**, [publisher full text](https://www.cambridge.org/core/journals/aeronautical-journal/article/examination-of-flow-field-and-force-predictions-for-closely-coupled-wings-using-a-lifting-line-approach/55A55A8945096C5615234E09F4751DC2), DOI 10.1017/aer.2026.10219; wake desingularization discussion and conclusions inspected. Published online 4 September 2026. | Compares finite-core wake models for interacting wings and explicitly mentions ASWING's quarter-chord core. It finds sensitivity in the local flow and discusses the limits of its interaction predictions. | Useful for **wake impingement between distinct surfaces**. Its abbreviated ASWING description omits the spacing lower bound and shared-physical-index exception; Drela's own rules below govern our implementation. It does not settle the attached winglet corner. |
| **Guermond (1990), A generalized lifting-line theory for curved and swept wings**, [publisher abstract](https://doi.org/10.1017/S0022112090001665); **Iosilevskii (1995), Asymptotic theory of high-aspect-ratio arched wings in steady incompressible flow**, [publisher abstract](https://doi.org/10.1017/S0022112095004307). Abstracts inspected; full derivations unavailable. | Guermond uses Hadamard finite-part integrals and derives consistent forces for high-aspect-ratio curved/swept wings. Iosilevskii extends an integral approach from plane curved wings to open/closed circular arcs. | Relevant mathematical foundations for treating the self-field rather than choosing a cutoff. These are not evidence of a ready-made sharp fork treatment. Do not equate a finite-part integral with merely omitting the receiver's own straight segment. |
| **Horcas et al. (2023), Comparison of aerodynamic models for horizontal axis wind turbine blades accounting for curved tip shapes**, [full paper](https://backend.orbit.dtu.dk/ws/files/299641915/Wind_Energy_2022_Horcas_Comparison_of_aerodynamic_models_for_horizontal_axis_wind_turbine_blades_accounting_for.pdf), DOI 10.1002/we.2780; §§2.1 and 2.3 inspected. | Compares lifting line and other models with blade-resolved CFD for swept, dihedral and combined tip extensions. The tip shapes are smooth and the lifting-line solver includes curvature corrections. | Independent support for testing sweep and dihedral together. Smooth rotor tips are a different problem from SA-11's offset, sharply joined upper/lower branches; the paper supplies no direct pass target for them. |

Two additional leads were located: Wickenheiser & Garcia's 2011 nonlinear
Weissinger extension ([author-hosted paper](https://www2.seas.gwu.edu/~amwick/pubs/Wickenheiser%202011%20Extended%20Nonlinear%20Lifting-Line%20Method%20for%20Aerodynamic%20Modeling%20of%20Reconfigurable%20Aircraft.pdf),
DOI 10.2514/1.C031406; indexed introduction/method opening inspected, direct
fetch timed out) concerns planar curved wings; Krebs & Bramesfeld's
[2017 OSTIV abstract](https://ostiv.org/files/ostiv-docs/congress/2017/Ostiv_Book_long_final.pdf)
specifically describes split-winglet design. Neither supplied an inspected
junction algorithm in this pass.

## What Drela actually specifies about a core

The [ASWING technical description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
§4.2, equation 161, introduces a finite core for other-surface influence, with
`epsilon = max(chord/4, interval width)`. The [user guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt),
“Physical index” and “Wake Vortex Core Radius,” adds the decisive qualification:
beams sharing a physical index use **zero mutual core**. Wing plus winglet is
one of its explicit examples. It warns against trailing legs passing near
control points of such connected components.

The bundled SA-11 winglet beams all use physical index 1. Current
[`aero.py`](../../openswing/aero.py) selects zero core for equal physical indices
and uses the configured chord/spacing rule otherwise. Thus the new interacting-wing
paper is not authority to enable quarter-chord cores at all SA-11 junctions.

## Consequences for the next investigation

The following priorities are **our inference**, not claims made by the authors
about native ASWING:

1. Separate the **bound-line/corner field** from the **trailing-wake field** at
   the actual failing receiver. The [saved SA-11 decomposition](isae-sa11-wake-direction-20261107.md)
   already contains examples of each. A change aimed at the wake cannot be
   assumed to cure a body-field peak.
2. Compare the documented ASWING section/force equations with the corrected
   three-dimensional-minus-two-dimensional field on a smooth, prescribed-circulation
   control first. Establish the straight-wing limit before testing a corner.
   The present sources do not resolve how a local two-dimensional section
   should be defined at a three-branch junction.
3. Keep chordwise force contributions tied to the **same vortex representation**
   used to solve circulation. The [finite-chord control](isae-sa11-finite-chord-20261107.md)
   already has such edges, but its force convergence remains unresolved.
   Increasing force quadrature with circulation held fixed would distinguish
   integration error from a singular force model; no such new run was performed
   for this literature addendum.
4. Retain local velocities, distributed forces, total forces/moments and
   independent drag checks through mesh refinement. A stable total lift or a
   small algebraic residual alone does not establish a usable junction model.

The search adds implementation evidence, not a production fix. No aerodynamic
code, example geometry, core default, validity gate, primary comparison fraction
or tracked scope was changed.

## Access record

Dates above are publication years, not search-engine crawl dates. Full-text
claims are based on the browser-readable primary documents identified in the
table. Chattot's text is the authored paper hosted on ResearchGate, not a
discussion or third-party summary. Abstract-only entries are labeled.

The Gaunaa paper's [online appendix](https://doi.org/10.5281/zenodo.18222326)
was located through its reference list but could not be retrieved. The Penn State
Bramesfeld thesis download returned HTTP 403. Direct local retrieval of the
Gaunaa PDF also returned HTTP 403 even though the browser tool supplied its
full text; no local PDF copy or successful figure inspection is claimed.
Access notes and unchanged-source verification are retained privately in
`.reference/winglet-literature-expansion-20261107/`. No new solver runs or
progress observations were needed for this documentation-only expansion.

The subsequent [fixed-circulation force-quadrature study](isae-sa11-force-quadrature-20261107.md)
executes the proposed integration check. Analytically predicted endpoint terms
explain growing root-edge loads, and exact coplanar wake/body intersections
occur in the upper/lower control. Quadrature refinement alone cannot make
that independent force model a usable validation reference.

The subsequent [smooth section-velocity audit](curved-section-velocity-20261107.md)
checks the bound correction on straight, swept and dihedral prescribed-circulation
controls. It confirms logarithmic growth of the on-line field with the current
kernels and much smaller changes with the published correction. It also derives
the restricted linear equivalence between the section relation and Drela's
control-point tangency equation. These results narrow the force-field question
without establishing a replacement for native ASWING or the SA-11 fork.

The [prescribed swept-wake follow-up](swept-wake-limit-20261108.md) separately
tests the continuous-sheet singularity noted by DLR and a chordwise attached-leg
field inspired by Gaunaa et al. The analytic logarithmic increment is reproduced
within 0.024%; the attached-leg control approaches an independent finite
principal-value reference. This is field-level evidence only: it implements
neither the full published force formulation nor an ASWING-compatible root fix.

The [solved attached-leg follow-up](attached-wake-forces-20261108.md) tests
section coupling, force direction and attached-leg forces together on a straight
swept control. Retained VSM source methods check the force and Trefftz formulas.
The results support the importance of consistent force accounting, while
retaining unresolved endpoint fields and a sub-percent drag discrepancy.
