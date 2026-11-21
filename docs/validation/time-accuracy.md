# Optional temporal refinement checks

The implemented temporal-check workflow has passing targeted native,
independent-reference, packaged-WASM and offline-browser evidence. It does not
close the full ASWING scope or establish aircraft/experimental validation.

ASWING's public time menu specifies a fixed interval and number of steps. The
optional `accuracy` setting is an OpenSwing numerical extension. It preserves
the default fixed-step implementation, forcing-event semantics and physical
equations. It is available for BDF1, BDF2 and three-stage Radau IIA.

## Meaning of the check

For each trial interval, solve one full step and two half steps from the same
accepted state and history. Compare physical quantities at the common endpoint,
then accept the two-half-step endpoint only if every checked discrepancy is
within tolerance. No extrapolation changes the accepted physical state.

For a scaled scalar or vector `q`, the ratio is

```
norm(q_half_steps - q_full_step)
----------------------------------------------
atol + rtol * max(norm(q_half_steps), norm(q_full_step))
```

The largest ratio over all checked samples and quantities must not exceed one.
Vectors use Euclidean norms rather than coordinatewise maxima. Rotations use
the relative SO(3) angle between the endpoints; their relative magnitudes use
the trial's starting orientation. Earth displacement is relative to the common
starting position, so a large arbitrary Earth origin cannot mask local motion.

The comparison includes nodal displacement, rotation, velocity and angular
velocity; circulation and its rate; section forces and moments; support/joint
reactions; local and frame accelerations; Earth motion; and scaled controller
variables. Reference length, force, velocity, rate and circulation scales are
recorded in `result.accuracy.scales`. The absolute tolerance is dimensionless in
these scaled variables. It is not a tolerance in metres or newtons.

The discrepancy is a local resolution indicator, not a calibrated local
truncation error or a bound on accumulated trajectory error. It does not bound
every derived output. A narrow feature missed by all trial samples can still
be missed. Check maximum step, tolerances and spatial mesh independently.

## Step selection and checkpoints

`dt` limits the trial interval between reported endpoints. Each endpoint follows
two internal half steps. `snapshot.step` records the final internal step;
`snapshot.accuracy.trial_step` records the interval between public snapshots.
The private midpoint is retained in BDF checkpoints as the actual predecessor.
`internal_steps` counts accepted half steps, excluding discarded coarse trials.

Both refined startup half steps use BDF1 when BDF2 lacks a predecessor. Subsequent
BDF2 trials use their real saved history. Forcing breaks reset that history;
the endpoint retains left-hand values and the next interval uses right-hand
values. Radau needs no predecessor. The gust phase guard applies independently
to each accepted half step.

A conservative square-root controller changes the next interval. It does not
assume fifth-order convergence of algebraic variables under Radau: constrained
reactions can have lower order. Failed nonlinear solves and failed accuracy
checks are counted separately. Failure at the minimum step raises an explicit
error; it never accepts a failed temporal check.

The default minimum is `min(dt, duration)/65536`. Its resolved value is saved
in the checkpoint so a shorter continuation does not silently change the policy.
`resume_time` inherits saved accuracy settings; an explicit `accuracy=None`
disables the optional check. Existing checkpoints without this field retain the
fixed-step behavior.

## Browser and API

Expand **Time-step accuracy check** under the time setup or checkpoint
continuation controls. Enable refinement, enter the relative and scaled absolute
tolerances, and optionally enter a minimum trial interval in input time units.
The time report shows accepted discrepancy ratios and accuracy retries. History
plots and CSV include the ratio and time between reported endpoints. Saved
cases, computed solutions and physical checkpoints preserve the settings.
When a continued history changes to fixed steps, earlier discrepancy values
remain available and the new segment has gaps. The combined internal-step count
includes both checked and fixed portions, while accuracy summary statistics
describe the new segment.

The API accepts, for example:

```python
accuracy = {"rtol": 1e-3, "atol": 1e-6}
result = solve_time(model, duration=0.12, dt=0.06, accuracy=accuracy)
```

The same optional setting is accepted by saved-equilibrium launch and checkpoint
continuation. It defaults to `None` for a new analysis.

## Independent verification design

`scripts/verify-time-accuracy.py` records source hashes and physical values for:

- A two-kilogram mass on a damped axial spring, compared with its exact decaying
  sinusoid, including velocity, internal force and support reaction. Tolerance
  refinement, changed consistent length/time/force units and BDF midpoint
  checkpoint continuation are checked.
- A spring with an actuator-lag feedback controller and a command jump at a
  non-grid time, compared with an independent three-state matrix exponential.
- A rigid finite wing in a gust ramp, compared with direct straight-line
  Biot--Savart integrals and a circulation-lag matrix exponential. Circulation,
  circulation rate and rate-dependent load are checked. This reference is
  linearized; a smaller gust amplitude probes sensitivity to this approximation
  separately from tightening the temporal tolerances.

Native tests additionally cover BDF1 refinement, minimum-step failure, forcing
events and continuation at a large Earth origin, and rotation through the global
angle branch. The WASM replay independently evaluates its references at its own
adaptive times and compares common physical endpoints with native results;
it does not interpolate one runtime's trajectory onto the other's grid.

The completed native gust study measures maximum scaled errors of 3.6076e-7
and 2.6285e-7 under tolerance refinement. Halving the amplitude at the tighter
relative tolerance gives 2.8771e-7. These maxima do not decrease monotonically
with amplitude, so this study does not establish a linear-reference error floor
or separate temporal and linearization contributions using that norm alone.
The reference remains an explicitly small-disturbance comparison.

These checks do not establish arbitrary constrained-DAE accuracy, complete ASWING
compatibility, zero-airspeed behavior, or aircraft/experimental flutter validation.

The temporal browser workflows and inspected captures exercise the Canvas
projection fallback. A separate actual Three.js WebGL workflow now passes using
Mesa's software Vulkan driver in Chromium 145: an offline WASM equilibrium,
true-scale deformation, camera/shape controls and mobile resize. The equilibrium
residual is 6.41472e-14 and the test checks force balance, a healthy WebGL2
context, visible wing pixels and absence of page errors. All four captured
views were inspected and retained as `browser-renderer-{jig,deformed,top,mobile}.png`.

Earlier general SwANGLE probes could not create a context and recorded a GPU
process crash. The WebGL-only SwiftShader mode created a context object but
failed the actual application check when GL_VERSION returned null. An initial
Mesa probe was also blocked; explicit test-only driver selection and the GPU
blocklist override enabled a shader/readback probe and the final application
workflow. These failures remain in `browser-renderer-20261006.json` alongside
the passing job, source/asset hashes and verified driver packages. This new
workflow is additional evidence, separate from the ten temporal workflows;
neither software path establishes physical-GPU or cross-browser coverage.

## Recorded outcomes

The native study records these maximum errors, each normalized by the explicitly
listed physical scales in its JSON. They are measured trajectory errors, distinct
from the local discrepancy used to accept steps.

| Case | Method | Relative tolerance | Scaled absolute tolerance | Accepted report intervals | Maximum scaled physical error |
|---|---|---:|---:|---:|---:|
| spring | BDF2 | 0.01 | 1e-05 | 11 | 0.00579498 |
| spring | BDF2 | 0.0025 | 2.5e-06 | 15 | 0.00270484 |
| spring | Radau | 1e-05 | 1e-08 | 6 | 8.99075e-08 |
| spring | Radau | 2.5e-06 | 2.5e-09 | 9 | 1.78377e-08 |
| spring · alternate units | BDF2 | 0.0025 | 2.5e-06 | 15 | 0.00270484 |
| controller | BDF2 | 0.01 | 1e-05 | 13 | 0.00466338 |
| controller | BDF2 | 0.0025 | 2.5e-06 | 19 | 0.00188071 |
| gust | Radau | 0.0001 | 1e-08 | 5 | 3.60758e-07 |
| gust | Radau | 2.5e-05 | 2.5e-09 | 5 | 2.62852e-07 |
| gust · half gust amplitude | Radau | 2.5e-05 | 1.25e-09 | 5 | 2.87706e-07 |

The six packaged-WASM cases cover BDF2, Radau, alternate units, controller
forcing and two gust amplitudes. Each runtime independently evaluates its
reference at its own adaptive times. Comparing 39 physical endpoint
components gives a maximum scaled native/WASM difference of 2.88658e-12.
Adaptive time grids are recorded; they need not be bitwise identical, and no
interpolation is used to force agreement.

All 113 distinct targeted native tests have passing evidence across the
original and corrected runs. All 24 JavaScript checks and ten distinct final offline
browser workflows pass across eleven runs. The additional migration run restores
a case with all four new time-accuracy fields absent and checks the fixed-step
default and numerical input defaults. The browser's independently checked spring history
continues through both checked and fixed intervals, preserving old diagnostics,
correct internal-step totals, checkpoint policy and saved-result values.
The desktop/mobile captures match the inspected first-run captures byte for byte.

The first new native batch had one test failure: converted-unit output was
incorrectly evaluated using default SI conversion factors. Passing the actual
conversion factors fixed the test without changing its tolerances or the
production equations. Sixteen other new checks had already passed. A corrected
rerun printed a pass but its supervisor ended without recording child exit; a
subsequent run has recorded exit zero. The independent study also lost its first
supervisor. After confirming its child had stopped, it resumed from three
source-matched completed cases. Those original logs and incomplete status
records remain preserved. No interrupted run is relabeled as a successful run.

The first browser workflow passed before inspection found missing retained
internal-step counts and hidden earlier plots when a later continuation disabled
refinement. The final workflow exercises both corrected behaviors. It retains
gaps for unchecked steps rather than inventing zero discrepancies.

Artifacts: `time-accuracy.json`, `time-accuracy-wasm.json`,
`time-accuracy-checks.json`, and standalone `time-accuracy.svg`/`.pdf` figures.
The final release audit compares served modules/assets and complete source/local
ZIP contents against the tested bytes. It is recorded outside the archives at
`/tmp/openswing-time-accuracy-release-audit.json` to avoid a checksum cycle.
No hosted deployment or full-project regression is claimed.
