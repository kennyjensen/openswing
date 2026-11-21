# FFWT-4 rigid attachments: continuous dynamic matrices

The explicit-extension and endpoint-pylon models now agree in their complete
continuous dynamic matrices, including velocity and acceleration terms.
Ten comparisons cover both retained beam ends, body and lifting-surface
material coordinates, two differentiation steps, and stationary-frame
controls. All use fully converged rigid, clamped vacuum equilibria.
The largest scaled coefficient difference is **2.562e-10**; independent
spatial-inertia and velocity-coefficient errors are **8.466e-12** and
**5.060e-11**. All unchanged numerical gates pass.

This extends the [steady-matrix study](isae-ffwt4-rigid-extension-20261106.md)
and [integrated single-axis comparison](isae-ffwt4-rigid-time-20261106.md).
It closes the local-rate/acceleration matrix gap for these synthetic models.
It does not change production attachment handling, establish native input
semantics, or add native matches. FFWT-4 remains **200/8,000**.

## Production equations and reduction

Each comparison builds the actual sparse `DynamicSystem` matrices from
`linearize`, using the production state derivatives and `descriptor_mass`.
The point object has mass 0.7, a full positive-definite inertia tensor with
nonzero products of inertia, and nonzero stored angular momentum. Moving
cases include nonparallel reference-frame rates and accelerations. All beams
are massless, exactly rigid and have zero material damping. There is no
airflow. The original synthetic fixtures and current 138-module kernel are
authenticated; no original ISAE file is rewritten.

The complete descriptor equations are `A z - M zdot = 0`. Directly comparing
their entries after deleting an anchor would be inappropriate: auxiliary
velocities and position constraints must first be accounted for. For each
complex growth rate s, the calculation:

1. Forms the full production pencil `A - s M`.
2. Eliminates local velocity variables in **both** models.
3. Converts state and equation scales back to physical units.
4. Eliminates the explicit extension's poses, internal loads and joint
   reactions, retaining every equation and variable on the original beam.

The full systems have 180 and 90 variables; both reduce to the same 60
retained mechanical variables. Their reduced operator is quadratic:

```
K(s) = K0 + s K1 + s² K2
```

K0, K1 and K2 are extracted separately and compared entry by entry. The full
operators also agree at six real/complex s values per case, through 10i s⁻¹.
The maximum departure from the quadratic representation is 1.560e-13.
This is a continuous-time comparison; it does not discard the previously
observed finite-BDF differences.

## Independent inertia and gyroscopic checks

Let `B x = b × x` for the point's offset b from its retained anchor, and
`O x = Omega × x` for the reference-frame angular velocity. Let J be the
point's complete inertia tensor and H its stored angular momentum. Expanding
rigid-point acceleration and angular momentum gives the independent blocks
of the force/moment residual:

```
K2 = -[ m I        -m B        ]
      [ m B         J - m B²  ]

K1 = [ -2m O         2m O B                              ]
     [ -2m B O       2m B O B - J O + S(J Omega + H) - O J ]
```

These blocks are placed at the retained anchor; all other entries of these
two coefficients must be zero for this massless-beam fixture. This checks
all three translational and all three rotational directions, including
parallel-axis inertia, Coriolis forces, gyroscopic couples and spin.

| Retained material coordinates | Maximum coefficient-pair difference | Maximum independent inertia error | Maximum independent velocity error |
| --- | ---: | ---: | ---: |
| Body | 2.562e-10 | 8.466e-12 | 3.941e-11 |
| Lifting surface | 1.742e-10 | 8.466e-12 | 5.060e-11 |

Values are scaled arithmetic differences `abs(actual - expected)/(1 +
abs(expected))`, **not native-error percentages**. The gates are 2e-7 for
paired operators, 2e-10 for independent inertia, 2e-8 for velocity terms and
2e-10 for the quadratic representation. They were set before the runs.

Twenty-four independent reference-formula tests pass. They check positive
spatial mass, kinetic energy, and complex-step derivatives of direct vector
force/moment equations over eight full-tensor cases, with and without frame
rotation. Deliberately omitting the pylon arm, spin or frame rotation fails
the corresponding comparisons by orders of magnitude. Thus agreement cannot
be attributed to all the relevant entries being zero.

## Separate saved-matrix audit

The assessor does not repeat the producer's Schur-complement implementation.
It inverts the **complete saved descriptor pencil** and selects the retained
physical compliance block. All 30 additional comparisons pass at held-out
values 0.5i, -2+3i and 20i s⁻¹, with maximum difference **3.019e-10**.
The two differentiation steps, 1e-5 and 3e-6, give coefficient differences
no greater than **1.829e-10**. No geometry, inertia or frequency parameter is
adjusted to obtain agreement.

All ten comparison processes and the oracle test process exited successfully,
running serially with one BLAS thread, a 512 MiB limit and a 150-second cap
per process. The assessment authenticates the actual terminal receipts,
kernel/helpers, source data, full A/M arrays and test report. Each comparison
performs two production linearizations; there are no time-integration steps
or native predictions in this study.

Evidence is in `artifacts/isae/ffwt4-rigid-dynamic-20261106/`, including
`assessment.json`, full compressed matrices for each case, immutable input
plans, terminal receipts and `oracle-tests.xml`. Reproduction helpers are
`scripts/verify-isae-ffwt4-rigid-dynamic.py` and
`scripts/assess-isae-ffwt4-rigid-dynamic.py`.

## What remains

Continuous rigid-point mechanics, retained section loads, steady and dynamic
matrices, and a refined single-axis time history now have independent
evidence. A production attachment resolver must preserve the original ASW
records, physical point location and properties, limit any rigid reduction
to genuinely rigid eligible beams, and retain source/checkpoint identity.
Its behavior on the original PM2 files and in the browser still needs testing.

The next implementation belongs in a separate analysis-attachment resolver;
`asw.weight_station` should retain its existing exact-decimal-alias meaning.
The shared resolver must be used by mandatory station collection in
`discretization.py`, the network's analysis-only Weight copies, displayed
attachment geometry, and the point-load collection in `wall_root.py`.
`asw_edit.py` must continue using only the exact-alias resolver. Original records and lossless source serialization stay
intact. Record the effective anchor and its justification in analysis/checkpoint
identity. Eligibility must come from complete stiffness tables, not sampled
large stiffness or a distance tolerance; the present matrix evidence also
assumes zero material damping and no point airflow. A changed physical record
or beam table must trigger fresh eligibility checking. Compare the resulting
original-model mechanics with an explicit rigid extension before claiming
production support or rescoring a native history.

This matrix comparison uses zero local rates at undeformed clamped
equilibria; it is not a general nonlinear three-dimensional trajectory or a
free-flight response validation. Point airflow is outside its scope, though
the six literal rejected PM2 objects have zero CDA and volume. Native
out-of-range attachment semantics remain unknown. Neither exact finite-BDF
equivalence nor whole-family validation is claimed.
