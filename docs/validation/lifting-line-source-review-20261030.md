# Independent lifting-line source review

2026-10-30. Three additional open implementations have been downloaded as
small, unmodified, revision-pinned source selections under `third_party`.
They supply independent arithmetic and formulation comparisons; none is an
ASWING reference executable. No production equation or ISAE score changes.

| Code | Retained revision | Useful comparison | Important difference from the target ASWING formulation |
|---|---|---|---|
| [MachUpX](https://github.com/usuaero/MachUpX) | `9935476395b205e74612b6dc53d931eb1cad8d5e` | Curved/swept lifting-line singularities, local velocity, nonlinear section closure | Uses a different effective lifting line for each receiver and jointed trailing vortices. These modifications are not established by Drela's published equations. |
| [AeroSandbox](https://github.com/peterdsharpe/AeroSandbox) | `edad83dd8bb6108dbb1b54aa76a6b34695844613` | Horseshoe arithmetic, force direction, section-speed normalization and nonlinear closure | Straight-segment midpoints, bound-segment force vectors, NeuralFoil section data, and a core parameter; wake alignment must be selected explicitly. |
| [XFLR5](https://sourceforge.net/p/xflr5/code/1506/tree/trunk/xflr5/) | SVN `r1506` | Classical straight-wing induced angle, nonlinear polar lookup, separate profile and induced drag | Its LLT is a classical spanwise formulation with small-angle induced-drag recovery, not ASWING's general curved-beam velocity/tangency system. |

## Strongest lead: MachUpX's treatment of singularities

The authors' [2021 paper abstract](https://digitalcommons.usu.edu/mae_stures/26/)
specifically identifies failure of conventional numerical lifting-line methods
to converge under refinement for swept wings and sideslip. The code provides
concrete mechanisms to inspect:

* [airplane.py](../../third_party/machupx/machupX/airplane.py), lines 569–647,
  blends the source line toward the tangent at each receiver and places short
  trailing segments normal to the resulting local tangent. Thus the source
  geometry depends on which receiver is being evaluated.
* [scene.py](../../third_party/machupx/machupX/scene.py), lines 520–541,
  excludes the receiver's own bound segment but retains bound contributions
  from other strips and both joint segments. Lines 590–634 add the trailing
  rays. Removing all neighboring bound-vortex contributions is not its method.
* Lines 732–792 use the total velocity projected into the local section plane
  for section scaling by default. Lines 927–952 recover inviscid forces from
  circulation and the cross product of local velocity with a line element.

Defaults are `joint_length=0.15` chord and `blending_distance=1.0` in
[wing_segment.py](../../third_party/machupx/machupX/wing_segment.py), lines
101–103. The [input documentation](https://machupx.readthedocs.io/en/latest/creating_input_files.html)
warns that shorter values can harm numerical convergence and that results
depend somewhat on these parameters. They are different modeling assumptions,
not corrections we can insert merely to improve an ISAE score.

This is relevant to our existing curved-wing logarithmic-velocity evidence and
the new [SA-4 localization](../../artifacts/isae/sa4-spacing-localization-20261030/report.md).
At N2048, the 95–98% material-semispan region accounts for most of the remaining
modified-spacing prediction error in all six retained loadings. This suggests
a focused comparison of local source curvature, receiver placement and force
integration. It does not prove that MachUpX's treatment explains the native
SA-4 mismatch. Drela's Eqs.154–160 still define the implementation target.

## AeroSandbox: a direct arithmetic comparison now passes

Its [nonlinear lifting-line source](../../reference/third_party/aerosandbox/aerosandbox/aerodynamics/aero_3D/nonlinear_lifting_line.py)
places force receivers at straight bound-segment midpoints (lines 275–280),
forms the nonlinear section equation at those points (340–399), and applies
`rho * Gamma * (V cross bound_segment)` for inviscid forces (406–430).
This differs from OpenSwing's Glauert-weighted force receiver and material
section-span integration. Its current section-angle and speed projections
also differ from OpenSwing's direct section-plane norm and Drela leakage law.
Neither solver's whole-aircraft outputs should be compared without recording
these differences and matching the section data.

The pinned [horseshoe routine](../../reference/third_party/aerosandbox/aerosandbox/aerodynamics/aero_3D/singularities/uniform_strength_horseshoe_singularities.py)
was executed, with zero core, on **13,020 shared-geometry velocity comparisons**:
512 deterministic random geometries at each of three length scales, plus all
other-horseshoe force-point influences and all control-point influences in the
six retained SA-4 baseline states. All 15 groups pass a 2e-8 scaled-vector
criterion; the largest discrepancy is **5.59e-12**. This reduces suspicion of
a basic non-self horseshoe sign/factor error on those geometries.

The [harness](../../artifacts/isae/lifting-line-source-review-20261030/compare_horseshoe.py)
loads only the upstream arithmetic function, with NumPy operations and a shape
assertion shim. It does not install or run AeroSandbox's nonlinear solver.
Self-bound force-point terms are excluded from this comparison. No equivalence
of finite-core models, refined near-singular fields, section closure, or global
drag has been demonstrated. [Complete results](../../artifacts/isae/lifting-line-source-review-20261030/horseshoe-comparison.json)
retain every group and source/input hash.

## XFLR5: useful mainly for SA-1 and straight-wing controls

The official [LLT source](../../reference/third_party/xflr5/xflr5v6/xflanalysis/plane_analysis/lltanalysis.cpp)
uses its classical `Beta` influence factors (165–181), relaxed induced-angle
iteration and section-polar lookup (488–553), and integrated
`cl * (-induced_angle)` for induced drag (234, 292, 330). Profile drag is
looked up and integrated separately. This offers a separate route for checking
straight-wing loading and drag normalization. It does not independently
validate ASWING's high-angle stall law or SA-4's curved-wing singular treatment.

## Retained evidence and next work

Each source directory includes `SOURCE.json`, upstream URLs, exact revisions,
file hashes and original license material. MachUpX and AeroSandbox use MIT
licenses. The selected XFLR5 file headers specify GPL v2 or later; its supplied
`License.txt` contains GPL v3. These are reference-only selections, not complete
installed packages or browser runtime dependencies.

The next targeted check is the geometry and force operator in SA-4's localized
95–98% region, preserving all adjacent influences. The external sources support
testing singularity treatment explicitly, but do not authenticate a change to
ASWING. SA-4 remains **562/588** in its complete diagnostic configuration.

The subsequent [DUST/OLAF review](lifting-line-additional-review-20261030.md)
adds two more retained implementations and an executed comparison with OLAF's
compiled finite-segment kernel. It records the different circulation/force
locations and core conventions, plus the limits of arithmetic agreement near
a singularity. Native counts remain unchanged.
