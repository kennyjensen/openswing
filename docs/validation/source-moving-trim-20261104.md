# Moving-frame trim with the source airflow equations

Started 2026-11-04; verified 2026-11-05.

The moving-airflow operator now permits prescribed or solved aircraft rates,
linear accelerations and angular accelerations during mounted steady trim.
Local elastic velocities, local elastic accelerations and circulation rates
remain zero. Beam deformation, circulation and the selected operating variables
are solved together by the existing full residual/Newton system.

This removes a stationary-only restriction from an operator which already
implements moving-frame inertia. It introduces no new force approximation,
outer trim loop, parameter fit or relaxed tolerance. The separate stationary
`drela-steady-coupled-v1` operator retains its zero-motion restriction.

ASWING's [documented nonlinear static capability](https://web.mit.edu/drela/Public/web/aswing/)
includes prescribed rates and indirect load/trim targets. The
[unsteady technical description](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf),
sections 6.1–6.3, retains aircraft motion in the real and apparent inertial
loads. Setting local elastic rates to zero therefore does not require aircraft
rotation or acceleration to vanish. This is an instantaneous equilibrium in
aircraft axes; a subsequent trajectory can change its Earth velocity and pose.
It does not establish a time-invariant linearization about every such state.

Select **Mounted aeroelastic equilibrium** and the **ASWING structure +
airflow** equations in the workbench. The existing motion inputs and operating
targets now accept nonzero frame motion. Saved equilibria retain the solved
motion and controls for time launch. Custom steady equations, minimum-control
allocation and steady feedback remain unsupported in this source route. The
workbench angular-motion fields use degrees per input time (or time squared);
the JSON/API motion vectors use radians.

Seven new physical checks pass:

- Five cases compare an axial bar with a rotating, accelerating tip mass against
  `delta = (P - m*a_y + m*Omega_z^2*L)/(k - m*Omega_z^2)` and the complete
  vector force/moment balance. They cover prescribed motion and separate solves
  for power, rotation rate, linear acceleration and angular acceleration.
  Position tolerance is 2e-9 m; wrench/solved-variable tolerance is 2e-8 in
  the corresponding input units. All three angular-acceleration components
  participate in the prescribed state.
- A flexible lifting wing recovers a separately prescribed loaded state by
  solving incidence and vertical acceleration. After releasing its trim rows,
  the fresh dynamic network's full residual is 2.69e-16 at zero local rates.
- A rotating/accelerating saved state launches without another equilibrium
  solve. Its local centrifugal deformation stays constant while its body-frame
  velocity follows `U_dot = a - Omega cross U`. Halving the step from .002 to
  .001 s over .004 s reduces normalized velocity error from 1.232e-6 to
  3.422e-7; the fine gate is 1e-6 and the contraction gate is .4. The initial
  full dynamic residual is 4.98e-15. This is a short launch check, not a long
  aircraft maneuver validation.

The 119 selected Python regressions and 39 JavaScript checks also pass. These
cover stationary compatibility, saved targets, malformed motion inputs and
the restrictions on unsupported steady/dynamic combinations. The total is
126 distinct Python checks. No full unrelated transient suite was repeated.

The built workbench passes an offline moving trim, computed-project restoration
without recomputation, and a four-step saved-state time launch. The browser
case uses a .7 rad/s rotation rate (entered in degrees), -0.4 m/s² reference
acceleration and a 5 N net-force target: solved thrust is 2.2302 N and tip
extension is .010 m. The test takes 44.2 s (1.1 minutes including setup), with
no page errors or HTTP requests after going offline. All 138 source/public/dist
kernel modules agree. All 17,230 numeric comparisons against native replay
of the exact exported requests pass `2e-8 + 2e-8 * abs(native)`; the largest
difference uses 9.85e-09 of its allowed gate. Strings, booleans, list lengths
and every native output field also match; only the root evaluation counter is
excluded. Browser-only provenance and request metadata are not solver outputs.

Two initial test-harness failures are retained: the native launch check read a
frame output from the wrong nesting level, and the first browser test entered
radians into a degree-valued UI field. Correcting those tests did not change
production equations or acceptance gates.

No native ASWING reference is added by these implementation checks. All 42
ISAE rows and their error summaries are unchanged. Full ASWING feature parity
and the remaining validation discrepancies stay open.

Code: [moving airflow](../../openswing/source_airflow.py),
[request validation](../../openswing/numerical_policy.py),
[physical checks](../../tests/test_source_moving_trim.py),
[browser workflow](../../tests/browser/source-moving-trim.spec.js).
Requests, results and logs are in
`artifacts/isae/source-moving-trim-20261104/`.
