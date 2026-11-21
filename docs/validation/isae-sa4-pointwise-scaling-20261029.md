# SA-4: direct-solver scaling and failed-state Newton checks

The [descending-angle continuation diagnostic](../../artifacts/isae/sa4-descending-alpha-20261029/report.md)
now recovers the default N160 6.55° point using the current direct solver and
the accepted 7.06° circulation as its seed. All 7/7 outputs pass, with maximum
reference error 1.862%, residual 7.55e-15 and maximum normal Mach 0.604.
The next 6.10° step fails; lower points are skipped. Thus initialization can
recover an admissible matching root at one cold-start failure, without changing
equations or gates. This remains a diagnostic, not a production-default fix.

The subsequent [fresh-Jacobian trust-region diagnostic](../../artifacts/isae/sa4-trust-region-20261029/report.md)
also recovers none of the three difficult cold starts within 1,000 residual
evaluations each. Maximum residuals remain 0.199, 0.260 and 0.206. The 7.06°
iterate is subsonic but still fails convergence. Tail steps continue measurable
merit reduction, so these are evaluation-budget failures rather than the
Armijo run's roundoff-scale stagnation. Eventual convergence is unproven;
the control retains 7/7 and registered scores remain unchanged.

The later [Armijo Newton diagnostic](../../artifacts/isae/sa4-damped-newton-20261029/report.md)
also recovers none of the three difficult cold starts. It decreases residual
merit but exhausts backtracking after 141, 63 and 47 accepted steps at
4.06°, 4.60° and 7.06°. Terminal maximum residuals remain 0.201, 0.225 and
0.785, and terminal normal Mach exceeds one. The 0.29° control retains 7/7
checks. Simple monotone damping is therefore insufficient in this sample;
no production solver change or additional reference pass is justified.
Saved terminal matrices are severely ill-conditioned even after column
scaling, while merit gradients remain appreciable. The evidence supports
weak Newton directions with very large corrections; it does not demonstrate
stationary nonzero residuals or absence of an admissible root.

Updated 2026-10-29. Fixed variable and residual scaling does **not** recover
the tested SA-4 direct solves. Fresh Jacobian checks at all six rejected
endpoints agree with directional differences. Full Newton steps increase
the residual merit sharply, while sufficiently small steps decrease it.
This supports a nonlinear step-selection difficulty at these states;
it does not establish a convergent replacement solver or native ASWING parity.
Production equations, defaults, acceptance gates and registered scores are unchanged.

The subsequent [full-Newton diagnostic](../../artifacts/isae/sa4-full-newton-20261029/report.md)
also fails to recover the three difficult cold starts: 4.06°, 4.60° and 7.06°
each exhaust 100 undamped steps. The 0.29° control converges in one step and
retains 7/7 checks. No call enters production polish; every full update is
retained and independently checked. Separately, all 42 earlier Taylor trials
place at least 99.49% of squared nonlinear departure in the curved-tip samples.
The remainder is the full stall-leakage composite, including local-speed
coupling. This narrows the location and equation term; it does not demonstrate
an incorrect stall law or justify a production change.

The subsequent [exact curvature split](../../artifacts/isae/sa4-stall-speed-curvature-20261029/report.md)
finds that the section-law term dominates local directional curvature by
64–639 times, while full-step section-law and speed-norm remainders are
comparable and strongly oppose each other. The numerical speed floor is
inactive over all tested paths. This is a verified algebraic decomposition
of the six rejected states, not a recovered physical solution.
Within the section-law term, the speed-denominator contribution to the
section-coefficient derivative has 1.58–6.12 times the curvature-weighted
amplitude of the circulation-numerator contribution. Both depend on the same
Newton direction and partly cancel; they cannot be treated as independent
causes. All 24 checks of this further decomposition pass.

## Paired scaling experiment

Eight fresh calls compare the current direct solver with a fixed transformed
system at 0.29°, 4.06°, 4.60° and 7.06°, using the default 160-interval
SA-4 geometry. Both arms explicitly use `circulation_method=direct`, the
ordinary linear circulation seed and the same analytic Jacobian. In particular,
the previously accepted automatic solve at 7.06° used continuation; its
failure in this forced-direct experiment is not a production regression.

For physical circulation `Gamma`, the transformed variables and equations are
`Gamma = D*u`, `F(u) = W*R(D*u)`, and
`J_F = W[:,None]*J_R*D[None,:]`. Here `D = 0.5*chord*speed`, and each
diagonal entry of `W` is the reciprocal row norm of `J_R(Gamma0)*D`.
Both positive scales are fixed before iteration; no reference output enters
their construction. These invertible transformations preserve roots and the
exact physical Newton correction. They can change a finite-step trust-region
trajectory. MINPACK already performs internal column scaling; the experiment
does not assume that the current solver uses unscaled variables.

The returned circulation and residual are mapped back before the unchanged
physical checks and near-root polishing. There are no retries, continuation
calls or accepted results from rejected fields.

| Incidence | Arm | Result | Residual evaluations | Maximum original residual before polishing | Maximum section-normal Mach at that endpoint |
|---:|---|---|---:|---:|---:|
| 0.29° | Current | Accepted | 11 | 9.19e-17 | 0.26278 |
| 0.29° | Scaled | Accepted | 11 | 1.00e-16 | 0.26278 |
| 4.06° | Current | Rejected | 47 | 0.19772 | 1.12164 |
| 4.06° | Scaled | Rejected | 76 | 0.20245 | 1.12830 |
| 4.60° | Current | Rejected | 39 | 0.26842 | 1.35652 |
| 4.60° | Scaled | Rejected | 58 | 0.27453 | 1.35539 |
| 7.06° | Current | Rejected | 111 | 0.32595 | 1.33783 |
| 7.06° | Scaled | Rejected | 39 | 1.60152 | 1.64113 |

All six rejections fail the original residual gate; their listed Mach numbers
are diagnostics of rejected states. Both accepted controls pass 7/7 reference
checks at 3%, with maximum reference error 0.07926%. CL, CD and Cm match
exactly between those controls; their largest difference among the twelve
reported coefficients/efficiencies is 4.44e-16 in efficiency.

Initial matrix condition numbers improve substantially: for example, at 4.06°
the raw Jacobian condition number is 7,258 and the transformed value is 658;
at 7.06° they are 80,294 and 82.4. That improvement does not recover a root.
It therefore supplies no reason to adopt this scaling as a production fix.

All eight workers completed and were reaped, with zero timeouts. The retained
41.6-second diagnostic elapsed time includes process startup and matrix
diagnostics; it is not a browser-performance measurement.

## Fresh Newton direction at the rejected endpoints

Three setup-only model assemblies captured the original residual and analytic
Jacobian without entering a nonlinear solver. At each of the six stored
endpoints, the residual, Jacobian and geometry replay exactly. A single linear
solve gives `delta = -solve(J, R)`. Its normwise backward error is at most
4.22e-17. No trial state is accepted or reused for another nonlinear iteration.

The protocol fixes forward fractions
`1, 0.5, 0.1, 0.01, 0.001, 0.0001, 0.000001` and central-difference
fractions `1e-2, 1e-4, 1e-6, 1e-8` before evaluation. All six best-of-four
directional derivative checks pass the declared 2e-6 scaled gate; the worst
is 4.325e-7. This is a check at the failed endpoints, extending the earlier
checks at the zero, linear-seed and preceding accepted states.

For `Phi = 0.5*||R||^2`, an accurate Newton direction has
`d Phi(Gamma+t*delta)/dt` at zero equal to `-||R||^2`.
The full-step merit ratio ranges from about 69 to 121,425 across the six
states: every full step increases Phi. A fraction of 1e-6 decreases Phi
at every endpoint; 1e-4 decreases it at five of six. Thus a local descent
direction exists, but taking the full correction is not locally reliable
at these rejected states. This does not prove that repeated backtracking
would find an admissible equilibrium, or explain every SA-4 failure.

The probe used 96 original-residual evaluations and six analytic-Jacobian
evaluations, with zero new nonlinear solves. It changes no reference score.
None of the 42 forward trials meets the original 1e-8 residual gate.

An [independent saved-array audit](../../artifacts/isae/sa4-pointwise-equilibration-20261029/newton-taylor/independent-review.md)
passes 1,530/1,530 checks with exact agreement in recomputed arithmetic.
Eleven of 24 individual finite-difference steps pass; all six state gates
pass under the predeclared best-of-four rule. Endpoint Gamma, D, R and J
match the original stored arrays. The regenerated setup seed, chord, span
and receiver arrays were not separately retained by the Taylor probe, so
their replay claims are supported by its source and execution records.
Small linear backward errors alone do not establish forward accuracy.

## Source evidence and scope

The [Newton source review](../../artifacts/isae/sa4-pointwise-scaling-20261029/globalization-source-review.md)
finds a full Newton description and iteration controls in the ASWING
documents, but no numerical circulation step cap, damping constant or
residual tolerance. The inspected JVL versions apply their residual-driven
circulation correction in full. Their later angle/control relaxation acts
on a separate global correction, and is not evidence for capping this
circulation step. JVL is a qualified analogy, not native ASWING source.

The small-step descent identity above is a mathematical diagnostic, not an
ASWING-documented backtracking algorithm. Neither its step fractions nor
the scaling constants are proposed as physical-model changes.

The independent paired-data audit retains **1,166/1,169 checks passing**.
Its three failed checks are exact-bit comparisons of the two accepted
0.29° controls' independently computed linear seeds, initial residuals and
mapped seeds. Maximum absolute differences are respectively 3.89e-16,
2.19e-16 and 3.47e-17. The initial Jacobian, geometry and both scales agree
exactly there, and all three failed-angle pairs have identical seeds and
initial residuals. All transformation, physical-gate and reference checks
pass, with maximum scaled discrepancy 1.33e-15. The raw audit failure is
retained; it is not relabeled as bit-identical control data.

Evidence: [paired protocol](../../artifacts/isae/sa4-pointwise-equilibration-20261029/protocol.json),
[compact saved-data summary](../../artifacts/isae/sa4-pointwise-equilibration-20261029/summary.json),
[full paired report](../../artifacts/isae/sa4-pointwise-equilibration-20261029/report.json),
[execution receipt](../../artifacts/isae/sa4-pointwise-equilibration-20261029/execution-receipt.json),
[independent audit](../../artifacts/isae/sa4-pointwise-equilibration-20261029/independent-review.json),
[Taylor protocol](../../artifacts/isae/sa4-pointwise-equilibration-20261029/newton-taylor/protocol.json),
and [Taylor results](../../artifacts/isae/sa4-pointwise-equilibration-20261029/newton-taylor/report.json).
