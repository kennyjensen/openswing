# Steady stability derivatives with source airflow equations

Date: 2026-11-05. Selected physical, regression and offline browser checks pass.
The [structured record](source-steady-derivatives-20261105.json) retains the
source hashes, requests, results and evidence inventory.

The source moving-airflow steady route now exposes the existing implicit
equilibrium derivatives, including feedback controllers, section response,
normalized flight inputs, body/reference-origin inputs and flap/engine commands.
The linearization retains the actual source network class and its converged
condition. Original trim equations are released. Other solved inputs remain
fixed; controller actuators and equilibrium states respond to the requested
input perturbation.

This follows [ASWING steady theory](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
sections 8.3–8.6, equations 212–229. For each input, `J dx/dp = -R_p` includes
source structural compatibility, nodal loads and circulation. In free-flight
response, six acceleration unknowns also preserve net force/moment balance as
in equation 213. Fixed-acceleration response instead holds those accelerations
at their converged values and reports the resulting load changes. Both assume
zero local elastic rates; they do not establish unsteady stability or flutter.
Force coefficients use fixed base axes, dynamic pressure and reference lengths.

In the workbench, choose **Mounted aeroelastic equilibrium**, then **ASWING
structure + airflow**, and enable **Stability & control derivatives**. For
free-flight response, first trim all six net loads. A non-equilibrated free-flight
base is rejected. The separate stationary source policy retains its zero-motion
restriction and does not acquire rate derivatives.

No physical linearization formula, differentiation step, singularity gate or
linear-residual tolerance changes here. The existing analytical circulation and
control columns, complete checked centered probes and output recovery remain.
One scaled matrix factorization serves all requested input columns. It is
recomputed at the converged physical state; this extension does not yet reuse
the Newton factorization or claim ASWING's derivative cost.

Source section derivative metadata now identifies the element constitutive
average and generally nonorthogonal averaged endpoint transform. This avoids
labeling those quantities as generic midpoint samples. Actual sensor anchors,
endpoint extrema and their one-sided values remain distinct. The numerical
section recovery already dispatches through the selected source law.
The browser plot annotations and distribution CSV use this declared sampling
metadata, including when restoring saved derivative results.

Six new checks establish the integration:

- A rotating axial bar obeys `k*delta = P + m*Omega^2*(L+delta)`. With
  `k=500`, `m=2`, `Omega=.7`, `L=2`, the original trim fixes `delta=.01`.
  After releasing that target, the derivatives are
  `d(delta)/dP = 1/(500-2*.7^2)` and
  `d(delta)/dOmega = 2*2*.7*2.01/(500-2*.7^2)`.
- Proportional and integral position controllers match independent spring
  derivatives, including actual actuator, measurement and integral-state
  responses to actuator-bias and position commands.
- A freely accelerating rigid body matches the analytical quadratic point-drag,
  engine thrust and Euler angular-momentum derivatives at nonzero rotation rate.
- A rigid lifting wing matches `a_p = (M_real + M_apparent)^-1 F_p`, using its
  literal point mass, offset and inertia tensor, separately evaluated aerodynamic
  perturbations and the reported apparent-fluid tensor. Omitting apparent mass
  measurably changes the response; all six net-load derivatives remain zero.
  This checks the coupled response, not an independent derivation of that fluid
  tensor.
- A deformed, rotating lifting wing matches fresh nonlinear equilibria perturbed
  in incidence, yaw rate and flap setting. The comparison includes every node,
  the complete fluid wrench and source section strains. The source analytical
  flap partial is active in this case.

Two initial test-harness failures are retained. The rigid-body expectation used
an unset density instead of the explicit file density; the wing check initially
assumed the source mass report supplied a generic spatial matrix. It deliberately
does not, since the general source endpoint operator is not an energy-derived
finite-element mass matrix. The corrected oracle uses the example's independently
specified point mass and inertias. No production equation or tolerance changed
in response to these fixture corrections.

All 122 distinct Python checks pass: six new integration checks above and 116
affected regressions. The regression batch takes 58.71 seconds. All 29 selected
JavaScript checks pass. One actual offline Chromium workflow passes in 53.0
seconds including setup (38.9 seconds for the test itself): source airflow,
integral feedback, command derivatives, table/plot displays, feedback and section
CSV exports, and exact project restoration without recomputation. There are no
page errors or HTTP requests after going offline. All 138 source/public/dist
kernel modules match.

Native replay of that exact exported browser request takes 4.37 seconds and
passes all 2,749 numerical comparisons, plus structure, string and boolean
checks. The unchanged gate is `2e-8 + 2e-8 |native|`; only the root evaluation
counter is excluded. The largest discrepancy uses less than 1e-8 of its allowed
gate. These are OpenSwing cross-runtime checks, not comparisons to an ASWING
executable.

This adds no native ASWING reference result. All 42 ISAE rows and error summaries
remain unchanged. Full ASWING feature parity, native reference agreement, Newton
factorization reuse for derivatives and remaining source restrictions stay open.

Code: [source airflow](../../openswing/source_airflow.py),
[implicit derivatives](../../openswing/derivatives.py),
[physical checks](../../tests/test_source_steady_derivatives.py),
[browser workflow](../../tests/browser/source-steady-derivatives.spec.js).
Requests, outputs and logs are retained in
`artifacts/isae/source-steady-derivatives-20261105/`.
