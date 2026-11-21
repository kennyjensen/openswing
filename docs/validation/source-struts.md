# Struts and wires in the source beam operators

2026-10-30. Source static equilibrium, fixed/moving vacuum dynamics, fixed
still-air dynamics and moving airflow dynamics now accept `.asw` Strut
records. The browser and JSON boundary preserve the selected bilateral or
tension-only law through modes, frequency response and cold time integration.
Saved launches and checkpoints retain their saved law and reject overrides.

## Equations and implementation

Steady theory section 3.5 describes an axial member from a rotating beam pylon
to a body-fixed anchor. Unsteady section 6.4 explicitly retains the static
strut and joint laws. These loads were already assembled by the common
`StaticNetwork.residual`; source policy guards prevented their use. The change
removes those guards without adding another force, mass or degree of freedom.
The pylon force and its arm moment enter local equilibrium once. The opposite
anchor reaction makes the brace an internal load for whole-aircraft motion.

The declared law remains `T = EAw (L-L0)/L0`, directed along the current member,
where `L0 = |anchor-pylon_jig| + dLo`. Wire mode clips negative extension and
has zero force and energy while slack. Bilateral mode permits compression.
The printed steady Eq.141 force-vector ambiguity, undocumented historical
large-strain behavior and absent buckling-strength input remain unresolved;
this extension does not claim an authenticated ASWING compression model.
See [NUMERICS](../NUMERICS.md#axial-struts-and-wires).

The native source modes/frequency routes also needed to forward `strut_mode`;
the browser previously discarded it for several source policies. Both are
now explicit. Invalid laws are rejected. The existing modal/frequency check
still rejects a wire equilibrium at, or a difference stencil crossing, the
slack/taut boundary because it has no unique smooth tangent there.

## Independent checks

The new native suite passes **40 tests**:

- Exact parallel-spring stiffness and preload through all three source static
  request routes, including a compressed bilateral member and a slack wire.
- Exact elastic poles with real point masses, across fixed vacuum, fixed
  still air, moving vacuum and moving airflow. Axial motion has no strip
  apparent-mass contribution in this fixture.
- Powered fixed/free-frame frequency response with both dense and sparse
  assembly sizes. A massless beam has stiffness 100 N/m; the taut wire adds
  200 N/m. The free 2 kg / 3 kg system has an elastic pole at `sqrt(250)` rad/s
  and tip response `1/(750-3 omega²)` to a unit tip force. Refinement retains
  the same matrices. A slack wire correctly contributes zero stiffness.
- A finite offset pylon under nonzero frame motion: dense/sparse tangents
  agree with an independent sixth-order full-residual directional stencil.
- Free motion crossing from taut to slack, compared with two exact sinusoidal
  arcs joined with continuous position and velocity. The crossing occurs at
  **0.07588511617 s**. Halving the BDF2 step from 0.005 to 0.0025 s reduces the
  maximum displacement/rate error, normalized by 0.3 m / 3 m/s, from
  **0.39556% to 0.09963%**. Center-of-mass position and velocity remain constant
  within 2e-9 in the fixture's units. Restarting a checkpoint before the
  transition agrees with uninterrupted integration.

![Exact and computed motion and wire tension](../../artifacts/isae/source-struts-20261030/wire-transition.svg)

The first test attempts had two harness errors: checking a nonexistent
`strut_mode` identity field, and applying an unbalanced initial force while
expecting a stationary free-frame preload. The corrected tests use the
reported brace law and equal/opposite preload forces. No force equation or
tolerance was changed to accommodate those failures. A regression assertion
also needed the new invalid-law error message. Original logs are retained.
Its isolated rerun exposed an existing test import-order dependency: subclasses
must load before their base class is replaced by a construction sentinel. The
eight corrected rejection cases pass in isolation, completing 295 distinct
affected regression checks. All 205 JavaScript checks pass.

The offline browser verifies powered frequency response and matrix reuse,
time response and checkpoint continuation, a shifted elastic eigenmode, and
three saved/reopened solutions retaining wire selection. Mobile rendering
has no horizontal overflow or browser exceptions. The final build also removes
the obsolete zero-offset help-text statement that struts are unsupported.

The WASM transition comparison uses a tighter nonlinear tolerance of `1e-12`
to compare net support forces after cancellation. At `1e-10`, one nearly zero
component differed between native and WASM by 9.5e-10 N, exceeding the retained
3e-10 absolute output comparison tolerance. The output tolerance is unchanged;
the first failed attempt is retained. Vacuum snapshots do not have aerodynamic
`force` fields, so the harness compares their physical applied/support loads.
All seven WASM cases pass **10,769 scalar comparisons**, using the same 132
kernel modules as the packaged browser. The cases include both powered frame
choices, taut/slack elastic poles, powered time response, the wire transition,
and a static slack-wire solve.

The [evidence directory](../../artifacts/isae/source-struts-20261030/) contains
native logs, exact-oracle results, seven JSON runtime requests, WASM comparisons
and the offline browser scenario. [Machine-readable completion evidence](source-struts.json)
records final check counts and artifact hashes.

## Remaining work

No aerodynamic equation or ISAE acceptance count changes. Full-aircraft
strut/wire validation against native ASWING remains open. Bodies, stepped axes,
feedback and inverse actuator/history targets remain unavailable in source
airflow dynamics. Fixed vacuum/still-air policies still do not support time
integration; the moving policies provide that route. The full project goal
remains incomplete.
