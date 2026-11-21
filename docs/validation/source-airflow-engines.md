# Engines in source airflow dynamics

2026-10-30. The `drela-moving-airflow-v1` route now accepts engine types 0/1/2
for coupled modes, frequency response and nonlinear time histories. This
extends [source airflow dynamics](source-airflow.md). It does not establish
archived ASWING aircraft agreement or change any ISAE acceptance count.

## Loads and a corrected derivative

The existing engine equations evaluate the moving attachment's local inflow
and angular rate, including body motion and elastic pylon motion. Thrust,
torque, P-factor loads and optional jets enter through the shared aerodynamic
evaluator. The source beam receives each engine force and moment once, with
its attachment moment arm. Real mass, inertia and rotor angular momentum
come from separate `Weight` records, not from the engine's spin setting.
Those records enter the source endpoint inertia operator once.

The new nonfrozen, powered matrix check exposed an actual derivative error.
The source residual measures a deformed interval using its averaged endpoint
frames, but the optimized geometry derivative still used the older
straight-chord length formula. Interval length affects the vortex core at
external receivers, including engines, so the inconsistency propagated
through engine inflow and jets into the response matrices. Same-surface
zero-core checks and frozen-influence checks did not expose it.

With `Rbar = (Ra + Rb)/2`, the residual's interval measure is
`u = solve(Rbar, rb-ra)` and `length = norm(u)`. Its derivative now uses
`du = solve(Rbar, d(rb-ra) - dRbar @ u)` and
`dlength = dot(u, du)/norm(u)`. The legacy operator retains its own measure.
No vortex-core convention, force formula or tolerance was adjusted.

Before the correction, the largest dense/sparse A-matrix discrepancy was
`9.04e-7` and persisted at three differentiation steps. Independent
sixth-order residual differences agreed with the dense column to about
`1e-10`. Replacing the optimized geometry fields with physical stencils
removed the discrepancy, and field isolation located a `1.06e-5` engine
inflow derivative error. The retained diagnostic files record these failures.
After the correction, both frozen and moving-influence matrix tests pass
their original gates against the full residual.

## Independent checks

The 16 new native tests cover:

- Zero-motion equivalence to the steady source operator for all three engine
  types, including jets and a separate frozen-influence case.
- Direct radial/azimuthal blade-force integration at both spin signs, with
  finite attachment rotation, elastic velocity/rate and body rotation. This
  independently checks P-factor coefficients and concentrated load transfer.
- Rotor gyroscopic torque obtained by differentiating Earth-frame angular
  momentum. It enters once through the separate point weight.
- An exact two-mass axial spring driven by engine power, with prescribed and
  free frames and both dense and sparse response matrices. Reusing the same
  matrices for extra frequencies preserves the analytical response.
- Full powered descriptor matrices with positive jets and nonzero body
  motion, compared with independent full-residual directional differences.
- A power step, time refinement and checkpoint continuation. For the free
  frame, halving the BDF2 step from `0.005` to `0.0025` reduces the scaled
  displacement/velocity error from `0.00161923` to `0.000405857`. For the
  prescribed frame it decreases from `0.000634207` to `0.000158717`.
  The free-frame center-of-mass balance is checked independently.

All **16 new tests and 183 affected regression tests pass**. The complete
JavaScript suite passes **200 tests**. The shipped WASM kernel passes
**631 grouped comparisons covering 2,729 scalar components** against five
native requests: prescribed/free power response, a physical propeller with
jets, a mode and a power-step history. All 132 shipped Python modules are
checked against their native bytes. The analytical tests provide physical
references; native/WASM agreement by itself does not validate the physics.

Browser and distribution verification are recorded in the
[machine-readable summary](source-airflow-engines.json) and the adjacent
[artifact directory](../../artifacts/isae/source-airflow-engines-20261030).
The browser scenario exercises offline engine-power response, frequency
matrix reuse, checkpoint continuation, a shifted mode, and saving/reopening
all three analyses. Its source is
[`source-airflow-engines.spec.js`](../../tests/browser/source-airflow-engines.spec.js).

Initial test failures are retained: two harnesses assumed internal output
keys or API names, and checkpoint comparison initially required exact
floating-point equality for engine coordinates. Correcting those harnesses
did not change the solver. The remaining matrix failure required the real
interval-length derivative correction described above.

## Remaining scope

Bodies, struts, stepped axes, feedback and inverse actuator/history targets
remain unsupported in this source dynamics route. Vacuum policies still
reject engines. General powered-aircraft mesh/time refinement and archived
modal, Bode and trajectory comparisons remain open. This increment does not
resolve the Daedalus Bode or SA-1–SA-5 discrepancies. `ISAE_STATUS.md` and
the provisional 3% reference-output tolerance remain unchanged.
