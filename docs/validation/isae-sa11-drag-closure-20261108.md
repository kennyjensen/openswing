# SA-11: where the near-field/Trefftz drag difference comes from

2026-11-08 UTC. A decomposition of the saved 0°, 1° and 5° fields rules out
the **beam-versus-bound-segment force measure** as the cause of their drag gap:
its body-x contribution is below 1.1e−17 in coefficient units. The two
Mach-invalid root receivers account for **41.92–42.89%** of the net gap; it is
not confined to those two samples. Changing only receiver placement at fixed
circulation reverses the gap's sign, predominantly through interactions within
the main wing.

This is new accounting evidence, **not a solver repair or a converged force
prediction**. Full states still reject local Mach. The primary SA-11 fraction
remains **163/9,184 at 5%**, with no scope, equations, guards or input changes.

## Scope and source definitions

The [authoritative index](aswing-authoritative-references.md) and source catalog
were consulted; all eight catalogued PDF hashes were checked. Drela steady
**Eqs. 64–70, pp. 15–16** define the near-field force; **149–161, pp. 30–33**
define PG-mapped vortex influences and receiver placement; **207–211, p. 49**
define the separate Trefftz calculation.

Reuse the [whole-beam polar fields](isae-sa11-whole-beam-polar-20261108.md):
report-derived −4° upper twist, disclosed Joint correction, original section
inputs, 240 m/s, density 1.2256, PG Mach `240/340.21`, frozen body-x wake and
64 fixed source intervals. At each of three angles, cross the two receiver
rules with the two saved circulation fields: **12 replays, zero solves**.
The intermediate crosses prescribe circulation from the other receiver rule;
they are not additional converged equilibria. No undefined root moment is
evaluated and no rejected force is promoted to an accepted load.

The comparison is vortex-induced drag only. Friction, pressure and stall drag
are not part of either side of this identity. The near force uses the flight
drag axis `e`; the existing frozen Trefftz calculation uses body-x.

## Exact decomposition at the saved sampling

For a body-x semi-infinite ray, write its physical transverse velocity as

```text
v_ray = v_half-infinite + v_finite-origin
v_half-infinite = Gamma (0, -dz, dy) / (4 pi r_perp²)
v_finite-origin = v_half-infinite X / sqrt(X² + r_perp²)
X = dx / sqrt(1 - M_PG²).
```

Thus the semi-infinite field contains half the infinite-wake field plus a
term depending on the relative streamwise position. Summing the half-infinite
terms at the same transverse receivers reproduces the existing Trefftz drag.
The complete difference is

```text
D_near(e) - D_Trefftz(x)
 = induced-force change of projection from x to e
 + change from bound-segment measure to beam-span measure, projected on x
 + bound-vortex contribution on x
 + finite-origin wake contribution on x.
```

The ambient-flow lift has zero projection on `e` and is excluded from the
induced-force terms on both sides. The force measure comparison uses identical
velocity and circulation. This decomposition introduces no extra vortex,
core, altered receiver or replacement drag formula.

| Alpha | Formal near-vortex CD | Trefftz CDi | Difference | Axis term | Bound term | Finite-origin term |
|---:|---:|---:|---:|---:|---:|---:|
| 0° | 0.00170987 | 0.00250410 | −0.00079424 | 0 | +0.00271344 | −0.00350768 |
| 1° | 0.00312868 | 0.00451877 | −0.00139009 | +0.00004845 | +0.00507530 | −0.00651384 |
| 5° | 0.01351630 | 0.01847394 | −0.00495763 | +0.00094519 | +0.02177904 | −0.02768187 |

The omitted measure column is roundoff-sized. The positive axis term partially
offsets the negative gap at nonzero alpha; it does not explain it away. The
bound and finite-origin terms are much larger than their combined difference.
Their incomplete cancellation describes this discrete evaluation; it alone
does not identify a wrong equation or prove a continuum convergence result.

## Receiver and source attribution

At 0°, the main-wing receiver contribution to the gap is **+0.00037785**,
while each winglet contributes **−0.00058605**. At 5°, those contributions
are **+0.00241933** and **−0.00368848 per winglet**. The two invalid root
receivers contribute −0.00034064 and −0.00211010, respectively. These are
signed accounting partitions: removing the root strips is not a valid repair.

Keeping the newer circulation fixed separates receiver placement from a new
circulation solution:

| Alpha | Gap using native receivers | Gap using whole-beam receivers | Change | Main-wing/main-wing finite-part change |
|---:|---:|---:|---:|---:|
| 0° | +0.00032007 | −0.00079424 | −0.00111431 | −0.00115177 |
| 1° | +0.00067720 | −0.00139009 | −0.00206729 | −0.00212634 |
| 5° | +0.00387083 | −0.00495763 | −0.00882846 | −0.00896674 |

The last column groups every receiver/source pair within beam 1 in the bound
plus finite-origin contribution. It accounts for **101.57–103.36%** of the
net receiver change; other terms partly oppose it. This is a pairwise
partition, distinct from assigning a net force to a receiver beam. It
explains why the receiver change can strongly affect integrated drag even
though the winglet-root receiver locations barely move.

The published whole-beam rule remains in production. Neither choosing the
native rule for a better near/far equality nor changing force measures is
supported by this result. The next source comparison needs actual native
force sampling, not just integrated CL/CDi. Main-wing force quadrature and
the separate local junction-Mach failure must both remain visible.

## Verification

### Follow-up: own-wake term checked in closed form

The receiver sensitivity can be localized further without changing any fields.
For one straight bound interval `d = b-a`, let its collinear receiver be
`p = a + lambda*d`, with `0 < lambda < 1`, and define

```text
beta = sqrt(1 - M_PG²)
kappa = (d_x/beta) / sqrt((d_x/beta)² + d_y² + d_z²)

CD_own_finite = rho Gamma² kappa / (4 pi q S)
               * [1/lambda - 1/(1-lambda)].
```

This follows directly by subtracting the two endpoint ray expressions above
and projecting their Kutta–Joukowski force on body-x. It describes **only the
finite-origin part of the strip's own trailing wake**. The half-infinite
own-wake contribution remains present even at `lambda=1/2`. The receiver's
own bound segment is already excluded by the existing force evaluation.

All native and whole-beam receivers in these three cases lie on their own
straight bound intervals within **3.34e−16 m**. The formula reproduces every
own finite-origin term within **1.26e−15 in CD**, using unchanged geometry,
PG and circulation. It vanishes at an arithmetic midpoint or at zero
streamwise bound slope, and reverses sign under `lambda -> 1-lambda` with
fixed `kappa`; those algebraic controls are checked too.

| Alpha | Main-wing own-wake change | Immediately adjacent pair change | Other main-wing pairs | Total main-wing pair change |
|---:|---:|---:|---:|---:|
| 0° | −0.00196776 | +0.00089132 | −0.00007533 | −0.00115177 |
| 1° | −0.00359366 | +0.00162446 | −0.00015714 | −0.00212634 |
| 5° | −0.01492234 | +0.00672493 | −0.00076932 | −0.00896674 |

Each row is whole-beam minus native receiver placement at the same newer
circulation. Adjacent means consecutive intervals on the same main beam,
including the pair across the center. The terms partly cancel; their absolute
magnitudes should not be treated as independent missing drag contributions.

For the first positive-y main-wing interval, the native receiver fraction is
**0.2598915**, while the whole-beam fraction is **0.5001622**. The mirrored
interval has complementary fractions. At 1°, the positive-side own finite
term changes from **+0.00138454** to **−0.000000720**. This is the expected
geometric effect of the documented sampling difference, not an unexplained
self-influence coding discrepancy. Moving every sample to an arithmetic
midpoint, deleting own wake, or adopting the native receiver rule would change
the published ASWING discretization and is not justified by this identity.
The separate winglet-root Mach failure remains unresolved.

[Follow-up driver](../../scripts/audit-sa11-own-wake-sampling.py),
[scope and source pins](../../artifacts/isae/sa11-own-wake-sampling-20261108/plan.json),
[all interval fractions, terms and verification errors](../../artifacts/isae/sa11-own-wake-sampling-20261108/analysis.json).
No new solve, accepted load, primary pass or scope change occurred.

### Original decomposition checks

An independent finite-segment integral with a rationalized collinear limit
and analytic semi-infinite rays reconstructs all twelve saved velocity fields
within **6.03e−10 m/s**. Near coefficients reproduce the saved force results
within **1.84e−15**; Trefftz coefficients reproduce the prior wake audit within
**2.43e−17**. The decomposition closes at every receiver within **2.39e−18**.

The checker separately reduces the original saved force arrays using scalar
dot products and accurate summation, validates receiver-beam and rejected-root
partitions, checks all **49 source pins**, and verifies that all twelve replay
fields retain two Mach-invalid sections. Antisymmetric receiver/source terms
cancel in the quadratic contraction to roundoff; the full symmetric part is
retained. This algebraic check is not permission to discard either part of
the underlying velocity field.

- [Audit driver](../../scripts/audit-sa11-drag-closure.py)
- [Predeclared scope](../../artifacts/isae/sa11-drag-closure-20261108/plan.json)
- [All twelve decompositions](../../artifacts/isae/sa11-drag-closure-20261108/analysis.json)
- [Independent force-accounting checker](../../scripts/check-sa11-drag-closure.py)
- [Verification and derived shares](../../artifacts/isae/sa11-drag-closure-20261108/verification.json)
