# Attached near wake: solved circulation and consistent force control

2026-11-08 UTC. Adding the attached-leg forces substantially improves the
agreement between near-field and Trefftz-plane drag in a solved straight,
swept-wing control. At 30 degrees sweep and 128 intervals, the drag difference
falls from **-8.278% to -0.848%**. Quarter-chord section velocities remain
bounded over an eightfold refinement, but velocities at the attached-leg tip
receivers grow. The remaining drag discrepancy persists at smaller incidence.

This is an independent formulation investigation. It does not reproduce native
ASWING, repair SA-11, or authorize changing the production force law. Registered
SA-11 remains **163/4,592 at 5%**. All 143 production/status/scope hashes remain
unchanged.

![Solved attached-leg control](../../artifacts/isae/attached-wake-forces-20261108-review/attached-wake-forces.png)

## Source interpretation and scope

[Drela's steady description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
§4.2, equations 150–161 and Figure 16, specifies wind-aligned trailing vortices
and wind-shifted force/control points. This review found no finite chordwise
attachment rule there. The user guide's shared-physical-index zero-core rule
also remains applicable. The alternative below therefore stays outside the
production solver.

[Gaunaa, Li and Pirrung (2026)](https://backend.orbit.dtu.dk/ws/portalfiles/portal/446323265/Gaunaa_2026_J._Phys._Conf._Ser._3224_042030.pdf),
§§2–3, couples a three-dimensional vortex field to two-dimensional section
properties. It distinguishes the three-quarter-chord loading magnitude from
the quarter-chord force direction and includes forces on the chordwise attached
vortex legs. This control implements those ingredients on a straight bound
line, where curved-bound-line self-induction is absent.

The retained [Vortex-Step-Method source](https://github.com/awegroup/Vortex-Step-Method/blob/716eb8d266c06b7fcce740a9b66a26bec1d75197/src/VSM/core/BodyAerodynamics.py)
provides an additional implementation check. Its unchanged
`compute_attached_trailed_vortex_forces` and `compute_trefftz_plane_induced_drag`
method bodies are executed with the source's reversed section ordering.
The attached-force method receives this diagnostic's zero-core velocity through
an explicit callback. This is **not a full VSM run**: its viscous wake kernels,
solver and general geometry machinery are not used. Independent Biot–Savart
integration separately checks the callback field on the coarsest grid.

## Defined problem

The wing is a straight oblique rectangle, not a symmetric V-shaped swept wing.
Bound-line arclength is 10 m and perpendicular chord is 1 m. Sweep is 0 or
±30 degrees. Geometric incidence rotates the chord by 5 degrees about the
bound-line span; the additional small-angle control uses 1 degree. Uniform
freestream is `(1,0,0)` m/s and density is 1 kg/m³. Compressibility, stall,
profile drag and section pitching moment are absent; vortex cores are zero.

Cosine nodes use 16, 32, 64 and 128 intervals, with arithmetic interval
midpoints. Each trailing path runs from the quarter-chord node to the physical
trailing edge along the local chord, then along the freestream. Source
circulation jumps are grouped exactly at the shared leg origins. Own attached
filaments contribute zero at their on-filament receivers; no adjacent filaments
are omitted or merged by a distance tolerance.

The section law is `Cl = 2*pi*alpha`, with residual

```text
R = Gamma - pi*c*|V_inner,3/4|*atan2(V_inner,3/4.n, V_inner,3/4.c).
```

The inner velocity removes the spanwise component and the infinite local
two-dimensional bound-vortex field. Section lift magnitude is
`rho*Gamma*|V_inner,3/4|*ds`, with direction perpendicular to the quarter-chord
inner velocity. Each attached leg adds `rho*jumpGamma*(V_at cross leg)`, using
the full velocity at the section's three-quarter-chord point on that leg.
Section and attached forces, application points and moments remain separate in
the saved ledgers. Trefftz drag uses the same solved circulation projected
onto the plane normal to freestream; it is not an ASWING reference value.

## Results and unresolved behavior

For +30 degrees sweep and 5 degrees incidence:

| Intervals | Section-only drag difference from Trefftz | Complete drag difference | Complete drag (N) | Lift, z component (N) | Peak attached speed / freestream |
|---:|---:|---:|---:|---:|---:|
| 16 | -8.074% | -0.185% | 0.02119028 | 1.590033 | 1.00934 |
| 32 | -8.199% | -0.596% | 0.02117174 | 1.568795 | 1.05312 |
| 64 | -8.253% | -0.768% | 0.02114870 | 1.557594 | 1.22244 |
| 128 | -8.278% | -0.848% | 0.02113310 | 1.551842 | 1.75658 |

From 64 to 128 intervals, complete drag changes -0.0738% and lift changes
-0.3693%. The peak quarter-chord speed stays approximately 0.9999 times
freestream throughout. Reversing sweep mirrors circulation, forces and moments
within the independent checks. The unswept complete-drag difference decreases
to +0.00198% at 128 intervals.

At 1 degree incidence and 128 intervals, the swept complete-drag difference is
**-0.85498%**, compared with -0.84833% at 5 degrees. This rules out reducing
incidence as a sufficient remedy in this control. It does not identify the
remaining error as a particular discretization term.

The largest attached-leg velocity occurs at a tip. At +30 degrees and 128
intervals its section-normal component is **1.4473 m/s**, despite the small
residual at the interval-centered section equations. Those equations do not
constrain flow at the separate boundary force receivers. The two endpoint
attached forces together contribute 0.0022635 N of drag, while all attached
legs together contribute 0.0015836 N; interior contributions partially cancel
the endpoints. These are signed force sums, not independent positive drag
fractions. Stable totals alone do not establish convergence of this field or
justify an arbitrary core.

The [preceding prescribed-field test](swept-wake-limit-20261108.md) isolated
the swept-line logarithmic wake term. The present solved control demonstrates
why changing that geometry also requires changing force accounting. The next
check should resolve boundary-force sampling and endpoint behavior against a
consistent finite-chord or continuous-sheet reference before extending the
construction to SA-11's sharp, offset and branching roots. No root locations,
original input properties or validity gates have been changed.

## Verification and reproduction

Fifteen completed states satisfy the explicit circulation residual gate, with
maximum independently reconstructed residual **1.05e-14 m²/s**. Directional
finite differences check every analytic Jacobian; the largest discrepancy is
5.63e-9 against a declared 2e-8 gate. Six direct velocity-integral comparisons
agree within 1.39e-17 m/s. Compensated scalar reconstruction checks all saved
force ledgers and moments within 5.76e-16 in the declared units. The retained
VSM force and Trefftz methods agree to roundoff.

The first 1-degree harness attempt stopped because MINPACK reported stagnation
at a residual of 3.04e-16. Its plan, driver and failure record are preserved.
The diagnostic was corrected to judge its explicit equation residual, positive
circulation/axial flow and Jacobian checks while retaining the MINPACK status.
In the fresh repeat, the 0- and +30-degree cases retain stagnation warnings at
machine-level residuals; the -30-degree case reports success. None is counted
as an ISAE pass. The initial 5-degree results were not rerun or overwritten.

The completed numerical stages total 2.21 seconds, excluding interpreter
startup, the first rejected harness attempt, and analysis/plotting. Each batch
runs serially with one BLAS thread, a 60-second timeout and a 768-MiB address
space limit.

- [Solver/control driver](../../scripts/verify-attached-wake-forces.py)
- [Independent saved-state audit and plotting](../../scripts/analyze-attached-wake-forces.py)
- [Complete analysis and manifests](../../artifacts/isae/attached-wake-forces-20261108-review/analysis.json)
- [Standalone SVG](../../artifacts/isae/attached-wake-forces-20261108-review/attached-wake-forces.svg)

Use the solver driver with `--panels 16`, then 32, 64 and 128, each with a fresh
`--output` directory. The added control uses `--panels 128 --incidence 1`.
Retained exact drivers in each artifact directory preserve both harness
versions and their original acceptance rules. All source/result manifests and
production/status/scope pins are verified before the review is written.

The subsequent [continuous-loading audit](continuous-attached-drag-20261108.md)
finds a roughly 1% single-point attached-force deficit in planar continuous
reconstructions of the saved circulation shapes. Chordwise integration restores
an independently checked global drag identity. Reconstruction also changes
Trefftz drag by 1.27% at N128, so it does not establish an exact correction for
the original discrete case. Distributed forces, moments and root behavior
remain unvalidated.
