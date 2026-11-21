# Saved-equilibrium position-history launch

The saved launch path accepts one nonrotating Earth-position actuator target in
force-only mixed motion. It retains unchanged loads and excludes controllers,
gusts, physical disturbances and rotating saved states. The explicit table must
initially match the saved position and Earth velocity. Existing velocity scopes
1–3 remain velocity-only; position launches own a separate version-4 scope.

Only the scope checks and records changed. The existing transition solver holds
the saved shape, local velocities, circulation and frame motion while completing
the right-side algebraic settings and accelerations. The original equilibrium
and before-input snapshot remain separately owned. The initial checkpoint has
physical-state validation; it is not a discrete-step or continuous-derivative
certificate. No physical equations, mesh settings or tolerances were changed.

The independent reference is a 2 kg tip mass on a 2 m axial spring with EA =
1000 N, giving stiffness 500 N/m. The saved frame acceleration is 0.4 m/s² and
spring extension is −0.0016 m. A natural cubic through (−1, 0.2), (0, 0), (1, 0.2)
commands Earth position y = 0.3t² − 0.1t³ for 0 ≤ t ≤ 1. Its initial acceleration
is 0.6 m/s². A correct launch holds the saved extension and engine force 0.8 N,
and changes local acceleration to −0.2 m/s². Re-equilibrating the spring would
give the wrong initial extension.

The independent equation is q″ + 250q = −0.6(1−t), with q(0) = −0.0016 and
q′(0) = 0. The standard-library reference in `scripts/verify-saved-position.py`
checks the analytic solution, spring/inertia balance, engine reaction and a
separate Radau/BDF discretization. It imports no production solver code.
Native coarse and fine Radau runs and BDF1/BDF2 continuations pass. Halving the
Radau step from 0.04 to 0.02 s reduces maximum displacement/force error by 29.46
and velocity error by 31.63 over the retained samples. Every checkpoint in these
runs restores through the public API; the original saved equilibrium is unchanged.

Permanent regression checks cover incompatible initial position and slope,
default-target mismatch, legacy-scope restrictions, corrupted target samples and
checkpoint ownership, JSON transport, and actual public continuation against the
independent spring equations. Browser coverage is recorded separately in
`saved-position.json`. Initial test-harness failures remain in the evidence;
they are not counted as successful workflows.

This is a scoped initialization and provenance extension. It does not establish
full ASWING spline/convention parity, general saved-history combinations or
aircraft-level validation. All 40 broad requirements remain Partial.
