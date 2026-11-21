# Additional source leads: AeroFuse, QBlade and TU Delft NLLL

2026-10-31. AeroFuse's vortex-lattice implementation has been downloaded and
inspected as a pinned reference selection. QBlade and TU Delft NLLL are
additional source/documentation leads. No new whole-solver comparison or
registered ASWING match is claimed here.

| Code | Retrieval / review status | Useful comparison |
|---|---|---|
| [AeroFuse.jl](https://github.com/GodotMisogi/AeroFuse.jl/tree/d073f81cb661edb57fc19a73b0e00aaf34badd83) | 16 unmodified files, 63,350 bytes retained; selected wake routines subsequently executed, whole-aircraft solver not run | Bound-segment force sampling, explicit exclusion of bound-induced velocity from force recovery, separate near-field and Trefftz drag |
| [QBlade](https://docs.qblade.org/src/theory/aerodynamics/lifting_line/lifting_line.html) | Official theory and developer guidance reviewed; older source distribution located, not downloaded | Local velocity / section-polar circulation iteration and wake connectivity; rotor free-wake formulation differs from ASWING's steady construction |
| [TU Delft NLLL](https://aerodynamics.lr.tudelft.nl/~shulshoff/nlll/doc/manual.html) | Indexed manual located; direct manual and source-directory requests timed out, source not inspected | Nonlinear section correction to flow tangency; manual identifies limitations of horseshoe-line force integration for induced drag |

## AeroFuse: force sampling is a formulation choice

The [retained manifest](../../reference/third_party/aerofuse_jl/SOURCE.json) records
revision `d073f81cb661edb57fc19a73b0e00aaf34badd83`, download URLs, hashes and
the upstream MIT license. These files are not browser dependencies.

[nearfield.jl](../../reference/third_party/aerofuse_jl/src/Aerodynamics/VortexLattice/nearfield.jl)
lines 4–15 form `rho * Gamma * (V cross bound_segment)` at the segment
midpoint. The actual call uses `induced_trailing_velocity`, which sums
`trailing_velocity` over **all** source horseshoes in
[residuals.jl](../../reference/third_party/aerofuse_jl/src/Aerodynamics/VortexLattice/residuals.jl)
lines 40 and 50–68. Thus its force velocity excludes all bound segments,
including neighboring bound segments; it retains neighboring trailing legs.
This is stronger than merely removing the receiver's singular self segment.
The influence matrix instead uses complete horseshoes at control points.

This gives a useful comparison of control versus force velocity. It does
not justify deleting bound terms from Drela's section-velocity equations.
Those equations, the force definition, and the line element must be matched
before assigning a discrepancy to an implementation error.

[farfield.jl](../../reference/third_party/aerofuse_jl/src/Aerodynamics/VortexLattice/farfield.jl)
lines 5–23 explicitly construct the wake influence matrix; lines 54–73 apply
the half factor in the induced-drag integral. Inspection also identifies a
qualification for any future audit: `trefftz_plane_quantities` computes
wind-axis vectors and projected lengths/normals, but returns the original
`wake_points` to the velocity routine. That routine uses the complete
three-dimensional distance. The high-level wrapper passes the stored
geometry and freestream angles. A swept/nonzero-incidence comparison must
therefore test consistent projection before treating this routine as an
independent reference. This is a source-level concern, not an executed
Julia failure or an identified OpenSwing defect at the time of that inspection.

The subsequent [executed qualification](../../artifacts/isae/aerofuse-reference-qualification-20261031/report.md)
now reproduces the projection defect in the actual Julia functions: an analytic
strip with unit sweep ratio gives drag 50% low. With explicitly projected
inputs and matched sampling, the source agrees with OpenSwing for all 84
saved SA-4 states. A separate geometric-midpoint sampling comparison loses
42 CDi/efficiency checks (160/168 to 118/168), gaining none. Neither issue is
a correction to OpenSwing. The retrieval manifest retains its original
inspection-only status; the linked report records the later executions.

## QBlade and NLLL: useful, with limited evidence so far

QBlade's [official theory](https://docs.qblade.org/src/theory/aerodynamics/lifting_line/lifting_line.html)
describes a quarter-chord lifting line, section-polar closure, and a connected
free wake. During the circulation iteration, wake induction is evaluated
once while bound circulation changes. That is useful for checking which
matrix terms may be reused without freezing unknown-dependent contributions.
The developer's [source navigation guidance](https://qblade.org/qblade-forum/topic/secondary-development-of-qblade/)
names `QTurbineSimulationData.cpp`, `QSimulation::onStartAnalysis()` and
`QSimulation::gammaBoundFixedPointIteration()`. Its
[SourceForge archive](https://sourceforge.net/projects/qblade/files/Source/)
offers version 0.96 source; that historical archive is distinct from the
current documentation and was not downloaded in this review.

The indexed TU Delft NLLL manual describes a nonlinear correction to a
horseshoe-based flow-tangency equation and cautions about force-integrated
induced drag. Direct source access failed, so no particular implementation
detail or numerical agreement is inferred from that description.

## Implication for the current investigation

MachUpX, DUST and Glidersim remain the stronger references for the SA-4/5
curved-line geometry question; AVL/JVL, VortexLattice.jl and TASOPT remain
the executed drag-bookkeeping controls. AeroFuse adds an explicit different
force-velocity convention to inspect. None changes the target mathematics.

The [completed local-equation follow-up](../../artifacts/isae/sa4-endpoint-local-branch-20261031/report.md)
leaves the SA-4 7.06-degree CDi error at 6.18–6.67% low for translated
endpoints, even with local residuals near roundoff. The tested adjacent-angle
seeds do not recover the reference either. These findings keep geometry,
force definitions and historical setup in scope; they do not establish a
specific cause. Production equations and registered passing counts remain
unchanged.
