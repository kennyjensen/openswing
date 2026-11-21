# SA-1: where OpenSwing differs from archived ASWING

SA-1 is the active priority. **19/154 registered checks pass**, all 22 baseline
jobs finish, and no complete seven-output row passes. The mismatch remains
unresolved. The source reviews and internal checks below narrow the search;
they do not establish that OpenSwing implements every historical ASWING detail
correctly.

![SA-1 lift, relative errors, and component error budgets](../../artifacts/isae/sa1-differences-20261027/differences.png)

[Vector figure](../../artifacts/isae/sa1-differences-20261027/differences.svg),
[PDF](../../artifacts/isae/sa1-differences-20261027/differences.pdf), and
[all original checks and plotted values](../../artifacts/isae/sa1-differences-20261027/report.json).
The [summary script](../../artifacts/isae/sa1-differences-20261027/summarize.py)
reads saved results and verifies their accounting; it performs no aerodynamic
solve. Displayed curves connect the original eleven incidences.

## Two distinct error patterns

At 1.9971 degrees, CL is **0.0580% high** while induced drag differs by just
**0.000293%**. The circulation-lift and efficiency discrepancies show that
matching induced drag alone does not establish matching circulation. At
18.091 degrees, CL is **2.6687% low** and induced drag is **4.6823% low**.
The near-stall error therefore cannot be explained by one constant lift multiplier.

| Incidence (deg) | Archived CL | OpenSwing CL (400 intervals) | CL difference (%) | CDi difference (%) | Checks passed (200 + 400) |
|---:|---:|---:|---:|---:|---:|
| 0.029369 | 0.0021285 | 0.00212973222 | +0.057892 | +0.000189 | 3/14 |
| 1.9971 | 0.144797 | 0.144881032 | +0.058035 | +0.000293 | 4/14 |
| 4.1116 | 0.298499 | 0.298670921 | +0.057595 | -0.000073 | 6/14 |
| 6.1087 | 0.444409 | 0.444665454 | +0.057707 | -0.000248 | 6/14 |
| 8.1351 | 0.593564 | 0.593889954 | +0.054915 | -0.005339 | 0/14 |
| 10.103 | 0.739397 | 0.739334671 | -0.008430 | -0.119744 | 0/14 |
| 12.1 | 0.878823 | 0.872300392 | -0.742198 | -1.426915 | 0/14 |
| 14.097 | 0.975602 | 0.958570066 | -1.745787 | -3.155304 | 0/14 |
| 15.095 | 1.00906 | 0.988300697 | -2.057291 | -3.678316 | 0/14 |
| 16.006 | 1.0342 | 1.01062448 | -2.279590 | -4.046341 | 0/14 |
| 18.091 | 1.07903 | 1.0502342 | -2.668674 | -4.682317 | 0/14 |

The seven registered outputs per mesh are lift, drag, CL, CD, CDi, Cm and span
efficiency. The two meshes repeat the same 77 archived scalar targets. Their
original printed tolerances remain unchanged.
All current passes are drag-related: drag 6/22, CD 6/22 and CDi 7/22. Lift, CL,
Cm and efficiency each remain 0/22.

At the highest incidence, **99.61% of the CL error is in circulation lift**;
only 0.39% is in profile lift. Induced CD is low by 0.00314842 while profile CD
is high by 0.00361697. These partly cancel in total drag. The
[load decomposition](sa1-load-consistency-20261027/report.md) derives native
circulation lift independently from moment and from efficiency/induced drag,
and propagates the original rounding intervals. These inferred components are
diagnostic quantities, not extra archived test targets.

## New checks of the adapter and load calculation

The [script mapping review](sa1-script-mapping-review-20261027.md) traces
`SA_1.sh` through the guide and adapter. The script supplies the operating
incidences and indicated airspeed and selects anchored constraints. The force
normalization inferred jointly from all native Lift/CL and Drag/CD pairs allows
only -0.141 to +0.366 ppm relative variation about the model's qS. That is far
smaller than the approximately 580 ppm attached CL discrepancy. For this
stationary rigid wing at fixed PG Mach zero, changing density and true airspeed
while preserving qS leaves the normalized circulation equations and reported
loads unchanged. IAS interpretation is consequently not an explanation within
that setup.

A direct [rigid-versus-mounted comparison](sa1-anchored-equivalence-20261027.md)
now checks the adapter's route against the anchored interpretation at 1.9971
and 18.091 degrees, using the original model and 200 intervals. All four solves
finish. The largest difference across the seven outputs is **6.67e-16** after
normalizing dimensional forces by qS. Geometry and circulation fields agree to
roundoff. The two routes have exactly the same
native matches: 2/7 at the attached condition and 0/7 near stall. Anchoring
therefore does not explain the mismatch in these tested states.

The [prescribed-circulation regression](sa1-lift-conservation-20261027.md)
checks an uneven grid, unequal circulation, a duplicated zero-width root, and
four incidences. **All 63 algebraic checks pass**, with maximum normalized
discrepancy 1.43e-14. Actual surface-load and Trefftz calculations agree with
`L = rho U sum(Gamma_i delta_y_i)`. The independent quadratic induced-drag
calculation also agrees. These synthetic fields are deliberately not solved
equilibria; their nonconverged flags are retained. They exclude a loss of lift
in the tested interval weights, source cancellation and force projections.

The source also narrows proposed load-transfer explanations. For pointwise
circulation constant on each interval, one-sided endpoint averaging preserves
that same lift integral. A structural load-transfer change alone cannot change
the source's Trefftz efficiency definition. Any proposed recovery correction
must explain both the surface loads and the wake-derived lift/efficiency.

The separate source structural policy also does not specify a different SA-1
aerodynamic model. Both interpolation policies reduce this original model's
two-knot tables to the same linear geometry and constant properties
([beam_spline.py](../../openswing/beam_spline.py)). The source mounted route
calls the same aerodynamic evaluator and retains its interval quadrature; its
endpoint transfer preserves the complete strip force and moment
([source_coupled.py](../../openswing/source_coupled.py)). For this rigid wing,
changing that policy would test structural/API consistency, not introduce a
documented aerodynamic correction. This is a code-derived rigid-limit argument;
no additional source-policy solve is claimed.

## What remains unresolved

The strongest remaining lead is how the historical discretization and sampling
produce the circulation distribution and its integrals, including the nonlinear
flow-tangency calculation near stall. The archived seven-column table does not
uniquely determine that distribution. This is a limitation of what the aggregate
outputs identify, not evidence that the current implementation is correct.

Existing [continuation checks](sa1-alpha-continuation-followup-20261027.md)
reproduce cold solutions, and [refinement to 1,600 intervals](sa1-mesh-limit-followup-20261027.md)
retains the near-stall gap. Further refinement of the same mesh family is not a
promising explanation. The reviewed [nonlinear section law](sa1-nonlinear-law-review-20261027.md)
and [scalar influence replay](sa1-steady-aero-source-review-20261027/report.md)
match the inspected published equations under their stated sampling conventions.

No production equation, original model, stall parameter or acceptance tolerance
has been changed in this investigation. A defensible fix still needs an
identified algorithmic discrepancy and a regression showing that the correction
accounts for the archived differences. No cause is assigned to unavailable
historical settings merely because the present internal checks pass.
