# Additional lifting-line and strip-code references

2026-10-30. Three additional source selections are retained under `third_party`.
Each selection contains original license material and a `SOURCE.json` with the
upstream revision, download URLs and SHA-256 hashes. These are source reviews;
none of the complete external solvers has been run in this investigation.
No OpenSwing equations or ISAE passing counts change.

| Reference | Revision | Most useful comparison |
|---|---|---|
| [Glidersim](https://github.com/pfheatwole/glidersim) | `0fdec89efa87be6f805ea17dc9e0ddb79792b755` | Curved lifting lines, self influence, section-plane velocity and circulation closure. |
| [VSPAERO](https://github.com/OpenVSP/OpenVSP) | `5240ef210f41c5d6aeed0ba7687f6fab0ca0cafb` | Shared-edge circulation, near-field force versus wake force, and coupled stall treatment. |
| [LADAC](https://github.com/iff-gsc/LADAC) | `1a295a82ecdf70acfc296e959cc011cf12eedbf4` | Nonlinear strip/VLM coupling, quarter-chord versus three-quarter-chord velocities, and wake bookkeeping. |

## Glidersim: the most relevant new curved-wing lead

The [Phillips implementation](../../reference/third_party/glidersim/src/pfh/glidersim/foil_aerodynamics.py)
supports sweep and dihedral. Its documentation explicitly identifies divergent
induced velocity as segment lengths approach zero (lines 129–131). An optional
outer-span polar clamp addresses large tip incidence, but this is not evidence
for an ASWING correction.

The source places nodes and receivers on the quarter-chord curve (144–146),
omits only the receiver's own bound segment (174–183), and retains both trailing
legs (215–229). Section incidence uses projected chordwise/normal velocities;
the nonlinear residual uses their squared norm (231–260). Inviscid force uses
circulation times the cross product of velocity and the straight endpoint
line element (418–420). That line element and its area definition differ from
OpenSwing's material-section integration on a curved beam.

This makes it useful for isolating geometry and velocity definitions in SA-4/5.
It does not justify removing adjacent strips. The subsequent
[executed section audit](../../artifacts/isae/glidersim-section-audit-20261030/report.md)
confirms that its analytic Jacobian retains full-speed terms inconsistent with
the projected residual and broadcasts a speed ratio over source columns.
The same audit verifies OpenSwing's actual Jacobian on eight saved SA-4/5
fields and agrees with the matched upstream velocities. This is evidence about
the tested operators, not a full Glidersim solve or an ASWING correction.

## VSPAERO: inspect the current equations, not older descriptions

The retained [edge routines](../../reference/third_party/vspaero/src/vsp_aero/Solver/VSP_Edge.C)
separate full-velocity force and downwash force (3693–3721).
The [solver](../../reference/third_party/vspaero/src/vsp_aero/Solver/VSP_Solver.C)
forms ordinary edge circulation from the difference between adjacent loop
circulations (34781–34782). Its wake-force integration uses trailing edges
(29651 onward). These are useful independent checks of circulation bookkeeping
and force sampling, after reconciling orientation and normalization conventions.

The current stall model includes a stall-factor residual, or an explicit relaxed
update, coupled to trailing vorticity (27570–27723). Its transition function is
a clipped cubic smoothstep over a normalized loading interval of 0.95–2
(27814–27835). It therefore cannot authenticate Drela's leakage law or supply
replacement stall constants for SA-1. Treating this revision as merely an older
postprocessing lift cap would misdescribe the source.

VSPAERO is primarily a vortex-lattice/panel reference, not an identical lifting
line. A controlled force/wake comparison is more informative than comparing
unmatched whole-aircraft drag coefficients.

## LADAC: explicit distinction between velocity locations

LADAC's [wing module](../../reference/third_party/ladac/aerodynamics/vlm_wing/README.md)
combines spanwise vortex discretization with nonlinear section aerodynamics.
[Local inflow](../../reference/third_party/ladac/aerodynamics/vlm_wing/state/aero/wingSetLocalInflow.m)
separates quarter- and three-quarter-chord motion velocities, including pitch
and structural motion.
[Circulation coupling](../../reference/third_party/ladac/aerodynamics/vlm_wing/state/aero/wingSetCirculationUnsteady.m)
uses section lift to alter aerodynamic normals, with separate bound and wake
influence matrices. Its induced-velocity recovery offers distinct induced-angle
and Trefftz-based paths (242 onward).

The [lifting-line ring helper](../../reference/third_party/ladac/aerodynamics/vlm_wing/vlmVoringsLlt.m)
uses common neighboring endpoints and finite closed rings extending along the
x axis. [Downwash evaluation](../../reference/third_party/ladac/aerodynamics/vlm_wing/wingGetDownwash.m)
chooses a wake length of ten spans. This is not the same boundary condition as
an exact semi-infinite wake. The main influence routine also has explicit
sideslip geometry adjustments. These differences must be accounted for before
interpreting disagreement as an OpenSwing error.

The SE2A Aviation 2023 repository led to this library through its submodules;
the retained revision is current LADAC, not a claimed reproduction of that
paper's exact historical dependency state.

## Additional candidate and diagnostic priority

[QBlade's published LLFVW description](https://docs.qblade.org/src/theory/aerodynamics/lifting_line/lifting_line.html)
is another useful reference for polar/circulation iteration and connected wake
nodes. Only its documentation was reviewed here; its source was not downloaded.

The next useful comparisons are local: hold geometry and circulation fixed,
separate bound and trailing contributions, and compare the section closure and
force integral independently. For SA-4/5, Glidersim complements the existing
MachUpX/DUST reviews. For drag bookkeeping, VSPAERO complements AVL/JVL and
VortexLattice.jl. All corrections still need support from ASWING's equations.
These reviews establish neither a new OpenSwing bug nor a new ISAE pass.
