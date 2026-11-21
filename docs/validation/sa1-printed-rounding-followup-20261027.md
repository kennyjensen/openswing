# SA-1: bounding printed-input uncertainty

SA-1 remains **19/154 registered checks passing**, with all 22 baseline jobs
complete. No production solver change is established by this follow-up.

The [previous native-distribution study](sa1-native-distribution-followup-20261027.md)
found an inconsistency in a conditional interpretation of archived rectangular
convergence data. The N12 current-influence reconstruction left a force residual
whose direction could not be produced by nonnegative profile drag at the assumed
local force samples. That earlier result held the printed local lift values and
coordinates fixed. The new calculation bounds their uncertainty as well.

## Result

For N12, **rounding of the specified printed quantities cannot explain the
current-influence inconsistency under the declared sampling model**. The
force-direction deficit remains at least **0.00170 N** after allowing every
retained coordinate, local `cl`, incidence, total-force and dynamic-pressure
token to vary over its half-last-place interval.

| Convention | Enclosed lower-direction margin | Conclusion under the declared conditions |
|---|---:|---|
| Current influences | −0.0146005 to −0.00170277 N | Entire interval violates the necessary condition |
| Frozen zero-angle influences | −0.00145969 to +0.0112474 N | Bound does not establish a violation |

A compatible profile residual requires a nonnegative margin. The frozen result
is inconclusive; an interval containing zero does not prove that a valid state
exists. Neither result determines the archived F setting or establishes ASWING
parity. These are two diagnostic interval-enclosure calculations, not additional
registered checks or new forward aerodynamic solves.

## What was bounded

The [protocol](../../artifacts/isae/sa1-native-cl-rounding-20261027/protocol.json)
was recorded before execution. It retains both conventions and all outcomes.
Each of the 13 distinct node coordinates and 12 local `cl` samples has its own
printed-precision interval. The two root records share one coordinate. Equal
printed values on opposite sides do not impose exact symmetry. Native incidence,
Fx, Fz and dynamic pressure retain their own intervals.

Writing `g = Gamma/U` removes speed from both inverse equations. Force is then
`2*q*g*(vhat cross span_direction)` per unit span, so separately rounded density
and speed do not introduce spurious uncertainty. The native `Dyn.Pr.` interval
is used directly. The declared straight, untwisted, isolated geometry, local
chord of 0.2 m, zero spanwise flow and zero PG Mach remain conditions of the
model; this calculation does not bound uncertainty in those conditions.

The implementation uses 70-digit decimal arithmetic with outward rounding,
bounded square roots and trigonometric series. An exact radical expression and
its coordinate monotonicity bound each Glauert midpoint without inverse-trig
dependency inflation. The uniform fixed-point contraction bound is **0.154790**,
below one for both conventions. It establishes one positive fixed point for
every permitted parameter combination. A residual bound encloses that fixed
point about the previous nominal reconstruction; 30 prescribed interval
intersections refine each enclosure.

The force integral retains shared-coordinate cancellation through an exact
summation-by-parts identity. This avoids treating adjacent interval lengths as
independent when they share a node. The necessary direction condition allows
arbitrary nonnegative strengths of profile force; no drag coefficient or input
value is fitted to the native forces.

An independent mathematical review found no blocking issue in the implementation.
The [certificate check](../../artifacts/isae/sa1-native-cl-rounding-20261027/verification.json)
reconstructs all 60 retained enclosure stages and evaluates the force margin
with a second exact summation identity. Its current-influence upper margin is
−0.001702765 N, preserving the exclusion. The checker shares the reviewed decimal
arithmetic primitives; it is not an independent interval-arithmetic library.

## The remaining interpretation matters

The [primary-source audit](../../artifacts/isae/sa1-native-cl-rounding-20261027/sampling-source-audit.md)
confirms Glauert-angle sampling and the bound-vortex lift location in steady
Eqs150–155. It also supports bound-vortex velocity in the ordinary Eq70 profile
terms; only the stall-leakage scalar explicitly carries the control-point
subscript. Replacing all profile speeds with control-point speed is unsupported
by those equations.

The native `cl` exporter's exact sampling/recovery is less explicit. The guide
places derived values between nodes and on the preceding output row, but does
not distinguish arithmetic and Glauert midpoints. Its coefficient definition
does not independently authenticate an exporter location. The mapping from
aerodynamic samples to integrated structural loads is also unresolved.

Consequently the exclusion applies to the **combined conditional interpretation**:
local chord/geometry, native `cl` recovery at the assumed force samples, and the
entire noncirculation force being nonnegative profile drag at those samples.
Changing any unsupported part of that interpretation can change the result.
The retained 5.99 documentation also does not establish the exact behavior of
the historical producer. The result rules out rounding as a repair for this
interpretation; it does not justify a production formula change or select a
different convention by numerical agreement.

The original SA-1 model, native table, acceptance criteria and all 123 recorded
production modules remain unchanged. The next investigation must resolve a
documented sampling or load-recovery rule before changing the solver.
