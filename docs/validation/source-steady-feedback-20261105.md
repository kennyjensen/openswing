# Steady controllers with source airflow equations

Date: 2026-11-05.

The moving-airflow steady route now solves controller actuators, integral states
and ordinary trim targets together with source beam deformation and circulation.
It calls the existing simultaneous controller solver with `SourceAirflowNetwork`;
the physical and controller equations, Newton tolerances and final full-tangent
rank check are unchanged. Source section outputs use the actual controlled
flight condition. Saved equilibria retain the controller definition, actual
actuators, integral states and solved commands for dynamic launch.

This follows the [ASWING unsteady technical description](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf),
section 11.2: control-law residuals (118) participate in the full equation
system, while setting the integral rate to zero in (117) requires measured
values to equal their commands. The existing declarative controller implements
these equations; this change does not execute an external Fortran CONTROL
routine or add an outer feedback/trim iteration.

In the workbench, select **Mounted aeroelastic equilibrium** and **ASWING
structure + airflow**, then enable **Feedback**. A controller-owned actuator
cannot also be prescribed by a trim row. Solve its `command.E#` or `command.F#`
bias, or a measurement command such as `command.RY[2]`, instead. Custom operating
equations, minimum-control allocation and steady derivative requests remain
unsupported for this source policy. The stationary source policy remains
separate and does not acquire controller support.

The new checks include independent mechanical and aerodynamic references:

- A bar with stiffness 500 N/m under proportional position gain 200 N/m has
  extension `200*.01/(500+200)`. Adding integral gain 100 gives exactly .010 m,
  5 N thrust and integral state -.05, with zero position error.
- Bias-command and measurement-command trim reach the same 5 N load with the
  expected distinct command values. An accelerating frame and accelerometer
  feedback require 5.8 N thrust and integral -.07, including real inertial load.
- Four independently integrated horseshoes predict the circulation distribution,
  flap setting and integral state for circulation feedback. Gates are 2e-6
  relative plus 2e-10 absolute, with full residual below 1e-9.
- Reusing an integral-controlled equilibrium for an 8 N target gives .016 m
  extension and integral -.08. A saved 5 N state launches without recomputing
  equilibrium and retains its nonzero actuator/integral state over two steps.
  Deliberately corrupting the integral state is rejected by the full initial
  dynamic residual. This is a held-equilibrium launch check, not a new forced
  transient refinement study.
- Redundant PI/bias trim and attempts to override controller-owned actuators
  are rejected, including a zero-residual but nonunique equilibrium.

The elastic climbing-turn case also passes: three flap controllers and one
engine controller retain all 16 targets, including all six net force/moment
constraints. Actual actuator settings and every node position agree with the
separately trimmed source model. Maximum net force is 6.22e-13 N, maximum net
moment 8.02e-14 N m, and the full residual is 8.44e-15. The final column-scaled
reciprocal condition is 2.26e-4, above the unchanged 1e-10 rank gate.
The controller half took 72.73 s, including fresh validation of the retained
reference. The original combined job ended without a terminal test report;
only the unfinished controller half was rerun, through the same test assertions.

Together, 139 distinct Python checks pass: 138 via pytest and the climbing-turn
assertion case completed separately. All 40 selected JavaScript checks pass.
The actual built workbench passes offline steady controller trim, exact
computed-project restoration and a saved-state time launch. Its PI controller
solves a 5 N force target with a 2.01 m position command, 5 N thrust and integral
state -.05. That state persists through four time steps after releasing the
trim target. The workflow takes 54.8 s (1.2 minutes including setup), with no
page errors or HTTP requests after disconnection. All 138 source/public/dist
kernel modules match. All 17,419 numeric fields from native replay of the
exact exported requests pass `2e-8 + 2e-8 * abs(native)`. The largest difference
uses 9.21e-08 of its allowed gate. Every native output field is compared,
including string/boolean values and list lengths; only the root evaluation
counter is excluded.

The project validator now reads a steady controller from its steady request,
rather than modal options, and checks that the saved time-launch setup retains
the same controller. A focused failing-before test covers this distinction.

No native ASWING result is introduced by these implementation checks. All 42
ISAE scores and error summaries remain unchanged. Full ASWING functionality
and historical executable agreement remain incomplete.

Code: [source airflow](../../openswing/source_airflow.py),
[source reporting](../../openswing/source_discrete.py),
[physical tests](../../tests/test_source_steady_feedback.py),
[project validation](../../web/solution-data.js),
[browser workflow](../../tests/browser/source-steady-feedback.spec.js).
Requests, results and logs are retained in
`artifacts/isae/source-steady-feedback-20261105/`.

Initial harness failures are retained: a launch assertion compared expanded
constraint records against abbreviated input, a synthetic project omitted its
required convergence flag, and the standalone reference check initially omitted
two constructor arguments. Their corrections do not change any physical gate.
