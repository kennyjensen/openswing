# SA-6 source endpoint inertia audit

2026-10-31. The existing source beam acceleration operator reproduces the
documented endpoint-load/arithmetic-midpoint calculation. The older spatial
mass report uses Glauert aerodynamic samples instead. These are distinct
discrete integrations; they should not be described as the same operator.
Both retain **2,288/2,904** native tensor matches at the provisional 3% gate
on the existing cosine-64/128 meshes. No production change or registered
acceptance gain follows from this audit.

## Which calculation is implemented

The steady Technical Description's equations 55–56 average completed endpoint
loads. The unsteady description's equation 266 transfers that average force
through the arithmetic beam midpoint. The existing
[`rigid_acceleration_response`](../../openswing/apparent_box.py) implements
this rule, and
[`SourceQuiescentNetwork.rigid_acceleration_report`](../../openswing/source_quiescent.py)
uses it for the source still-air operator.

The existing [`apparent_properties`](../../openswing/inertia.py) report builds
a symmetric spatial tensor from section masses at aerodynamic sample points.
That operator is retained and independently verified under its stated
discretization. This audit does not replace it with the source acceleration
Jacobian: with general endpoint-varying properties, the source Jacobian can
be nonsymmetric and is not interchangeable with a symmetric spatial mass
tensor. For the literal constant-section SA-6 geometry, both can be checked
against separate kinetic-energy reconstructions.

All four paired source models retain their constant chord, physical 4° twist,
straight span, density and zero reporting reference. No experimental geometry,
adjusted material property or inferred deformation is introduced. The 44
native `.fmat` files and all 33 printed tensor entries per file are preserved,
including their tiny nonzero values. Repeated geometry is assembled once per
model and mesh; repeated native cells are not new independent observations.

## Absolute tensor evidence further constrains the mesh

The [previous audit](isae-sa6-native-mesh-20261031.md) found 57 candidate grids
compatible with three apparent-inertia/mass ratios. Ratios alone provide a
necessary condition. Using the literal density, span, chord and twist also
fixes the mass multiplying the spanwise second moment. Applying the absolute
printed inertia bounds narrows that interval to

```
0.19337406958768433655 <= sum(ds_i*y_i^2)/span
                      <= 0.19339578359246651435  m^2
```

This retains **22 of the 57** candidates, still not a unique native mesh.
With the source control boundaries inserted, the survivors are:

| Spacing | Compatible nominal counts |
|---|---|
| Uniform | 33, 34 |
| Cosine | 42, 43, 44 |
| Modified cosine | 38, 39 |

The previously tested modified-cosine-40 mesh with control breaks is
ratio-compatible but does **not** satisfy every absolute printed inertia.
Its source `Izz` is `8.906551593739262e-5 kg m²`, versus native
`8.906e-5 ± 5e-9 kg m²`. This small miss does not fail the provisional 3%
gate, but excludes exact recovery at printed precision under these assumptions.
It reinforces the earlier decision not to adopt that mesh. No additional
mesh or aerodynamic parameter sweep is performed.

## All native tensor comparisons

Each row below compares all 1,452 printed cells from the 44 original files.
The source response and legacy spatial tensor are separate diagnostics.

| Requested mesh | Legacy strict | Source strict | Either operator, 3% |
|---|---:|---:|---:|
| Cosine 64, 66 actual intervals | 880/1,452 | 968/1,452 | 1,144/1,452 |
| Cosine 128, 130 actual intervals | 880/1,452 | 880/1,452 | 1,144/1,452 |
| Modified cosine 40, 42 actual intervals | 880/1,452 | 1,056/1,452 | 1,144/1,452 |

All **484 non-tiny cells per mesh/operator** pass at 3%. The remaining 308
failures per mesh/operator retain their strict printed tolerances. For the
source cosine-128 calculation, their typical absolute errors are:

| Native component | Median absolute error | Maximum | Units |
|---|---:|---:|---|
| Apparent mass xy | 1.62e-16 | 1.91e-13 | kg |
| Apparent mass yy | 6.88e-29 | 2.03e-22 | kg |
| Apparent mass yz | 2.32e-15 | 2.73e-12 | kg |
| Apparent inertia xy, either printed reference | 2.87e-10 | 2.87e-10 | kg m² |
| Apparent inertia yz, either printed reference | 7.05e-12 | 7.05e-12 | kg m² |

No residual is snapped away and no tolerance changes. The larger strict match
count on a coarser candidate is not proof of convergence or historical identity.
This acceleration-response audit supplies no correction to the remaining
circulating-force/state-derivative differences.

## Verification

One native process completed 12 geometry assemblies, 24 source response
matrices and 24 legacy spatial matrices, including a translated reference.
The work took about 2.05 seconds after imports and required **zero nonlinear
or aerodynamic solves**. The process exited with status 0.

Forty-eight independent energy reconstructions and a separate standard-library
scalar reconstruction reproduce all matrices within **4.17e-17**. Independent
exact-rational comparisons replay all **8,712 scalar decisions** (1,452 native
cells × three meshes × two operators). High-precision literal constants and
the native last-digit rounding intervals define the stronger mesh constraint.
All sources and results are hash-bound. No browser or parallel job was launched.

Evidence:

- [Declared scope and source pins](../../artifacts/isae/sa6-source-inertia-20261031/plan.json)
- [Matrices, comparisons and candidate filtering](../../artifacts/isae/sa6-source-inertia-20261031/analysis.json)
- [Independent verification receipt](../../artifacts/isae/sa6-source-inertia-20261031/receipt.json)
- [Producer](../../artifacts/isae/sa6-source-inertia-20261031/run.py) and
  [scalar verifier](../../artifacts/isae/sa6-source-inertia-20261031/verify.py)
