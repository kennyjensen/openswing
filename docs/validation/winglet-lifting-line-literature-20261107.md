# Lifting-line methods for winglets: expanded literature search

The [further literature addendum](winglet-lifting-line-literature-addendum-20261107.md)
adds Chattot's explicit winglet-junction discussion, Li's bound-field correction,
Gaunaa's 2026 section/force formulation, distributed-vorticity winglet applications,
and a recent interacting-wing core study cross-checked against Drela's rules.

2026-11-07. The strongest new leads concern connected-surface topology and
swept-line force evaluation. None establishes the missing native ASWING
treatment. Keep original ISAE comparisons as the validation target; independent
literature cases diagnose mechanisms rather than replace those comparisons.

| Source and inspected material | Relevant evidence | Consequence for OpenSwing |
|---|---|---|
| [DLR LIFTING_LINE 3.2 manual](https://unicado.pages.rwth-aachen.de/unicado.gitlab.io/documentation/analysis/aerodynamic_analysis/references/LIFTING_LINE_V3.2_UserDoc.pdf), March 2023, pp. 18–19, 58–62, 75–76, 96–97; PDF read, selected pages visually checked | Quadratic circulation with explicit edge coupling. At forks, signed circulation sums balance; all branches are not simply assigned equal circulation. The manual explicitly identifies singular velocity at a swept bound vortex adjoining a continuous wake sheet. Lift/sideforce and Trefftz-plane drag are evaluated separately. Sharp bends have different coupling choices from smooth joins. | Audit branch conservation and force evaluation separately. This is a different formulation, not authority to replace ASWING drag or omit self-influence. The manual also retains collision/singularity limitations. |
| [Reid & Hunsaker, *General Approach to Lifting-Line Theory, Applied to Wings with Sweep*](https://aerolab.usu.edu/publications/journal), Journal of Aircraft 58(2), 334–346, 2021, DOI 10.2514/1.C035994; author abstract and corresponding MachUpX implementation inspected | Local straightening of the effective lifting line and finite near-wake segments perpendicular to it address the swept-line singularity. Reported cosine-grid convergence is approximately second order. | Provides a concrete alternative kernel/near-wake treatment for an independent comparison. It changes the geometry used for induction; it is not a tiny-core adjustment. |
| [Goates & Hunsaker, *Modern Implementation and Evaluation of Lifting-Line Theory for Complex Geometries*](https://doi.org/10.2514/1.C036748), Journal of Aircraft 60(2), 490–508, 2023; [author abstract](https://aerolab.usu.edu/publications/journal), [official developer notes](https://machupx.readthedocs.io/en/latest/developer_notes.html), and retained source inspected | Extends the approach to arbitrary sweep, dihedral and twist with section-property corrections. MachUpX explicitly groups directly connected segments into lifting lines, handles branches separately, and uses receiver-dependent effective geometry. | Its connected-segment handling is worth comparing with our per-logical-beam construction. Neither the native ASWING mapping nor numerical equivalence follows from this. Full journal paper was not accessible in this search. |
| [J. G. Coder, *Accuracy of high-order, discrete approximations to the lifting-line equation*](https://doi.org/10.1017/aer.2023.16), The Aeronautical Journal 127, 1536–1553, 2023; full publisher HTML, especially §§2–3 | Explains why continuous polynomial elements require additional continuity constraints and why split winglets complicate their closure. Presents discontinuous polynomial elements with Gauss-Legendre collocation. The demonstrated accuracy study is restricted to planar wings. | A higher-order basis is not automatically a junction fix. This supplies a systematic discretization comparison, but no demonstrated solution of our swept split-winglet case. |
| [Kleine, Hanifi & Henningson, *Simulating Airplane Aerodynamics with Body Forces: Actuator Line Method for Non-planar Wings*](https://arxiv.org/abs/2209.00096), AIAA Journal, 2023, DOI 10.2514/1.J062398; version 2 PDF, §§II–IV | Explicit unswept winglet and T-tail cases compare nonlinear lifting line with an actuator-line calculation. The authors identify inconsistency between circulation and the velocity used for body forces, and correct that actuator-line inconsistency. They retain limitations near intersections. | Useful geometry/settings for an independent junction control. Their smearing/vorticity correction belongs to the actuator-line formulation and cannot simply be inserted into ASWING. |
| [Gaunaa, Réthoré, Sørensen & Døssing, *A computationally efficient algorithm for the aerodynamic response of non-straight blades*](https://backend.orbit.dtu.dk/ws/portalfiles/portal/6372784/Rethore_paper_ewea2011_paper.pdf), EWEA 2011; §2.1 read via the indexed PDF | Their nonplanar free-wake model evaluates bound-vorticity self-induction through a vortex-lattice calculation and an iterative weighted difference of 3-D and 2-D self-induced velocities. The model also uses a finite viscous wake core. | Another explicit treatment of the singular self-field, distinct from both ASWING and Reid's construction. Rotor/free-wake results do not by themselves certify a fixed-wing ASWING change. |

An additional [Døssing 2007 report, Risø-R-1621](https://backend.orbit.dtu.dk/ws/portalfiles/portal/151422033/ris_r_1621.pdf),
Part 3, examines winglet height, bend radius, spacing and optimal circulation.
Its increasing wake strength near a tighter bend supports distinguishing sharp
and rounded junction tests. These are primarily induced-drag/optimal-loading
studies, not recovered SA-11 operating points.

## What changes in the investigation

The existing [eight-call Fourier check](isae-sa11-winglet-modes-20261107.md)
shows that merely lowering the mode count can permit execution while retaining
large local residuals. The earlier [junction check](isae-sa11-winglet-junction-20261107.md)
shows that equal upper-root circulation would still leave the field of a finite
streamwise connector between offset origins. These findings constrain any new
proposal: neither equality alone nor a smaller Fourier space is enough.

Prioritize these independent checks before another SA-11 parameter sweep:

1. **Topology:** use a straight wing split into collinear pieces, then an
   unswept winglet, then a three-branch junction. Verify source orientations,
   grouped trailing strengths and signed circulation balance at coincident
   origins. With longitudinally offset origins, retain the finite connector
   contribution explicitly. This does not assume the real model's origins
   should be moved or that branch circulation equality is a native constraint.
2. **Force velocity:** compare fixed prescribed-circulation fields under the
   existing documented ASWING geometry, a fully specified generalized lifting-line
   construction, and a resolved finite-chord calculation. Keep their control
   equations and load definitions separate. Check local fields and moments,
   not only integrated lift or drag.
3. **A documented nonplanar control:** Kleine et al. Table 1 specifies main
   span 1, winglet span 0.2, chord 0.1, section slope 2π, zero section drag,
   and angle 1/(2π) radians; §III uses 0.02 control-point spacing. Its printed
   degree value, 9.189°, does not equal the radian expression (about 9.119°).
   Resolve/disclose that inconsistency before claiming numerical reproduction.
   The radian expression is consistent with its stated isolated-section CL=1.
   This case would test junction behavior without SA-11's sweep or transonic
   corrections; it would add no ASWING-reference passes by itself.

These priorities are our inference from the sources and current diagnostics.
They do not establish that native ASWING uses any of the alternative methods.
No production aerodynamic rule, core default, Mach guard, model input or
ISAE completion fraction was changed during this search.

The subsequent [unswept junction control](unswept-winglet-junction-20261107.md)
executes the topology and sharp-corner checks. It verifies signed fork fields
and same-mesh logical partition, but still finds growing bound-induced velocity
at a coincident, unswept 90-degree junction. Kleine et al. explicitly describe
that ideal-junction singularity in §III (PDF p.12) and recommend desingularizing
and smoothing the connection when refining. This additional source detail
supports separating corner behavior from the swept-wake issue; it does not
establish an ASWING-compatible regularization. The new control is not scored
against the paper's curves or counted as an ISAE pass.

The [subsequent generalized-field audit](winglet-generalized-fields-20261107.md)
executes the pinned MachUpX connected-geometry routines on a prescribed
unswept fixture. It demonstrates the effect of connected grouping and records
near-wake joint gaps and unsatisfied section-equation residuals. It is not a
full MachUpX run, a recovered ASWING algorithm or a new validation pass.

The [nonlinear follow-up](winglet-generalized-solve-20261107.md) subsequently
solves those nine section-equation systems. The connected construction keeps
peak speed near 1.10 times freestream and changes lift by 0.152% across a
fourfold span refinement. Loads still differ from the finite-chord control;
this supports further investigation without establishing native ASWING parity.

The [actual SA-11 topology follow-up](isae-sa11-generalized-topology-20261107.md)
distinguishes a structural joint, a shared physical index and a connected
quarter-chord curve. Pinned source-grouping checks expose the extra mapping
needed for offset roots and three-branch attachments; the successful ideal
connected case does not establish a direct production port.

The [SA-11 finite-chord comparison](isae-sa11-finite-chord-20261107.md) further
shows why numerical stability on the ideal geometry is insufficient. Exact
overlap subdivision preserves all unit-source fields, but the ten retained
linear controls still have unresolved force-edge and load refinement behavior.

The [wake-direction isolation](isae-sa11-wake-direction-20261107.md) subsequently
separates a negative-drag symptom caused by the frozen trailing wake from
remaining near-root body fields and close wake/body encounters. It preserves
the distinction between numerical residual checks and physical validation.

## Source access and retained evidence

The DLR manual and Kleine version-2 paper are retained privately under
`.reference/winglet-literature-20261107/`, with SHA-256, URL and UTC metadata.
Only summaries and links belong in the public documentation. Full-text browser
access was available for Coder and the DTU papers; direct PDF download attempts
returned HTTP 403 and are recorded as unavailable. USU's 2021 download and the
2023 journal download were unavailable; author abstracts and official code/docs
support only the claims identified above. No restricted source was obtained.

Existing MachUpX source remains pinned at
`9935476395b205e74612b6dc53d931eb1cad8d5e` in
[`third_party/machupx/SOURCE.json`](../../third_party/machupx/SOURCE.json).
Relevant locations are `wing_segment.py:234` (direct continuation),
`airplane.py:479` (connected groups), `airplane.py:574` (effective geometry),
and `airplane.py:709` (branch grouping). This is a reference implementation,
not an installed runtime dependency or newly validated solver.
