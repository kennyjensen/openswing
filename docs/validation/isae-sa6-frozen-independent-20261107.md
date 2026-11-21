# SA-6: independent finite-wing equations and native profile-force identity

2026-11-07. All **88 frozen-influence, strength-40 states** agree with an
independent reconstruction of their geometry, vortex fields, circulation
equations and control response. Four nonlinear solves started from zero
circulation also recover the same equilibria. No production correction was
found. Native-reference scores remain **470/528 static** and **370/528 F1**
at 5%; these independent checks add no native targets or passes.

## Full finite-wing check

The [reader](../../artifacts/isae/sa6-frozen-independent-20261107/run.py)
imports no OpenSwing code. It reads the literal constant section tables and
scaled, discontinuous control table, generates the declared cosine nodes
and mandatory control breakpoints, and places samples at Glauert midpoints.
Closed-form integrals of straight bound and semi-infinite trailing vortices
independently produce both velocity operators. It then assembles the complete
strength-40 leakage residual, its circulation Jacobian, the control-normal
rotation and the resulting force/moment derivatives. Loads use the physical
quarter-chord arm and the interval centroid for profile forces.

This extends the earlier strength-20 finite-wing investigations and the new
infinite-wing section checks to the complete **current** static/F1 scope.
The four independent nonlinear controls are the 15% and 35% chord models at
F1=4 and 44 on the 128-interval request. They use an independent root solver
with zero initial circulation, not OpenSwing's saved solution as a starting guess.

| Independent comparison | Maximum absolute difference or residual |
| --- | ---: |
| Geometry positions | 3.89e-16 |
| Bound/control velocity, divided by freestream speed | 3.62e-12 |
| Circulation residual at all 88 saved equilibria | 3.60e-12 |
| Complete circulation Jacobian | 2.99e-11 |
| Circulation response to F1 | 3.45e-15 |
| All 528 static coefficients | 1.34e-15 |
| All 528 F1 coefficients | 1.13e-16 |
| Four cold solves: circulation difference | 9.24e-12 |
| Four cold solves: nonlinear residual | 3.09e-11 |

All reconstruction differences are below the declared 2e-9 gate. Every cold
solve passes the unchanged 1e-8 nonlinear residual gate. Four serial batches
of 22 cases take 6.95 seconds after imports and source verification, using
one BLAS thread and a 768 MiB address-space cap. No production solver calls
or browser jobs were needed. All four batch processes finish normally.

## Where the control response decreases

![Regional roll sensitivity](../../artifacts/isae/sa6-frozen-independent-20261107/regional-control-response.svg)

For the fine 35%-chord model, CldF1 decreases from 0.00406132 at F1=32 to
0.00172085 at F1=44. The side driven toward lower stall accounts for **88.31%**
of this decrease; the opposite side accounts for 9.97%, and the uncontrolled
center for 1.72%. On the opposite side, pressure-force contributions eventually
outweigh its positive circulatory roll derivative. The regional sums exactly
recover the integrated derivative. These are model predictions, not recovered
native spanwise measurements, so they localize the response without proving
which native term differs.

## A diagnostic available from the native totals

The [Technical Description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
equations 72 and 74, supplies another constraint. These literal models have
constant chord and physical twist 4°, zero section Cm/control moment slopes,
zero moment origin, and the beam axis at x=z=0. Therefore the profile-force
component normal to the physical chord can be inferred from reported totals:

```
CN_profile = cos(alpha + twist) CL - sin(alpha + twist) CX + 4 Cm
```

This follows by subtracting the circulatory normal force, obtained from its
quarter-chord pitching moment, from the total normal force. It is **not total
CDp**. Its interpretation for the historical outputs is conditional on those
geometry and moment conventions; an undocumented native moment convention
could also affect it.

The [independent identity reader](../../artifacts/isae/sa6-frozen-independent-20261107/native-profile-identity.py)
reparses the original coefficient tokens and propagates their rounding intervals,
including incidence precision. It covers all 44 distinct native rows on both
current meshes. Direct integration of OpenSwing's saved profile forces agrees
with the identity within 8.68e-16.

| Setting | Signed error in inferred profile-normal force |
| --- | ---: |
| Current frozen/strength-40 default | +11.92% to +12.84%; median +12.33% |
| Preserved frozen/strength-20 diagnostic | −0.662% to +0.516%; median −0.079% |

Even the most favorable native rounding interval leaves the default at least
**11.85% high**. The maximum interval half-width is 2.639e-6 in coefficient
units. Thus printing precision does not explain this component difference,
although each original CX, CL and Cm separately passes the 5% allowance.
This transformation reuses existing targets; it is not an independent held-out
test or a reason to enlarge the tracked denominator. The strength-20 values
are reused, hash-verified historical results, not fresh current-kernel runs.

The first interval-check attempt incorrectly required the incidence derivative
to be negative in every case. It changes sign across operating points; the
correct requirement is a constant sign within each tiny rounding interval.
The initial reader is retained. No result, model equation or gate was altered
to remove that harness error.

The independent equations support the current implementation. The native
profile-force identity adds evidence for a stall/setup or load-convention
difference, but still does not authenticate a different strength or justify
fitting one. Next separate these possibilities using the native force/moment
and control-response constraints. Repeating the completed local-equation or
vortex-field checks is not the next task.

Evidence: [declared scope](../../artifacts/isae/sa6-frozen-independent-20261107/plan.json),
[finite-wing audit](../../artifacts/isae/sa6-frozen-independent-20261107/analysis.json),
[native identity and precision bounds](../../artifacts/isae/sa6-frozen-independent-20261107/native-profile-identity.json),
[process receipt](../../artifacts/isae/sa6-frozen-independent-20261107/process-receipts.json).
