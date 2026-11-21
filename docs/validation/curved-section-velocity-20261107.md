# ASWING section velocities: equation audit and smooth-curvature control

2026-11-07 UTC. The inspected production paths use the evaluation points and
load definitions specified by Drela. A controlled calculation nevertheless
shows a mathematical limitation of the zero-core bound-line velocity: even a
smooth curved line develops logarithmic mesh dependence. Independent direct
integration confirms the computed field; the growth is not a kernel arithmetic
error. The published three-dimensional-minus-two-dimensional bound correction
has much smaller refinement changes on these controls.

This is progress on the mechanism behind the winglet investigation, not a
native ASWING comparison or an accepted replacement force law. No production
equations, model inputs, cores, validity gates or ISAE fractions change. SA-11
remains **163/4,592 at 5%**. The complete ASWING implementation remains incomplete.

## Equation-to-code audit

The primary source is Drela's [steady technical description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf).
The following matches concern the inspected steady section paths, not every
solver feature or the unavailable native source.

| Quantity | Published prescription | Current implementation |
|---|---|---|
| Bound and control locations | Eqs. 155–157: wind-directed offsets; control spacing set by section lift slope | `lifting_geometry` in [frozen_influence.py](../../openswing/frozen_influence.py) |
| Circulation equation | Eq. 200: control-point tangency; Eqs. 202–204: stall leakage | `vcp`, `normal_velocity`, `local_residual` in [aero.py](../../openswing/aero.py) |
| Steady lift | Eqs. 64–67: full relative velocity at the bound-vortex force point, crossed with section span | `vhv`, `velocities`, `flift` in `aero.py` |
| Section-normal speed and moment | Eqs. 69, 72–73: remove spanwise velocity; use local perpendicular Mach | `vperp`, `vp_speed`, `local_mach`, `section_moment` in `aero.py` |
| Frozen influence option | §4.6: jig geometry and zero wind angles for influences | `FrozenInfluences`; section frames, ambient flow and loads remain live |

The own straight bound segment is omitted before force-point summation; the
other bound segments and all wake sources remain. That self convention is
explicit in the code. The cited sections do not provide a curved-line finite-part
or sharp-fork prescription that would justify deleting neighboring sources.

For core selection, the [user guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
requires zero mutual core for beams sharing a physical index. All bundled
SA-11 winglet beams share index 1. This audit therefore retains zero core.

## Why the newer circulation relation is not necessarily a different linear solve

[Li et al. (2020)](https://backend.orbit.dtu.dk/ws/portalfiles/portal/220872251/Li_2020_J._Phys._Conf._Ser._1618_052038.pdf),
§§2.2–2.3, subtracts the local infinite two-dimensional bound-line field from
the three-dimensional field at three-quarter chord. The resulting bound
correction also enters the quarter-chord force velocity. This avoids evaluating
the curved bound line on itself. The paper distinguishes this construction
from a full second-order asymptotic derivation.

For a local section with span `s=+y`, chord `c`, normal `n=+z`, incompressible
slope `a0=2*pi`, and the control point `c/2` behind the bound point:

```
B_2D(cp) . n = -Gamma / (pi*c)
V_inner      = V_total(cp) - B_2D(cp)
R_section    = Gamma - pi*c*(V_inner . n)
             = -pi*c*(V_total(cp) . n)
```

Thus zero residual of the linear section relation is exactly the control-point
tangency condition on this geometry. More generally, a normal offset
`d=a0*c/(4*pi)` gives `B_2D.n=-2*Gamma/(a0*c)` and the same cancellation.
These are our algebraic deductions under the stated local assumptions. They
do not establish equivalence with finite-angle polar lookup, compressibility,
stall, arbitrary twist, or a forked junction.

The diagnostic checks the two residual definitions on all 18 prescribed
fields; their largest difference is **4.45e-16**. The residuals are generally
nonzero: this identity is not a claim that the prescribed fields solve a wing.

The force velocity differs even in this linear comparison:

```
Current on-line construction: V_ambient + W(hv) + B_3D(hv)
Corrected construction:       V_ambient + W(hv) + B_3D(cp) - B_2D(cp)
```

Consequently, a force-only substitution would still change the model and its
coupled feedback. Agreement of linear loading equations is not authorization
to silently replace all section velocities.

## Controlled numerical evidence

Three shapes use the same arc-length extent: a straight line, a circular swept
line in x–y, and a circular dihedral line in y–z. Curved cases have radius
10 m and half-angle 30 degrees. Chord is 1 m, constant prescribed circulation
is 1 m²/s, density is 1.225 kg/m³, and ambient speed is 10 m/s at 5 degrees.
Influence wake direction is +x, consistent with a zero-angle frozen geometry;
Mach and core are zero. There are no engines, volume sources or unsteady terms.

Uniform arc-angle subdivisions give 15, 31, 63, 127, 255 and 511 straight
segments. Only the central section is evaluated. Its own segment midpoint
also equals the Glauert midpoint by symmetry. Its local span is +y and its
control point is half a chord downstream. The sampled midpoint approaches
the smooth curve as the polygon is refined.

Constant circulation makes all interior trailing rays cancel. Their summed
field is checked against the two endpoint rays, isolating bound-curvature
effects from wake discretization. Constant circulation at the tips is a
deliberate mechanism control, not a physically solved finite-wing loading.

The table projects bound velocity on the central binormal: minus z for sweep
and plus x for dihedral. The corrected dihedral field also has a small z
component, retained in the full-vector refinement checks and saved forces.

| Segments | On-line bound velocity, either curve (m/s) | Corrected sweep (m/s) | Corrected dihedral (m/s) |
|---:|---:|---:|---:|
| 15 | 0.02771092 | 0.02216200 | 0.01735833 |
| 31 | 0.03350002 | 0.02314008 | 0.01663700 |
| 63 | 0.03914551 | 0.02337855 | 0.01641315 |
| 127 | 0.04472473 | 0.02343611 | 0.01635892 |
| 255 | 0.05027195 | 0.02345024 | 0.01634560 |
| 511 | 0.05580344 | 0.02345374 | 0.01634231 |

![Central curved-section velocity refinement](../../artifacts/isae/curved-section-velocity-20261107-review-final/curved-section-velocity.png)

For smooth curvature `kappa`, local expansion of the Biot–Savart integrand
gives a leading binormal term proportional to `1/abs(s)`. Integrating both
sides of the omitted own interval predicts the mesh increment

```
Delta B = Gamma*kappa/(4*pi) * binormal * log(N2/N1) + higher-order terms.
```

Here `Gamma*kappa/(4*pi) = 0.0079577471546 m/s`. There is no fitted coefficient
or fitted core. At 255→511 segments, the predicted increment magnitude is
0.0055314781521 m/s and the observed increment is 0.0055314872129 m/s.
Their relative difference is **0.0001638%**. The on-line field therefore keeps
growing by a finite amount on each near-doubling, rather than converging.

Over the same step, the corrected full-vector changes are **3.5012e-6 m/s**
for sweep and **3.2986e-6 m/s** for dihedral: approximately **1,580** and
**1,677** times smaller. The refinement trend is consistent with convergence
on these smooth controls, not a proof of accuracy for SA-11.

The straight control has exactly zero on-line bound field. Its corrected field
is small but nonzero for finite span, and agrees with the analytic finite-line
minus infinite-line expression. Increasing straight semispan from 10 to 100
to 1,000 chord lengths reduces that correction from 3.9714e-4 to 3.9788e-6
to 3.9789e-8 m/s. This verifies the two-dimensional limit while showing that
the correction is not confined solely to curved geometry.

## Verification and implementation consequence

Independent 80-point line quadrature agrees with the production finite-vortex
fields within **1.67e-16 m/s**. Interior-wake cancellation agrees within
**8.89e-16 m/s**. Direct componentwise force calculations verify the local
`rho*Gamma*(V cross s)` evaluation. All 18 field evaluations finish; their
recorded calculation time is **0.74 seconds**, excluding startup and plotting.
No circulation solve or production change was made. All 143 production,
status and scope hashes remain unchanged.

This rules out a simple wrong-force-point interpretation of Drela's equations
as the fix. It also shows why successful control-point tangency alone cannot
validate a curved lifting-line force field. Before an alternative can repair
the actual winglet examples, it must handle the offset and three-branch roots,
retain a consistent loading/force definition, and be checked against independent
surface solutions or native ASWING evidence. The earlier singular all-edge
[finite-chord reference](isae-sa11-force-quadrature-20261107.md) cannot supply
that validation yet.

- [Bounded serial diagnostic](../../scripts/verify-curved-section-velocity.py)
- [Results and retained fields](../../artifacts/isae/curved-section-velocity-20261107/results.json)
- [Plan and production hashes](../../artifacts/isae/curved-section-velocity-20261107/plan.json)
- [Residual identity and plot audit](../../artifacts/isae/curved-section-velocity-20261107-review-final/review.json)
- [Standalone SVG](../../artifacts/isae/curved-section-velocity-20261107-review-final/curved-section-velocity.svg)

The initial plot review is retained separately; the linked final rendering
removes overlapping minor x-axis labels without rerunning any velocity fields.

The subsequent [actual SA-11 field replay](isae-sa11-section-velocity-20261108.md)
shows that this smooth-control improvement does not remove the winglet peaks:
the wake field dominates at the tested worst receivers. The alternative probe
and local-line mappings are retained explicitly; no production substitution
follows from the smooth-control result.
