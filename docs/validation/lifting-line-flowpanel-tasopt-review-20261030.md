# Additional reference codes: FLOWPanel and TASOPT

2026-10-30. Two additional source selections are retained under `third_party`.
They add specific comparisons for the remaining SA-1–SA-5 discrepancies.
No production equation, acceptance tolerance, or ISAE passing count changed.

| Code | Pinned revision | Useful comparison | Scope limitation |
|---|---|---|---|
| [FLOWPanel.jl](https://github.com/byuflowlab/FLOWPanel.jl) | `28c2e911622b8b7c8965aa7108e4145a9c4c9724` | Nonlinear lifting-line closure, swept/curved source geometry, section and force velocities | Uses Reid/Goates-style effective horseshoes and a different section closure; not an implementation of Drela's equations |
| [TASOPT.jl](https://github.com/MIT-LAE/TASOPT.jl) | `b562a25ddbe0eba446204ec00e1bbd17abca3e17` | Wake-strength bookkeeping, Trefftz lift/drag and span efficiency | A transport-aircraft design model with prescribed loading and wake-contraction assumptions; not ASWING's nonlinear lifting-line solver |

Both selections include their MIT licenses. The 21 files total 329,941 bytes.
Each `SOURCE.json` records immutable download URLs, SHA-256 hashes and verified
upstream Git blob identities. These are incomplete reference selections, not
new application dependencies.

## FLOWPanel: distinct section and force velocity paths

The lifting-line module identifies its theory sources in
[`FLOWPanel_liftingline.jl`](../../reference/third_party/flowpanel_jl/src/FLOWPanel_liftingline.jl).
It is relevant beyond the package's panel-method functionality.

[`liftingline.jl:449`](../../reference/third_party/flowpanel_jl/src/liftingline/liftingline.jl)
constructs a different effective source geometry for each receiver, blending
toward a local straight line. The following `jointerize!` routines add short
trailing joints. Defaults are a blending parameter of 1.0 and joint length of
0.15 chord. This is another implementation of the family of methods already
identified in MachUpX, rather than independent evidence that ASWING uses it.

The force routine in
[`postprocess.jl:24`](../../reference/third_party/flowpanel_jl/src/liftingline/postprocess.jl)
first evaluates section coefficients using the effective-horseshoe solution.
Its default `use_Uind_for_force=true` then recomputes velocity using the
original horseshoes before integrating forces. Setting it false retains the
effective-horseshoe field. It does **not** simply remove induced velocity.
The upstream [Weber sweep example](https://flow.byu.edu/FLOWPanel.jl/stable/examples/ll-weber-aoasweep/)
documents different accuracy tradeoffs between integrated drag and its spanwise
distribution, plus incomplete convergence in its post-stall sweeps.

**Useful inference:** source geometry, section closure and force recovery need
separate audits. Agreement in a vortex kernel alone cannot establish agreement
in drag. For SA-2/SA-4, this suggests comparing those intermediate fields at
fixed circulation before changing an entire nonlinear solver. It does not
justify importing FLOWPanel's velocity switch into ASWING.

Its closure also deserves a specific restriction for SA-5:
[`nonlinearsolver.jl:344`](../../reference/third_party/flowpanel_jl/src/liftingline/nonlinearsolver.jl)
derives speed from an inflow-angle relation that assumes no induced component
along the incident flow. The source explicitly notes the limitation for dihedral
and winglets. Consequently, its complete 45-degree-dihedral result would not be
an unquestioned reference for our remaining SA-5 error. FLOWPanel was inspected,
but its nonlinear solver was not executed in this review.

## TASOPT: an executed Drela-derived Trefftz check

The [upstream repository](https://github.com/MIT-LAE/TASOPT.jl) identifies TASOPT.jl
as originally based on Drela's Fortran TASOPT. Its raw wake routines offer a
useful additional comparison without requiring a full aircraft-design run.

[`induced_drag.jl:158`](../../reference/third_party/tasopt_jl/src/aero/induced_drag.jl)
forms interior wake strengths from differences in adjacent bound circulation,
cancels the symmetric root filament, and retains the terminal tip filament.
[`WakeGeometry.jl:199`](../../reference/third_party/tasopt_jl/src/aero/WakeGeometry.jl)
sums those filaments and their opposite-sign mirror images at each receiver.
The integration at `induced_drag.jl:505` includes the wake-energy half factor,
the symmetric-image factor and coefficient normalization.

The unmodified wake-geometry file and the original parsed definitions of
`calculate_wake_circulation!` and `compute_induced_drag!` were executed in Julia
1.10.10. The harness supplies prescribed circulation to both implementations;
it does not translate TASOPT's arithmetic into Python.

The comparison covers 24 symmetric fields: flat, 45-degree-dihedral and curved
wake traces; 16/64 elements per half-wing; arithmetic/angle-midpoint receivers;
and elliptical/modulated circulation. TASOPT receives circulation normalized
by speed times reference span; OpenSwing receives the equivalent dimensional
circulation on both mirrored halves. Both use the same endpoints and receivers.

**All 1,032 scalar comparisons pass.** They compare normal wake velocity, lift,
induced drag and span efficiency. Maximum absolute difference is
**5.9952e-15**, below the declared `2e-12 + 2e-11*abs(reference)` criterion.
This supports the raw Trefftz signs and normalization on these nonintersecting
fields. It is not a new SA case pass, a stall check, a near-field comparison,
or proof of ASWING's historical setup.

TASOPT's aircraft routine separately scales its assumed circulation to a
specified lift before computing drag (`induced_drag.jl:79–85`). Its documentation
also discusses wake contraction and lift-based normalization. Those features
were excluded from this same-input check and are not missing terms established
for ASWING. The source's near-coincident-point cutoff was not exercised.

## Evidence and next comparison priority

The [comparison results](../../artifacts/isae/lifting-line-flowpanel-tasopt-review-20261030/comparison.json)
include every case. The adjacent Python/Julia harnesses, input/output tables,
dependency manifest and download script retain the reproduction details.
An initial harness run lacked Julia's `Printf` import required by an upstream
display method; its log is retained. Adding that import allowed execution
without modifying upstream source.

The most useful references for further work are now:

1. **MachUpX and FLOWPanel:** compare curved/swept source geometry and distinguish
   the section-solve velocity from the force-recovery velocity.
2. **AVL/JVL, VortexLattice.jl and TASOPT:** isolate force and wake bookkeeping.
   The [earlier executed VortexLattice audit](vortexlattice-force-audit-20261030.md)
   already tested the standalone midpoint-receiver substitution on retained
   SA-2/SA-4 fields and found it insufficient.
3. **XFLR5 and CN-AeroModels:** check straight-wing nonlinear section inputs,
   preserving the distinction from Drela's particular stall law.

No confirmed new OpenSwing defect was found. All production Python files and
`ISAE_STATUS.md` retain their hashes from the start of this review.
