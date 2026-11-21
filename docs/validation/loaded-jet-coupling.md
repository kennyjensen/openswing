# Daedalus yaw investigation: loaded propeller–fin coupling

The [log–log axes, decade labels and minor grids](bode-log-axes.md) are
implemented. The full Daedalus rudder-to-yaw curve still differs from
[Drela’s published response](https://web.mit.edu/drela/Public/web/aswing/rudder-bode.pdf).
This component investigation adds independent checks of moving propeller/fin
coupling. It does not identify a production correction for the aircraft curve.

## Physical scope

A loaded fin interacts with a positive-thrust propeller jet. Fin circulation
changes the velocity at the engine; that changes jet strength and the fin’s
flow, closing a nonlinear feedback loop. The test prescribes either engine
rotation about an oblique axis or fin translation along an oblique direction.
The engine and fin move independently, so this is not a structural mount or
free-aircraft model. Input units are radians of engine rotation or metres of
fin translation, not rudder deflection.

The two-metre fin has 0.75 m chord, 2° incidence, `Xax=0.35`, lift slope `2π`,
`Cdf=0.01`, `Cdp=0.02` and `Cm=0.02`. Speed is 10 m/s and density is
1.225 kg/m³. The engine has 0.6 m radius, 80 N thrust and −2 N·m shaft torque.
Its downstream axis is parallel to `(1,0.12,0.08)` and its centre is
`(−1,0.25,0.2)` m. The [complete fixture](loaded-jet-fixture.json) and
[literal ASW model](loaded-jet-fixture.asw) retain all positions and motion axes.

The independent [reference](../../scripts/loaded_jet_fin_reference.py) imports
no production aerodynamic or geometry functions. It integrates vortex fields
directly, independently integrates the spreading-jet profile, solves the
nonlinear circulation base and differentiates its residual and full load model.
The equations follow Drela’s
[steady theory](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf) and
[unsteady extension](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf).
The reference retains the documented wind-centred jet geometry with velocity
directed along the engine axis; this agreement does not independently validate
that empirical convention against experiment or the original executable.

Cases use 4/8 fin intervals, 0.1/1/10 Hz and circulation lag off/on.
Checks include every circulation coefficient and six force/moment components
for the fin, engine and their sum. Total, circulation-rate, apparent and
remaining loads are checked separately, including engine follower loads and
moment-arm changes. Fixed 16/32-point reference quadrature, two complex-step
sizes, branch clearances and positive subsonic flow are checked. Every physical
component uses `abs(error) <= 2e-8 + 2e-8*abs(reference)`.

## Retained failures and refinement

The first attempt stopped before any production evaluation because the new
reference transposed an engine-field contraction incorrectly. Correcting that
reference storage orientation left the production equations and fixture intact.

The corrected run completed eleven four-interval cases, then failed the larger
output perturbation for the 10 Hz, lag-enabled translating fin. Total axial
force for the fin and combined system exceeded the unchanged tolerance; the
largest gate fraction was 1.51948. Its circulation solution, quadrature and
harmonic-equation checks passed. The run stopped before its second perturbation
or any eight-interval case. The original failure remains in the evidence.

A saved-data decomposition traced the difference to the finite-width derivative
of circulation-rate lift. A separate diagnostic held the already solved complex
circulation exactly fixed and evaluated only eight new output probes. Halving
the perturbation twice reduced the original fin-force error from `1.039e-6` to
`2.595e-7` and `6.450e-8`, consistent with second-order stencil truncation.

| Output perturbation | Maximum fraction of allowed component error | Result |
| --- | ---: | --- |
| `1e-5` m, retained original | 1.51948 | Failed |
| `5e-6` m, same solved state | 0.38123 | Passed |
| `2.5e-6` m, same solved state | 0.09435 | Passed |

The successive differences in the original worst component contract by 3.995.
Extrapolation is saved as a diagnostic only; acceptance uses the directly
measured responses. No tolerance or physical parameter was changed. This
fixed-state output refinement does not replace the unexecuted second harmonic
solve and output-probe set of the original case. Both forcing matrices had
already been assembled before that case failed.

The twelve previously unexecuted eight-interval cases then ran with declared
perturbations `5e-6` and `2.5e-6` in each input’s units. All twelve completed,
with 3,501 checks passing. The largest circulation-error gate fraction is
0.05204; the largest force/moment fraction is 0.35769. That run uses 210
production evaluations, 14 independent field assemblies and 54 small solves.
The two meshes have nonzero induced engine inlet velocity and nonzero
circulation-to-jet feedback; neither reduces to a frozen-inlet linear example.

Together these are **23 completed two-width cases plus one four-interval case
with separately verified output-width refinement at its saved harmonic state**.
They are not a clean pass of the original 24-case plan. Across the corrected
four-interval run, its refinement and the eight-interval run there are 392
production evaluations. The first failed reference attempt and the separate
four-case regression retain their own operation counts.

## Durable regression and evidence

The [focused regression](../../tests/test_loaded_jet_coupling.py) passes all four
one-hertz cases: both prescribed motions with lag off/on, using four fin
intervals. It shares one independently solved nonlinear base and compares the
full nonlinear production residual and loads along independently solved
harmonic directions. It uses 20 production evaluations and seven small
reference solves. The maximum normalized residual is `1.80e-11`; the largest
load error uses 3.15% of its allowed tolerance.

A separate saved-data audit passes **15,746 checks**. It reconstructs raw
load sums, derivative stencils and saved harmonic equations, while explicitly
retaining the expected coarse-probe failure. It uses 99 small saved matrix
products, with no model/reference imports, physical evaluations or solves.
The earlier failure decomposition used three additional saved products.
Every numerical child exited and was reaped; no failed run was overwritten.

[Machine-readable results](loaded-jet-coupling.json) and the
[reproducible evidence archive](loaded-jet-coupling-20261025-evidence.zip)
retain both failures, the narrower-width diagnostic, final runs, source hashes
and process closeouts. The archive includes reconstruction instructions and
stores the identical production source snapshot once. No production kernel,
physics default, browser build or hosted deployment changed in this increment.

This checks finite discrete component equations. Full loaded/deformed structural
and free-frame feedback, the published operating point, the near-1 Hz yaw
minimum, higher-frequency aircraft mesh convergence and a nonlinear rudder-step
comparison remain unresolved. No broad requirement or ISAE case becomes fully
validated.
