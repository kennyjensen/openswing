# Further reference codes: VortexLattice.jl and Aeroelasticity.jl

2026-10-30. Two additional source selections were downloaded and inspected.
They provide specific independent comparisons, but this review establishes
no new OpenSwing defect or additional ASWING/ISAE pass. Neither Julia package
was installed or executed. OpenSwing's production equations remain unchanged.

| Reference | Pinned revision | Useful comparison | Limitation |
|---|---|---|---|
| [VortexLattice.jl](https://github.com/byuflowlab/VortexLattice.jl) | `966c2f369ae2ab8dafcea18bbc6187d36b398b45` | Near-field force sampling, Trefftz drag, coincident edges, nonlinear section inputs | Vortex-lattice geometry and polar closure differ from ASWING |
| [Aeroelasticity.jl](https://github.com/byuflowlab/Aeroelasticity.jl) | `255c533083ab5b5f002e525b7aa21542806e6189` | Relative section velocity, aerodynamic axes, distributed beam loads | The inspected lifting-line/beam route assembles independent 2D sections; it supplies no 3D wake interaction |

Eighteen unmodified files (290,887 bytes) are retained under
`reference/third_party/vortexlattice_jl` and `reference/third_party/aeroelasticity_jl`, including
both MIT licenses. Their `SOURCE.json` manifests record immutable source URLs,
SHA-256 hashes and verified upstream Git blob identities. These are reference
selections, not complete packages or application dependencies.

## VortexLattice.jl: force and wake bookkeeping

The steady near-field routine in
[`src/nearfield.jl:38`](../../reference/third_party/vortexlattice_jl/src/nearfield.jl)
samples velocity at the top bound-vortex receiver, sums the surface and wake
influences, and computes force from local velocity crossed with the actual
bound endpoint vector (lines 134–137). For interior chordwise rows it uses the
difference between consecutive panel circulations. The same-surface call
disables its finite-core model; other surfaces use core treatment according
to component identity (lines 82–99).

The bound-receiver overload in
[`src/induced.jl:1248`](../../reference/third_party/vortexlattice_jl/src/induced.jl)
suppresses the receiver's own top edge and the coincident bottom edge of the
preceding chordwise panel. It does not suppress entire adjacent spanwise
strips. This is consistent with the earlier AVL and SHARPy bookkeeping
reviews, and supplies no justification for deleting neighboring influences
from OpenSwing.

Its surface-side force calculation excludes induced velocity
(`nearfield.jl:172–180` and `:202–210`), explicitly following an AVL assumption.
For steady translation without additional velocity, those side forces are
perpendicular to freestream and cannot themselves add freestream-axis drag.
This is an algebraic inference, not a numerical result. It is the same reason
the earlier AVL surface-leg observation was insufficient to explain the gap.

Trefftz geometry is assembled from the trailing-edge row, rotated into wind
axes and projected into a transverse plane in
[`src/panel.jl:512`](../../reference/third_party/vortexlattice_jl/src/panel.jl).
The same file evaluates the two opposite-sign wake filaments and their drag
contribution at lines 581–627; `src/farfield.jl` sums all receiver/source pairs.
This offers a separate implementation for a future comparison at identical
geometry and circulation. It does not establish agreement for OpenSwing's
Glauert sampling, material section-span force vector, or nonlinear solution.

## Its nonlinear route is a different closure

The force routine also computes a separate velocity using streamwise
filaments, excluding spanwise lattice edges. The nonlinear section iteration
uses that field for polar lookup:
[`src/nonlinear.jl:203`](../../reference/third_party/vortexlattice_jl/src/nonlinear.jl),
with section-plane projections at lines 220–238. By contrast, OpenSwing's
ASWING leakage residual uses total relative velocity at its bound-vortex
force point (`openswing/aero.py:470–489`). Different field selection in this
polar-based lattice model is not evidence that ASWING's field should change.

The upstream [nonlinear documentation](https://flow.byu.edu/VortexLattice.jl/dev/advanced/)
reports possible nonphysical wingtip behavior with nonuniform meshes above
75 spanwise panels, and describes a default iteration limit rather than a
guaranteed converged solution. Its code tests the damped circulation update
against tolerance (`nonlinear.jl:238–251`). Consequently, a cross-code test
must check convergence and refinement explicitly; the default result is not
an accuracy reference.

The warning is relevant to SA-4's localized tip sensitivity, but the models
and discretizations differ. It does not demonstrate a common cause, support
switching OpenSwing to uniform spacing, or resolve the archived ASWING gap.

## Aeroelasticity.jl: useful strip and beam checks

In
[`src/models/aerodynamics/liftingline.jl:43`](../../reference/third_party/aeroelasticity_jl/src/models/aerodynamics/liftingline.jl),
each section residual receives its own state and inputs. The retained
GXBeam coupling computes local flow from freestream minus element velocity,
rotates into aerodynamic axes, and transforms sectional forces and moments
back into the beam/body frame before distributed-load integration
(`src/models/couplings/liftingline-gxbeam.jl:72–105`). This route contains no
inter-section Biot–Savart coupling. The upstream
[model description](https://flow.byu.edu/Aeroelasticity.jl/dev/models/aerodynamics/liftingline/)
also describes an assembly of 2D aerodynamic models.

The steady section implementation exposes normal/axial forces, the moment
reference offset, compressibility and profile drag separately in
[`src/models/aerodynamics/steady.jl:26`](../../reference/third_party/aeroelasticity_jl/src/models/aerodynamics/steady.jl).
It is a useful source for auditing axes and load transfer, with its thin-airfoil
assumptions recorded. It cannot validate SA-1 stall or SA-2/SA-4/SA-5 wake drag.

## Priority and outcome

For the remaining steady discrepancies, the most useful references are
MachUpX for curved/swept source geometry; AVL and VortexLattice.jl for paired
near-field/Trefftz calculations; and CN-AeroModels/XFLR5 for nonlinear section
normalization and straight-wing controls. SHARPy, DUST and VSM supply other
shared-filament and force-location comparisons. AeroBeams and Aeroelasticity.jl
are more useful for section/beam coupling than for the current 3D drag gap.

The existing [reference overview](lifting-line-sharpy-strip-review-20261030.md)
links the earlier executed kernel comparisons and the unsuccessful SA-4
force-vector substitution. This review has not rerun either Julia solver or
the ISAE suite. All production Python files and `ISAE_STATUS.md` retain their
pre-review hashes; registered counts and the 3% policy are unchanged.
See the [verification record](../../artifacts/isae/lifting-line-byu-review-20261030/verification.json).
