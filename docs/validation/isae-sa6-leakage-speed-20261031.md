# SA-6: velocity used in the stall leakage law

2026-10-31. The control-point and uniform-freestream speed interpretations
make the archived derivative comparison worse. The current bound-vortex
interpretation remains in production. This diagnostic supplies no new
registered pass and does not establish the original native settings.

The Technical Description explicitly evaluates lift velocity at the bound
vortex in equation 67. Equations 202–204 define stall leakage using the
section-normal speed without restating its evaluation point. This follow-up
tests that ambiguity while keeping the force law, wake, section properties,
targets and provisional 3% rule fixed.

All eight previously declared SA-6 pilot states are covered: four paired
aileron models, controls 4 and 44 degrees, and the finer 128-interval request.
They retain the separately qualified frozen-influence / strength-20 setup.
The three definitions change only the speed used in the section lift
coefficient and stall leakage equation:

- **Bound vortex:** the existing local relative velocity, including rotation
  and induction, projected perpendicular to the span.
- **Control point:** the corresponding relative velocity at the flow-tangency
  control point.
- **Uniform freestream:** the flight velocity projected perpendicular to the
  span, excluding local rotation and induction.

Every hypothesis still evaluates lift and profile force using bound-vortex
velocity, and stall drag using control-point tangency, as in the retained
interpretation of equations 67 and 70. Each new base solves its own nonlinear
equation; these are not changes to a derivative while keeping an inconsistent
base state.

| Leakage speed | Static coefficients | All state derivatives | Pitch-rate subset |
|---|---:|---:|---:|
| Bound vortex | 48/48 | 253/288 | 24/48 |
| Control point | 47/48 | 190/288 | 12/48 |
| Uniform freestream | 48/48 | 154/288 | 24/48 |

Neither alternative gains any passing check. Control-point speed loses 63
derivative checks and one static check; uniform speed loses 99 derivative
checks. Static agreement alone would miss the uniform-speed discrepancy.

For the 15%-chord aileron at 4 degrees:

| Derivative | Native ASWING | Bound vortex | Control point | Uniform freestream |
|---|---:|---:|---:|---:|
| CLa | 1.268730 | 1.257846 | 1.072178 | 1.341877 |
| CLq | 1.998780 | 2.091946 | 1.932769 | 2.106424 |
| Cmq | -0.462280 | -0.485471 | -0.446354 | -0.488962 |
| CXq | -0.009690 | -0.031125 | -0.044813 | -0.020988 |

A selected coefficient can move closer while the complete set gets worse.
The remaining SA-6 differences are therefore not resolved by either alternate
speed definition.

## Numerical verification

The diagnostic imports no OpenSwing modules. It independently constructs the
straight-wing horseshoe operators, solves circulation from zero, differentiates
the local stall equation, and integrates the published forces and moments.
Its bound-vortex control reproduces the retained production coefficients and
all state derivatives within 2.31e-13.

The completed run has 24 cold bases and 48 cold perturbation solves. Maximum
base residual is 2.83e-14 and maximum local normal Mach is 0.0611. All calls
finish. At two endpoint states, incidence and pitch-rate columns are checked
at centered steps 2e-5 and 1e-5. **23/24 individual stencils pass** the fixed
2e-6 absolute derivative gate; **all 12 finer-step checks pass**.

The control-point model at 35%-chord / 44 degrees has a coarse pitch-rate
stencil error of 2.45993e-6, decreasing to 6.14836e-7 at half the step. The
factor-of-four decrease is consistent with centered-difference truncation.
All 12 Richardson extrapolations also pass the same gate. The coarse failure
is retained and is not relabeled a pass.

Two initial attempts stopped at that check. The first had less tightly
converged nonlinear states; Newton polishing of the same equations did not
remove the coarse-step discrepancy. The final run retained the failed coarse
check and completed the finer stencil. The failed sources, plans and logs are
preserved separately. The first attempt did not retain an exact call counter,
so aggregate accounting is a range of 194–196 independent nonlinear calls,
including the final 72; the second and final attempts have exact counters.
These are independent diagnostic calculations, with zero production API calls.

The [retained plan](../../artifacts/isae/sa6-leakage-speed-20261031/plan.json),
[per-state comparison](../../artifacts/isae/sa6-leakage-speed-20261031/analysis.json),
and [verification receipt](../../artifacts/isae/sa6-leakage-speed-20261031/receipt.json)
include source/input hashes, every comparison, derivative stencils, and
termination accounting. Production physics and registered counts remain
unchanged; the complete project and SA-6 validation remain unfinished.
