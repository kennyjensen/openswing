# SA-6: a common pair of rate-sampling locations cannot close the discrepancy

Changing only the fixed rotational-velocity sampling locations cannot make
all eight retained pilot states pass. Even allowing arbitrary, independent
x/z offsets at the bound-force and control points, the minimum worst error is
**1.41125 times the allowed tolerance**. An exact rational certificate verifies
that bound. At least one of its five nonzero reference comparisons must differ
by **4.23375%**, above the unchanged 3% gate.

This closes a broader branch than the earlier
[control-point/force-point split](isae-sa6-rate-receiver-split-20261101.md),
which improved the pitch-rate pilot from 24/48 to 38/48 but lost one roll check.
It does not rule out changed induced operators, a different equilibrium,
discretization, or force/stall equations. The bound holds the retained
frozen-influence, strength-20 states and complete force derivatives fixed.
No inferred locations are adopted or scored as accepted physical settings.

The scope is the four paired aileron-chord models, controls 4° and 44°, and
the existing 128-interval request: eight states and 48 pitch-rate coefficients.
The models share the same straight geometry and chord. The four allowed
coordinates are changes in `x_hv/c`, `z_hv/c`, `x_cp/c` and `z_cp/c`, common
to all strips and all states. They have no imposed physical bounds, making
this an intentionally broad explanation test.

For normalized pitch rate, the velocity changes at either sample are
`delta V = 2 U (-delta_z/c, 0, delta_x/c)`. With the base state and induced
operators fixed, the direct residual and wrench changes are linear in those
four coordinates. Solving the saved circulation Jacobian gives a matrix `B`
such that the pitch-rate coefficient vector is `C = C0 + B delta_r`.
The material force arms and reporting references remain fixed, as specified
by the source load definitions.

Minimizing the largest error divided by its tolerance gives 1.4112493031156053.
Because the pilot is already infeasible, the predeclared extension to the
remaining 80 saved states does not run. The numerical optimizer is used to
locate a certificate; the certificate is then checked without that optimizer.

| Native constraint in the certificate | Required side of its tolerance interval | Positive weight, rounded |
|---|---|---:|
| 15%-chord, 4° control: CXq | Upper bound | 0.00777519 |
| 30%-chord, 44° control: CXq | Upper bound | 0.51339355 |
| 15%-chord, 4° control: Cnq | Lower bound | 0.10385055 |
| 35%-chord, 44° control: Clq | Lower bound | 0.23128267 |
| 35%-chord, 44° control: Cmq | Lower bound | 0.14369804 |

The saved certificate contains exact rational weights, not these rounded
display values. They are positive, sum to one, and cancel all four coordinate
coefficients exactly. Adding the five normalized comparison inequalities
therefore requires `0 <= -0.411249303115592...`, a contradiction. The resulting
exact lower bound is 1.411249303115592 times tolerance. This certificate applies
to the retained decimal representations of the independently checked discrete
maps; it is not a claim about arbitrary aerodynamic formulations or meshes.

The source review establishes why a partial numerical match cannot select a
production rule. Steady equation 64 evaluates rotational velocity at the
receiver; equations 155–157 construct the wind-directed vortex/control points.
The guide's K/F option and steady §4.6 freeze influence coefficients at jig
geometry and zero wind angles. Unsteady equations 29–32 separately describe a
material quarter-chord offset. These passages do not explicitly prescribe the
mixed live/frozen sampling rule examined in the previous pilot. The present
bound allows every fixed x/z pair under its stated assumptions, rather than
choosing one of those interpretations from its pass count.

The four response columns satisfy three independent translation identities:
moving both receivers together reproduces the saved speed/incidence response
in x and z, and the original receiver coordinates reproduce the saved q
column. Maximum discrepancy is **1.60e−14**. Applying the prior control-point
and force-point offsets reproduces both earlier component results within
**1.12e−16**.

A standard-library verifier independently reconstructs the straight-wing
velocity kernels and finite perturbations of all four forcing columns at
steps `1e-5` and `5e-6`. Circulation follows the computed first-order response;
these are equation checks, not new converged aircraft states. All **384**
coefficient-derivative checks pass, with maximum error **1.38e−10**. The scalar
linear residual is at most **1.07e−13**. The finite tangency-derivative error
decreases under step refinement; its largest value is 1.27e−7, including
finite-stencil truncation error. All 48 native tokens and comparison tolerances
are checked directly, along with the exact certificate and source/result hashes.

The matrix/optimization worker takes **3.65 seconds** after input verification
and imports. BLAS and HiGHS are explicitly limited to one thread. The independent
verifier uses scalar Python only. Both processes finish successfully. There
are no nonlinear solves, production field calls, browser launches or builds.

Production equations, all 42 registered status rows and comparison policy are
unchanged. The full qualified SA-6 state result remains **2,780/3,168**, including
**282/528** pitch-rate checks; the separate static roll/yaw table comparison
remains **616/616** under its documented hypotheses. Native reproduction and
the full project goal remain incomplete. Further receiver-location-only trials
within this fixed-state formulation cannot resolve the complete pitch-rate set.

Evidence: [declared scope](../../artifacts/isae/sa6-rate-location-bound-20261101/plan.json),
[coefficient maps and numerical bound](../../artifacts/isae/sa6-rate-location-bound-20261101/analysis.json),
[exact certificate and independent checks](../../artifacts/isae/sa6-rate-location-bound-20261101/verification.json),
[producer](../../artifacts/isae/sa6-rate-location-bound-20261101/run.py),
[scalar verifier](../../artifacts/isae/sa6-rate-location-bound-20261101/verify.py).
