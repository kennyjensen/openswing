# ST-4 independent flowing-air reference

An independent finite-span bending–torsion model now agrees with OpenSwing's
converged cosine pilot within **0.1% in all 12 tracked pole components**. Its
lowest-frequency difference is **0.01397%** and its minimum mechanical mode-shape
MAC is **0.999999605**. The independent structural and aerodynamic
refinements both pass the unchanged **0.1%** component mesh gate.

This materially supports the current linear aeroelastic equations for this
specific pilot. It does **not** resolve the native ASWING mismatch: the independent
lowest frequency is **11.494%** below the archive, almost the same
discrepancy as OpenSwing's **11.506%**. Neither result establishes which historical
settings generated the archive. ST-4 remains unvalidated against native ASWING.

## Independent formulation

[`isae_st4_flow_reference.py`](../../scripts/isae_st4_flow_reference.py) imports no
OpenSwing code. It uses cubic Hermite bending displacement/slope and linear twist,
with kinetic/strain energy for the literal straight beam. The original distributed
mass, both rotary inertias, elastic/centroid offsets and both eccentric point masses
are retained. Signed gravity contributes the downstream tension and chordwise first
moment, including the small actual point-mass axial offsets. The infinite extension,
in-plane stiffness and shear limits follow the same original ST-4 input interpretation.

The aerodynamic matrix is a separate closed-form Biot–Savart calculation for
finite bound segments and semi-infinite wakes. Bound vortices are at quarter chord;
flow tangency is sampled at the material Glauert midpoint and three-quarter chord.
The literal omitted lift-slope default is 2π. There are no images or PG correction
in this fixed pilot. Piecewise constant circulation is an explicitly documented
option; no spanwise smoothing or fitted correction is introduced.

The reference uses the attached-flow linear tangent. With the pilot's omitted
section limits ±2, stall width 0.05 and factor 40, the zero-circulation soft-stall
slope correction relative to the two-dimensional bound-vortex term is only
`80/(1+exp(40)) = 3.40e-16`. Its omission is at floating-point roundoff, not a
stall-model validation; no conclusions here extend to separated or stalled flow.

Drela's retained unsteady description supplies:

- Eqs. 33–36: steady and circulation-rate lift at quarter chord.
- Eqs. 43–44: midchord apparent mass, rotary fluid inertia and pitch-rate loads.
- Eqs. 48–49: local shed-vorticity lag, with the published coefficient 2/π.

The source PDFs/text are pinned in the evidence. The structural energy derivation
extends the earlier [independent loaded-beam reference](../../scripts/isae_st4_loaded_reference.py)
to flowing air. The earlier [spacing audit](isae-st4-airflow-discretization-20261103.md)
documents the pointwise/Fourier and sampling conventions.

In physical coordinates `x=[q,v,Γ]`, the independent descriptor equations are
`qdot=v`, `(Ms+Ma) vdot + ρ c L Γdot = −K q −Ca v −ρ U L Γ`, and
`(2/(π U)) Γdot = U Φ q + Hcp v + HΓ Γ`. Here L integrates the quarter-chord
virtual-work arm, Φ samples twist, Hcp samples control-point velocity and HΓ is
the normal horseshoe influence. The separate structural and aerodynamic meshes
are joined by exact element/strip intersections and polynomial integration.
Every degree of freedom is retained; there is no modal-basis truncation.

The physical input remains `Weight7a/7a_b17.asw`, U=120, ρ=1.0771417304,
zero incidence, gravity −9.81 in body z, fixed frame, Mach zero and enabled lag.
These match the declared current pilot, not an authenticated historical startup.
No original `.asw` file, operating point, mass, stiffness, damping or empirical
coefficient was changed or fitted.

## Refined comparison

The final independent model uses **128 requested uniform structural intervals**
and **256 requested cosine aerodynamic intervals** (129 and 257 after the required
weight station). OpenSwing uses its retained 128-interval cosine model. The
methods intentionally use different structural discretizations of the same physics.
Re/Im values below have units 1/s; nonzero component errors are relative to the
independent result. The nominally real pole retains the 5e-8 absolute imaginary
component gate, rather than an undefined percentage.

| Archive ordinal | Independent Re, Im | OpenSwing Re, Im | Real difference | Imaginary difference |
|---:|---|---|---:|---:|
| 1 | -24.8863848, 5.2014399 | -24.8877930, 5.2007131 | 0.00566% | 0.01397% |
| 2 | -4.4636737, 101.8161850 | -4.4635386, 101.8233089 | 0.00303% | 0.00700% |
| 3 | -3.4836863, 187.6050672 | -3.4803909, 187.6279547 | 0.09459% | 0.01220% |
| 4 | -8.3431669, 355.5158435 | -8.3452243, 355.5598653 | 0.02466% | 0.01238% |
| 5 | -392.9455521, 0.0000000 | -392.9375603, 0.0000000 | 0.00203% | 4.8e-13 absolute |
| 6 | -8.3209772, 540.3217031 | -8.3151390, 540.6322436 | 0.07016% | 0.05747% |

Pole matching is injective and checked against displacement/rotation shapes in
physical coordinates, weighted by span length. The reference elastic-axis
displacement is transformed back to the original beam reference axis before
comparison. This supports OpenSwing/reference branch identity; the native archive
has no eigenvectors, so its own branch labels remain qualified.

## Resolution and numerical controls

In the table A is the requested aerodynamic interval count and S is the requested
uniform structural interval count. Both grids retain the literal point station.

| Refinement | Mesh changed | Passing component checks | Largest nonzero-component change |
|---|---|---:|---:|
| A32 / S32 → A128 / S32 | aerodynamic | 8/12 | 0.35570% |
| A128 / S32 → A128 / S64 | structural | 11/12 | 0.69911% |
| A128 / S64 → A256 / S64 | aerodynamic | 12/12 | 0.04258% |
| A128 / S128 → A256 / S128 | aerodynamic at final structural mesh | 12/12 | 0.04113% |
| A256 / S64 → A256 / S96 | structural | 11/12 | 0.13450% |
| A256 / S96 → A256 / S128 | structural | 12/12 | 0.04721% |

The final structural comparison changes components by at most
**0.04721%**; the aerodynamic comparison on the finest structural
mesh changes them by at most **0.04113%**. Coarser failures remain in
the table. No native printed-precision gate is replaced by the 0.1% numerical
comparison gate.

All **112 saved right eigenvectors** across seven completed reference cases are
checked again against reassembled original physical equations, reconstructing
velocity and circulation independently. The final maximum relative action
residual is **1.48e-14**, below
1e-8. Four independent formula tests pass: direct line integration of every
horseshoe term plus the infinite-span lift slope; exact beam/fluid energies and
nonsymmetric pitch-rate loads; exact cross-mesh lift virtual work and control-point
kinematics; and signed gravity/eccentric-weight potential energy.

The first cosine structural reference failed its relative residual check, both
before and after row scaling. Inverse iteration and a dense generalized eigensolve
confirmed that the highly clustered fourth-order energy stiffness needed better
numerical treatment; those initial results were not accepted. A uniform structural
mesh avoids the shortest elements. The initial 64-element reference still missed
the gate at 1.4754e-8, so all refined solves use bordered Newton corrections of
the complete original eigenproblem. Residuals are evaluated in extended precision;
the correction factors remain ordinary complex-double sparse LU. No physical term
or unknown is removed and the 1e-8 residual gate is unchanged. Exact pre-change
reference versions, failed logs and the successful results are retained.

The finest reference calculation took **4.96 s** after imports,
including eigenvalue solution and comparison-data loading, with peak RSS
**137.9 MiB**. It is a specialized linear benchmark, not
a general nonlinear ASWING implementation or a timing comparison with OpenSwing.
All numerical jobs were serial, one BLAS thread, capped at 180 s and 512 MiB.

## What remains

This result argues against a large error in the audited linear circulation,
unsteady lift, apparent-mass or coupled beam terms at this operating point.
It does not prove every nonlinear equation, swept geometry, controls, other
operating points, unsteady wake approximation or historical setup. The near-critical
lowest pair remains sensitive: both independent methods reproduce essentially the
same frequency, yet disagree with the archive. Missing historical mesh/startup
settings and remaining model differences require further investigation; the archive
is not declared wrong. Registered native ST-4 counts remain **0/3,749 vacuum**
and **1/12 conditional flowing-air scalar matches**, with no complete native root
matched in the pilot.

All 136 production kernels and the previously verified public/dist application
remain unchanged. This study adds a native reference tool, tests and evidence;
it does not claim a new browser run or rebuild the unchanged app packages.

[Portable evidence summary](isae-st4-flow-reference-20261104.json),
[raw assessment](../../artifacts/isae/st4-flow-reference-20261104/assessment.json),
[formula tests](../../tests/test_isae_st4_flow_reference.py), and
[previous production mesh study](isae-st4-spatial-convergence-20261103.md).
