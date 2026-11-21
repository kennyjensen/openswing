# SA-11 finite-chord control: force quadrature exposes singular integrals

2026-11-07 UTC. Increasing force-integration resolution does **not** repair the
saved independent finite-chord control. At fixed circulation and geometry,
the computed loads continue to grow. An independent endpoint calculation
predicts the growth on the two dominant root edges without fitting a parameter.
The upper/lower geometry also has two exact coplanar intersections between
trailing rays and body-edge interiors.

This diagnoses the reference control's all-edge line-force treatment. It is
not a new production ASWING result, nor evidence that native ASWING uses this
force rule. SA-11 remains **163/4,592 at 5%**; no comparison scope or denominator
changes. The broader project remains unvalidated.

## Controlled calculation

The [wake-direction study](isae-sa11-wake-direction-20261107.md) supplied the
upper and upper/lower N48 solutions with two chord rows: 300 and 492 panels.
Its circulation, vortex positions, body-edge coefficients, normals, frozen
Prandtl–Glauert map and freestream-aligned trailing rays remain fixed.

Twelve small serial jobs evaluate Gauss–Legendre orders 1, 2, 4, 8, 16 and 32
on each body's straight edges. Order 1 reproduces the saved midpoint result.
The force rule is the reference model's integral of
`rho * Gamma_body * (V cross dr)`; the moment is integrated at each quadrature
point. Only the receiver's own exact straight edge is omitted from its induced
velocity. Neighboring edges and incident wakes remain present. There is no
finite core, endpoint cutoff, coordinate change or circulation re-solve.

The previous control's qualifications still apply: frozen lifting geometry,
independently prescribed section normals, quarter-panel rear extension of the
ring lattice, and no profile drag, stall or section moment. This is not a fully
resolved physical wing surface or the native ASWING force law.

| Points per edge | Upper CL | Upper CD | Upper/lower CL | Upper/lower CD |
|---:|---:|---:|---:|---:|
| 1 | 0.670334 | 0.015651 | 0.737882 | 0.021448 |
| 2 | 0.661143 | 0.014832 | 0.676027 | 0.015944 |
| 4 | 0.695519 | 0.017927 | 0.745816 | 0.022049 |
| 8 | 0.740837 | 0.022030 | 0.799511 | 0.026951 |
| 16 | 0.779337 | 0.025530 | 0.841228 | 0.030779 |
| 32 | 0.818918 | 0.029127 | 0.889812 | 0.035205 |

From midpoint to order 32, CL changes by **22.17% / 20.59%** and CD by
**86.10% / 64.14%**, for upper / upper-lower respectively. Even the final
16→32 step changes drag by **14.09% / 14.38%**. Sampled peak speed increases
from 27.79 / 49.13 to 8,830.83 / 9,930.86 times freestream as points approach
singular locations; these are mathematical fields of the diagnostic model,
not predictions of physical high-speed flow.

![Force integration and endpoint growth](../../artifacts/isae/sa11-force-quadrature-20261107-review-with-crossings/force-quadrature.png)

## Endpoint calculation: growth is not just insufficient quadrature

The largest changing forces act on the symmetric upper-root edges with
`x = 1.1720696254 ... 1.1812952863`, `y = +/-1.2426`, `z = 0.15257` metres.
Each is approximately 9.226 mm long. Trailing rays start at their endpoints.
Those rays point along the 5-degree freestream while the body edges point
along x. Their nonzero strengths produce velocity proportional to `1/s` as
distance `s` to an endpoint tends to zero along the body edge.

The audit calculates the limiting coefficient from each incident source's
outward direction and circulation in PG space, then maps the velocity back
before taking the physical Kutta–Joukowski cross product. It does not estimate
the coefficient from the computed load sequence.

For normalized edge position `u`, the singular part of the force integrand is
`K_a/u + K_b/(1-u)`. At order Q, the Gauss sum of each reciprocal endpoint
term is exactly `2 H_Q`, where `H_Q = sum(k=1..Q, 1/k)`. Hence its predicted
contribution is `2 H_Q (K_a + K_b)`, which grows logarithmically. This identity
is also checked numerically for all six orders.

| Model, each symmetric root edge | Vertical coefficient K_a+K_b (N) | Predicted force increase, Q16→32 (N) | Observed increase (N) |
|---|---:|---:|---:|
| Upper | 7.553410463 | 10.238892646 | 10.238892667 |
| Upper/lower | 9.525476114 | 12.912091540 | 12.912091541 |

At these edges the finite incident-source endpoint coefficient is zero; the
listed coefficient comes from the wake. Across the four edge checks, the
largest vector prediction error is **1.18e-7 N**. Direct evaluation of the
incident rays independently verifies the analytic `1/u` and `1/(1-u)` fields.

Summing all body-edge endpoint coefficients gives nonzero vertical terms of
**15.1101 N** and **19.0550 N**. They predict whole-model Q16→32 vertical-force
increases of 20.4822 / 25.8296 N, compared with observed 20.4485 / 25.1006 N.
The difference contains the remaining field/integration effects; it is not
assumed to be a converged regular remainder. The plot's dotted curves use the
analytic endpoint slope and the observed Q16 value as their anchor.

## Additional upper/lower wake intersections

Two lower-root rays start at
`[1.0647394273, +/-1.2426, 0.1525]`. They rise to `z=0.15257` and cross a
body edge at `x=1.0655395309`, about **0.803 mm downstream along the ray**.
The crossing is at **62.924%** of the edge from `x=1.0409232917` to
`x=1.0800440480`. Both the ray and body-edge circulation are nonzero.

This classification uses exactly equal y coordinates, exactly x-directed body
edges and the ray's zero y component; no distance tolerance or core is used
to select the pairs. It checks this coplanar subset only, not every possible
three-dimensional encounter. No such interior crossing is found in that subset
for the upper-only case.

These interior singularities supply another reason that ordinary Gauss
quadrature is not a complete force prescription. The audit does not assign a
principal value, omit those interactions or close the original 70-micrometre
root-height difference.

## Consequence and verification

The preceding positive-drag result and apparently stable two-grid integrated
coefficients cannot make this all-edge force model a validation reference.
Increasing its quadrature order has now been ruled out as a sufficient repair.
Subtracting the logarithmic terms would define a different force model and is
not adopted here.

Before using a finite-chord reference to decide between native ASWING force
treatments, its wake/body topology and force formulation must be specified
consistently. The [literature addendum](winglet-lifting-line-literature-addendum-20261107.md)
supplies alternatives to audit, including distributed wake vorticity and the
separate section-loading/force-direction construction. A native ASWING fix
still requires evidence beyond stability of an alternative solver.

Order 1 reproduces the saved fields and forces. Constant-field moments agree
with their exact straight-edge integrals within **5.69e-14 N m**. The Gauss
reciprocal identity agrees within **1.73e-13**. The largest sideforce
coefficient is **1.13e-14**, consistent with symmetry. All saved Gamma arrays,
source artifacts and 143 production/status/scope pins were verified unchanged.
Recorded field-evaluation stages total **35.74 seconds**, excluding startup,
artifact verification and analysis; no circulation solves were run.

- [One-order serial driver](../../scripts/verify-sa11-force-quadrature.py)
- [Independent endpoint/crossing audit](../../scripts/analyze-sa11-force-quadrature.py)
- [Results, source pins and checks](../../artifacts/isae/sa11-force-quadrature-20261107-review-with-crossings/analysis.json)
- [Standalone SVG plot](../../artifacts/isae/sa11-force-quadrature-20261107-review-with-crossings/force-quadrature.svg)

Each order retains its plan, exact driver, quadrature arrays, result and hash
manifest in `artifacts/isae/sa11-force-quadrature-20261107-{up48,both48}-q{Q}/`.
The initial endpoint-only analysis is retained separately in the `-review/`
directory; the linked analysis adds exact coplanar crossing detection and
uses neutral wording for the unaccounted force change.
