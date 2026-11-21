# ST-6 nonlinear elastica and loaded modes

**2/2 fine equilibrium cases and 4/4 modal comparisons pass**, including both mirrored lateral-load directions. The largest fine modal error is **0.012321%**, largest mesh change **0.036976%**, and largest position error **0.003899% of beam length**. The actual built offline worker also passes **21/21 comparison groups** on the coarse control case.

This verifies a large-rotation equilibrium after buckling and the vibration modes about that curved state. It extends the straight-column [distributed-mode study](isae-st6-distributed-modes-20261104.md). It is an analytical supplement, not an original ISAE model or native ASWING result. The original ST-6 archive has no native model/output pairing.

## Specified load and independent solution

The unchanged [Euler-column model](../../examples/euler-column.asw) has a 2 m massless, inextensible rod with EIcc=100 N m², a clamped root and a 1 kg free-tip mass. Only one bending direction is flexible. A constant axial compression of **92.52754126 N**, or 1.5 times the continuous Euler threshold, is combined with a lateral dead load of **±1.85055083 N**. The lateral force is explicitly 2% of the axial force; it selects a bent branch and is not adjusted to fit an output. The requests specify the equivalent body gravity vector [0,-92.52754126,±1.85055083] m/s².

The [independent reference](../../scripts/elastica_tip_mass_reference.py) uses complete/incomplete elliptic integrals to select the primary elastica branch. It then integrates the nonlinear arclength equations and analytic sensitivities to both Cartesian tip-force components. The free-tip moment condition determines the root-moment sensitivity. This yields an exact continuous tip compliance and the complete modal shapes for this massless-rod/tip-mass problem.

The two positive compliance eigenvalues give two stable mode pairs, lambda=±i/sqrt(m*c). OpenSwing retains the full nodal geometry, internal loads and rates in its descriptor calculation. The reference’s two-coordinate expression follows exactly from having inertia only at the tip. The [derivation](../../artifacts/isae/st6-elastica-20261104/DERIVATION.md) gives the elliptic length condition, nonlinear equations, force tangent and modal relation.

All **eight reference tests** pass: nonlinear force perturbations verify the tangent on both sides of the Euler threshold; reflection preserves frequencies; the small-load limit agrees with linear cantilever theory; and physical length/stiffness/mass scaling holds. Initial checks mistakenly rejected real eigenvalues stored in a complex dtype. The corrected guard tests actual imaginary values, retaining strict nonreal rejection. The original failed log and code are preserved; no physical input or test tolerance changed.

## Refinement

Each production calculation starts cold and uses the normal 16-step load continuation. No reference shape seeds the solver. The eight-interval dense control finds exactly four finite roots and reaches the bent stable branch. Its coarse continuum errors remain recorded. The declared fine study uses uniform N64/N128 meshes and the full shifted descriptor method.

| Intervals | Positive tip angle | Position error, % of L | First mode error, % | Second mode error, % |
|---:|---:|---:|---:|---:|
| 8, coarse control | 98.397719° | 0.999332 | 0.436727 | 3.245946 |
| 64 | 99.008696° | 0.015595 | 0.006708 | 0.049302 |
| 128 | 99.015901° | 0.003899 | 0.001677 | 0.012321 |

The continuous tip angle is **99.018302°**. The fine negative-load case is its mirror. Across the full rod, the largest fine angle error is **4.386e-5 rad** and the root-moment error is **0.002861%**. Geometry, angle and reaction mesh checks all pass. The gates were fixed before the fine runs: 0.1% for position/length, moment, poles and corresponding mesh changes, 0.001 rad for angles, and 0.999 for shape assurance.

| Mode | Reference angular frequency, rad/s | N128 positive branch | Fine error, % | N64→N128 change, % |
|---:|---:|---:|---:|---:|
| 1 | 6.183180694 | 6.183077018 | 0.001677 | 0.005032 |
| 2 | 41.685358827 | 41.690495039 | 0.012321 | 0.036976 |

Both members of each mode pair are compared. Independent one-to-one shape assignments agree with the computed frequency order for both meshes, both references and the opposite pole partners. The minimum shape assurance is **0.9999997491**. Mirror pole differences are below **6.04e-12 relative**; position/angle mirror checks also pass. No eigenvalue component is rounded to zero.

All four fine-study cases pass fresh equilibrium residual, mass, gravity force, clamp and global force/moment balance checks. All **32 fine-study and eight coarse-control left/right eigenvector checks** pass against the complete physical A/M pencils. The maximum fine-study backward error is **3.497e-16**. The coarse dense result establishes four finite roots at N8; the larger shifted cases verify all four requested roots without asserting a separate complete-spectrum classification.

## Offline browser verification

The actual built WASM worker reproduces the complete N8 dense request: full A/M matrices, nonlinear base, all four poles, both eigenvector sides and physical outputs. All **21 comparison groups / 61,217 numeric comparisons** pass at the unchanged `2e-8 + 2e-8*abs(reference)` gate; the largest discrepancy consumes 13.56% of that allowance. Browser-side multiplication also checks all eight left/right pencil residuals.

The worker solve takes **12.08 seconds** after runtime initialization; the full harness takes **43.17 seconds** in this observation. All 137 kernel hashes match source/public/built copies before and after. No page errors, failed network requests, external requests or requests after disconnection occur. This verifies runtime parity on the coarse control, not fine-mesh continuum accuracy or a new workbench/project-save flow.

The four refined native jobs run serially under a 512 MiB address-space cap and total **103.9 seconds** of recorded child-process time, with peak RSS below 113 MiB. The browser runs afterward as a separate bounded job. Production kernels are unchanged; no new browser build or release package is needed for this reference/validation increment.

Remaining scope includes dynamic trajectories through buckling, other post-buckled branches, distributed-mass post-buckling, and general fixtures. Native ST-6 comparisons remain unavailable; no experimental or Euler-plot value is relabeled as native solver output.

## Evidence

- [Portable assessment and browser evidence](isae-st6-elastica-20261104.json).
- [Fixed fine-study plan](../../artifacts/isae/st6-elastica-20261104/plan.json), [serial receipts](../../artifacts/isae/st6-elastica-20261104/serial-receipt.json), [reference test log](../../artifacts/isae/st6-elastica-20261104/reference-tests.log), and [saved-result assessment](../../artifacts/isae/st6-elastica-20261104/assess.py).
- [Reference tests](../../tests/test_elastica_tip_mass_reference.py) and [offline worker report](../../artifacts/isae/st6-elastica-20261104/browser-n8/report.json).
- Complete physical results, fine sparse matrices, reference shapes/sensitivities, the coarse dense control and original failed reference attempt are retained under `artifacts/isae/st6-elastica-20261104/`.
