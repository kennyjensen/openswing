# Lifting-line and strip references for the ISAE discrepancies

Selected sources are retained under `reference/third_party` for local inspection
or under `third_party` for verification scripts, with
upstream revisions and hashes in each `SOURCE.json`. These are reference
selections, not new browser dependencies. Drela's published ASWING equations
remain the implementation target.

| Priority / code | What it can help isolate | Review and evidence |
|---|---|---|
| MachUpX and FLOWPanel.jl | Curved/swept source geometry, receiver-dependent singular treatment, section versus force velocity; strongest SA-4 lead | [MachUpX review](lifting-line-source-review-20261030.md), [FLOWPanel review](lifting-line-flowpanel-tasopt-review-20261030.md). Both modify the effective source line; that is not established as ASWING's method. |
| DUST | Circulation-control versus force locations, 2D section correction, polar closure and near-field forces | [Source review](lifting-line-additional-review-20261030.md). Its finite core and stall regularization differ from the ASWING target. |
| OpenFAST/OLAF | Neighboring-width collocation, section-plane normalization, finite-segment arithmetic and core treatment | [Review and executed comparison](lifting-line-additional-review-20261030.md). All 13,020 baseline segment comparisons pass; the separately retained near-singular proximity test shows limitations of the upstream formula. |
| AeroSandbox | Horseshoe signs, factors, force direction and nonlinear section closure | [Review and executed comparison](lifting-line-source-review-20261030.md). All 13,020 shared-geometry horseshoe comparisons pass. This does not validate its different whole-aircraft formulation against ASWING. |
| AVL/JVL, VortexLattice.jl and TASOPT.jl | Adjacent-circulation bookkeeping, near-field force, Trefftz drag and span efficiency | [AVL/JVL review](lifting-line-avl-cn-review-20261030.md), [1,164 force/wake comparisons](vortexlattice-force-audit-20261030.md), [1,032 TASOPT wake comparisons](lifting-line-flowpanel-tasopt-review-20261030.md). Those executed counts pass at matched geometry and circulation. |
| XFLR5 and CN-AeroModels | Straight-wing loading, nonlinear section inputs, polar lookup and drag separation; useful for SA-1/SA-5 | [XFLR5](lifting-line-source-review-20261030.md), [CN-AeroModels](lifting-line-avl-cn-review-20261030.md). Their section laws do not independently authenticate Drela's stall law. |
| Vortex Step Method | Chordwise control/force locations and surface-vortex force treatment | [Review](vortex-step-method-review-20261030.md). Useful formulation comparison; no new ASWING pass established. |
| SHARPy/UVLM and AeroBeams | Shared-edge circulation forces, section frames and transfer to a structural beam | [Review](lifting-line-sharpy-strip-review-20261030.md). Optional strip drag estimates are distinct from a resolved wake calculation. |
| OpenAeroStruct and PyTornado | Mesh, aerodynamic normals, force sampling and near-field load integration | [Review](lifting-line-oas-pytornado-review-20261030.md). Vortex-lattice references, not interchangeable nonlinear lifting lines. |
| Glidersim | Curved lifting-line singularities, projected section speed and endpoint versus material line elements | [Source review](lifting-line-glidersim-vspaero-ladac-review-20261030.md) and [executed audit](../../artifacts/isae/glidersim-section-audit-20261030/report.md): matched velocities agree; its analytic Jacobian has projection/broadcast inconsistencies. OpenSwing passes 72 refined directional checks. No new ISAE passes. |
| VSPAERO | Adjacent-loop circulation differences, near-field/wake force separation and coupled stall | [Additional source review](lifting-line-glidersim-vspaero-ladac-review-20261030.md). Current stall equations differ from older postprocessing descriptions and from Drela's leakage law. |
| LADAC | Nonlinear strip/VLM coupling, quarter-/three-quarter-chord velocity and separate bound/wake matrices | [Additional source review](lifting-line-glidersim-vspaero-ladac-review-20261030.md). Finite closed wakes and explicit geometry adjustments must be distinguished from ASWING. |
| Filtered lifting-line example | Separate grid refinement from prescribed vortex smoothing in a straight-wing control | [Pinned source selection](../../reference/third_party/filtered_llt/SOURCE.json). Source inspected only; no solver execution or ASWING comparison. Lower priority than the curved-wing references above. |
| AeroFuse.jl | Bound-segment force sampling, trailing-only force velocity and separate near-field/Trefftz drag | [Executed qualification](../../artifacts/isae/aerofuse-reference-qualification-20261031/report.md): raw source fails sweep invariance; projected, matched operators agree on all 84 SA-4 fields. Geometric-midpoint wake sampling loses 42 native-output checks. |
| QBlade | Section-polar circulation iteration, wake connectivity and reuse of wake influence | [Additional reference review](lifting-line-aerofuse-qblade-review-20261031.md). Official theory/source guidance reviewed; historical source archive located but not downloaded. |
| TU Delft NLLL | Nonlinear section correction and limitations of force-integrated induced drag | [Additional reference review](lifting-line-aerofuse-qblade-review-20261031.md). Indexed manual found; source site timed out, so no source inspection or execution. |
| PteraSoftware | Bound-center force velocity and shared-edge load allocation | [Pinned source review](lifting-line-ptera-pysailing-review-20261031.md). Includes all horseshoes in velocity; ring loads explicitly avoid shared-edge double counting. Source inspection only, not an executed ASWING comparison. |
| pySailingVLM | Separate control/force points, chordwise circulation differences and complete trailing-leg connectivity | [Pinned source review](lifting-line-ptera-pysailing-review-20261031.md). Includes neighboring sources; finite connecting segments matter when comparing wake origins. Source inspection only. |

The executed checks reduce suspicion of basic vortex arithmetic and wake
sign/normalization errors on the tested geometries. They do not establish
ASWING's exact source/receiver construction, force self-influence convention
or nonlinear section behavior. No reviewed implementation justifies deleting
all adjacent-strip influences.

The [resolved SA-4 turn investigation](../../artifacts/isae/sa4-resolved-turn-20261030/report.md)
also shows that the prescribed bound-velocity logarithm survives local
refinement of the sharp smooth turn. This strengthens the need to resolve
the complete source/receiver convention before importing another code's
regularization. It does not establish the limit of newly solved circulation
or explain native drag differences. The reference reviews add no ISAE passes.

The subsequent [complete material-quarter-chord comparison](../../artifacts/isae/sa4-material-source-20261030/report.md)
tests a specific steady/unsteady document ambiguity by moving the source,
receivers and Trefftz trace together. All 84 solves finish, but the score
falls from 562/588 to 439/588. Independent field and load checks verify the
diagnostic arithmetic. The tested substitution is rejected as an SA-4
correction; the production wind-directed construction remains unchanged.

The 2026-10-31 search also retained the
[filtered lifting-line example](https://github.com/tonyinme/filtered_lifting_line_theory_solution/tree/89ee0210768ed356dede88127f0c34bba7de0813).
Its source defines a uniform spanwise grid, independently selected smoothing
width, polar interpolation and a nonlinear inflow-angle solve. Its `G` is
lift per unit density and span; `Gamma` is recovered separately, so the two
must not be equated in a comparison. The retained solver takes the root
finder's `.x` without checking success; an executed audit would need its own
residual/convergence gate. This is a possible straight-wing filter-limit
control, not an ASWING stall or curved-wing reference. Original source headers
and file hashes are retained. No runtime code or ISAE counts changed.

The highest-value next comparison remains MachUpX/DUST/Glidersim for SA-4/5:
hold circulation and geometry fixed, compare bound and trailing velocities
separately at the actual section and force points, then compare force integrals.
AVL/JVL and VortexLattice.jl provide the corresponding drag-bookkeeping controls.
Only after those operators agree should a whole nonlinear solve be used to
attribute a discrepancy to section closure. These priorities are an assessment
of the existing audits, not a new claim that an OpenSwing error has been found.

The [2026-10-31 complete endpoint solves](../../artifacts/isae/sa4-endpoint-solves-20261031/report.md)
advance the geometry question beyond fixed-circulation sensitivity: both
receiver-on-segment constructions pass 570/588 SA-4 checks, versus 562/588
for the qualified original geometry. Translated nodal endpoints preserve all
SA-1/2/3/5 passing controls; interval-constant offsets lose eight SA-3 drag
checks. All 552 case solves have independent field/load verification. This
makes the translated construction a stronger candidate for source-level
clarification, without authenticating it as ASWING or changing production.

The [local-equation and adjacent-seed follow-up](../../artifacts/isae/sa4-endpoint-local-branch-20261031/report.md)
does not resolve the remaining 7.06° CDi discrepancy: translated endpoints
remain 6.18–6.67% low with cold full-local closure. Convergence improves
from 34/42 to 39/42, including six recoveries and one new 6.55°/N156 failure.
All 336 planned outcomes and both independent audits are complete. Production equations and registered ISAE counts remain unchanged.
