# Daedalus: independent complete harmonic balance

An independent calculation now closes all **2,044 equations** along the saved
Daedalus rudder responses at 1 Hz and 1.15737773741517 Hz. The largest normalized
discrepancy from the saved matrix action is **1.08943e-11**. This found no
corrective change to production physics. The latest corrected-mesh yaw response
remains 28.1% high at 1 Hz and **2.172 times** Drela's drawing at its dip; roll
at 1 Hz remains 32.7% low. There is no new aircraft trim or frequency sweep.

This extends the [complete aerodynamic check](daedalus-full-aero.md) through
the independent state and gravity transformations, aerodynamic load transfer,
real inertia, structural equilibrium, rigid attachments, braces, and free-flight
balance and kinematics. The existing corrected C16 cruise project supplies the
loaded state: 6.7 m/s, Mach 0.1, 108 nodes, 103 elements and 82 lifting panels.

## What was independently calculated

The independent implementation reconstructs node poses, velocities and
accelerations, the flight frame, circulation and the rudder input from the raw
saved response coordinates. Gravity rotates from Earth axes into body axes;
the nonzero baseline Earth-position drift is retained. No captured native
velocity, force or residual is used as an expected physical load.

Aerodynamic loads retain the previously checked complete lifting/body/point/jet
model and are transferred to nodes by independent virtual-work maps. Real
mass and CG offsets are integrated over the original material lengths, with
independent material-frame interpolation. Point masses retain their pylon
arms. The force and moment equations include loaded internal resultants,
reaction arms, rigid-joint geometry and both bilateral braces. The six
free-flight equations sum external loads before internal/support assembly.

The full row coverage is:

| Equations | Rows | Independent calculation |
| --- | ---: | --- |
| Loaded beam compatibility | 618 | Previously derived complete compatibility matrix, applied to the exact saved raw responses |
| Node force and moment balance | 648 | New composed loads and structural assembly |
| Rigid attachment constraints | 30 | Independent geometry and rotation maps |
| Circulation | 82 | Independent complete aerodynamic residual |
| Free-flight force and moment balance | 6 | Sum of independent external loads |
| Node and flight-frame kinematics | 660 | Independent descriptor/state transformations |

The harmonic convention is `(i*omega*M - A)*Z = B`; the corresponding residual
direction is `A*Z - M*(i*omega*Z) + B`. Only the real response directions include
the unit native rudder input. All four complete residual directions close.

## Results and numerical checks

An initial assembly-only pass uses the existing captured external loads as
explicit inputs and passes 2,466 checks. The subsequent complete composition
replaces those inputs with independent aerodynamic, inertia and gravity loads.
It passes **3,823 array comparisons**, covering 700,110 scalar comparisons.
These are checks of one aircraft base and four response directions, not
thousands of independent aircraft cases.

| Check | Largest absolute difference |
| --- | ---: |
| Complete normalized residual direction versus saved matrix action | 1.08943e-11 |
| External nodal force/couple direction versus native stencil | 1.75674e-10 |
| Independently reconstructed physical input chart | 7.10543e-15 |
| Quadrature refinement, any retained directional output | 1.06581e-14 |
| Complex-step refinement, any retained directional output | 1.24345e-14 |

Physical loads use the model's native force/moment units per native F3 unit.
The fixed load/directional gate is `2e-7 + 2e-7*abs(reference)`. The input-chart
gate is `2e-12 + 2e-12*abs(reference)`; conservation uses `2e-10` absolute and
relative tolerances. Vortex quadrature orders 16/32 and mass quadrature orders
8/16 are compared, with complex steps 1e-24/1e-20. Native fourth-order stencils
at widths 1e-3 and 5e-4 reuse the 33 previously captured residual evaluations.
The complete independent evaluation runs 18 times and performs no aircraft,
circulation or harmonic solve.

The first composed report correctly retained a failure: four provenance checks
compared raw response directions with a prior archive's normalized directions.
The original producer explicitly divided by each direction's infinity norm.
A saved-data correction confirms exact equality after that normalization; the
physical computation already used the correct raw directions. No physical
array, evaluator, setting or tolerance changed, and no physics was rerun.
Both the original failure and its correction are retained.

A separate saved-array review passes 5,163 checks and exactly reconstructs all
four complete residual directions. Its initial review-only mass-sign error
and correction are also retained. Five portable tests pass against the current
native implementation, using 17 full residual calls and 19 expected-array
comparisons; their largest complete-row difference is 1.95607e-11. Neither
review nor regression performs a trim, linearization or harmonic solve.

## Scope and remaining work

This verifies the declared discrete equations at the actual stationary loaded
aircraft and four selected directions. It does not establish equality of every
tangent column or the historical ASWING executable. Parsed material samples,
topology and the saved operating point remain input assumptions. Material
interpolation and ASWING's exact spline endpoint conventions still need
independent actual-file validation.

The actual file has zero intrinsic point/distributed centroid inertias, point
spin and additional `D` mass fields. This comparison therefore exercises real
translational mass, distributed CG offsets, point pylon arms and gravity
transport; it does not add nonzero tensor/spin coverage. The reference retains
the complete first-order terms at the stationary base and is not a finite-motion
time integrator. Existing body apparent-mass and endpoint conventions retain
the qualifications in the [aerodynamic report](daedalus-full-aero.md).

The historical reference operating point, complete Bode agreement and
higher-frequency mesh convergence remain unresolved. No broader requirement or
ISAE validation status is upgraded by this result.

The [published rudder plot](https://web.mit.edu/drela/Public/web/aswing/rudder-bode.pdf)
identifies only operating point 1. Its accompanying 0.2/1 Hz movies likewise do
not specify speed, attitude or trim controls. The 6.7 m/s comparison speed comes
from Daedalus's design-cruise specification, not a verified setting for this
plot. The [existing speed study](daedalus-rudder-speed.md) demonstrates a large
response change with operating point, but the tested settings do not reproduce
all reference curves.

## Reproduce and inspect

The portable tests compare current native base loads and full residuals, plus
four fourth-order directional stencils, with the independently saved arrays:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q tests/test_daedalus_full_balance.py
```

The [machine-readable report](daedalus-full-balance.json) and
[evidence archive](daedalus-full-balance-20261025-evidence.zip) retain the
independent source, material inputs, original comparisons, corrected metadata
check, saved-data reviews and regression results.
