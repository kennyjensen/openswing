# Inverse motion histories and accepted-step restart checks

The integrated kernel has 69 modules. It adds actuator constraints for 25 motion
and reference-flow quantities, consistent cold initialization, BDF position-history
coordinates, guarded saved-equilibrium history launch, and recorded-step replay
on checkpoint restoration. The current mounted-equilibrium optimization remains
in place. Scoped integration validation passes; the records below distinguish
earlier isolated numerical evidence from current-checkout acceptance.

## Quantities and physical conventions

The public ASWING guide's parameter-file table lists V, A, B, Wx/Wy/Wz,
RX/RY/RZ, Ex/Ey/Ez and Ga, alongside the previously implemented force, moment,
acceleration, flap and engine labels. The new catalog implements those 13
motion/flow labels plus 12 explicitly named Earth-vector extensions. See the
[published documentation](https://web.mit.edu/drela/Public/web/aswing/) and
`openswing/time_history.py`. Catalog tests use an independently written expected
map, and the browser fixture checks the same quantities and units.

V currently means gust-relative equivalent airspeed; exact ASWING indicated-speed
parity is unresolved. Position is at the body origin, velocity at the velocity
reference, and acceleration at the acceleration reference. Body angular-velocity
labels use degrees per input time in tables and radians in the kernel. Explicit
Earth angular vectors use radians. Angular velocities are not Euler-angle rates.
Periodic residuals retain a local continuous branch during initialization;
multi-turn angle histories and singular angle charts are not supported.

Cold initialization retains the declared frame pose, velocity, angular velocity
and local velocities. It solves elastic shape, circulation and actuators using
the physical residual and differentiated constraints. Incompatible initial
targets are refused. Controller initial values remain prescribed; their rates
need not vanish. Finite probes reject witnessed nonsmooth controller alternatives;
they do not prove arbitrary global or nonsmooth uniqueness.

## Numerical accuracy and restart meaning

For a typed kinematic inverse target in BDF, the nonlinear residual tolerance is
`requested / K / K`, where `K=max(1, sum(abs(actual BDF coefficients))/rate_scale)`.
No absolute tolerance floor is added. Unrepresentable gates are refused.
Ordinary load/acceleration targets retain the requested tolerance, and Radau's
existing stage policy is unchanged. This addresses observed amplification of
small velocity residuals into actuator-force errors; it is not a global force
error bound and does not remove temporal truncation or predecessor error.

New checkpoints own the actual accepted BDF stencil or Radau stages, physical
inputs, endpoint and convergence gate. Restoration re-evaluates those recorded
discrete equations without solving another state. This rejects corruption that
can satisfy an instantaneous force balance while violating the accepted step.
Initial and legacy checkpoints explicitly retain physical-only validation.
Recorded-step consistency does not authenticate an entire trajectory, establish
continuous initial consistency, prove root uniqueness or provide a global error
bound. Legacy BDF records retain their original acceptance tolerance.

A saved history launch currently supports one nonrotating Earth-velocity target
with force-only mixed frame constraints, unchanged loads, no controller or gust,
and a smooth cubic table with distinct increasing times extending strictly
beyond the run. The saved physical state is held while initial accelerations and algebraic settings
are completed. Snapshot/checkpoint 0 is the completed right state. The original
before-input snapshot and source equilibrium are separately owned in
`launch_transition.before_input`. Continuation keeps the original smooth table;
unsupported replacements, cutoffs and missing scope records are rejected. The
[smooth-table extension](saved-spline-histories.md) uses scope version 2 while
preserving the two-knot contract of existing version-1 checkpoints.

## Retained isolated native evidence

Archives and exact hashes are in
[`inverse-histories/prior-native-evidence.json`](inverse-histories/prior-native-evidence.json).
Each archive identifies its own numerical source; their results are not relabeled
as new current-checkout or browser tests.

- Cold initialization: ambiguous-controller refusal and unique-boundary positive
  mechanics on the composed 65-module source, with the original counterexample
  and finite-arithmetic failure preserved.
- Composed mechanics: independent tip/controller and position-history BDF/restart
  checks on that source.
- Curved BDF accuracy: the original run failed 16 physical gates despite meeting
  its requested residual tolerance. The stricter 67-module candidate passed the
  unchanged physical gates for BDF1, BDF2 and checked BDF2, with no rejected steps.
  The original failure remains in the archive.
- Saved launch on the exact 69-module kernel: value-jump rejection, held-state
  spring launch with Radau continuation, and BDF1/BDF2 from the same initial
  checkpoint passed 231 assertions across three actual attempts. Maximum force
  errors were 6.76e-13 N for Radau and 7.96e-11 N for BDF; these are fixture results,
  not general accuracy bounds. The ordinary saved-launch output remained exactly
  equal to the 67-module baseline, including all 4,867 numeric values.
- Accepted-step validation and 23 legacy restores preserve original reports and
  residuals. Initial records retain their weaker, explicitly reported scope.

## Current-checkout validation

The [integration summary](inverse-histories/integration.json) records exact source
hashes, counts, runtime and scope. The
[portable integration evidence](inverse-histories/integration-evidence.zip)
has SHA256 `a2554e7010377c3a3f0c866581861b1786b69d1d903a0125a6c7a795611b3f19`.
Its CRC, exact member set, and fresh-extraction verifier pass. The verifier checks
retained bytes and independent native/browser/WASM mechanics without importing
the production solver. Original failed fixture results are included unchanged.

The native, packaged-WASM and browser checks pass. Reproducible
entry points are `scripts/verify-inverse-histories.py`,
`scripts/test-inverse-histories-wasm.mjs`, `tests/inverse_history/`, and
`tests/browser/inverse-histories.spec.js`. The public mechanical oracle uses
independent BDF recurrences and the exact Radau discretization of a spring model.
The browser test exercises an actual offline solve, target/achieved/residual
plots and CSV, mobile navigation, and checkpoint continuation.

The first current-checkout selection passed 349 cases and failed four scalar
retry-fixture cases because their synthetic network could not be serialized by
the new recorder. The fixture now intercepts record capture as well as snapshot
capture; all four retry/fatal-refusal checks pass. This changes no numerical
code, and does not reclassify the original failed attempt. All 60 standalone
JavaScript tests pass. Current collection is 1,645 tests; no full-suite pass is
claimed. A further 72 existing time-actuator, saved-launch, checkpoint and full
tangent cases pass, giving 425 distinct passing selected native cases across
the corrected fixture and the two selections.

The current public curved-velocity BDF2 solve and continuation accept four steps
with no rejections. Against the independent discrete recurrence, maximum force
error is 1.72e-9 N and velocity error is 2.19e-11 m/s. The saved spring launch
also passes in packaged WebAssembly, including both checkpoint restores;
maximum force error is 6.57e-13 N and shape error is 9.99e-16 m.

One actual offline production-browser workflow passes on the 69-module kernel:
curved-velocity solve, target/achieved/residual/input series and CSV, 390-pixel
mobile navigation, then continuation from the selected computed checkpoint.
There were no page errors or external network requests. The completed workflow
took about eight minutes on the shared host; no interactive-performance claim
is made for cold inverse initialization. Its retained screenshot still uses the
existing three-significant-digit axis labels, which can duplicate nearby tick
labels; CSV and point tooltips retain more precision.

After that browser run, one static help sentence was corrected to distinguish
ordinary saved launches from motion-history launches. No executable JavaScript
or numerical code changed in this follow-up. The tested text and exact diff are
retained with the integration evidence.

The default mounted 48-panel result exactly matches the previous optimized
result, including the same 1,900 residual evaluations. The full canonical
physical-output SHA256 remains
`72f9305baa696d92101e1cab3a21ab9338871abc2befb56c51c66cdef3aa3eac`.
This run took 33.23 seconds on the shared host; timings from different runs
are not treated as a fixed performance guarantee.

## Remaining full-goal work

Arbitrary history combinations, saved position/attitude histories, controller
and load changes at saved launches, events/cutoffs, broader initialization and
restart compatibility, exact ASWING conventions and aircraft-level comparisons
remain unfinished. Full browser/WASM validation across those combinations is
also required. All 40 broad requirements remain Partial; the full ASWING goal is
active and incomplete.
