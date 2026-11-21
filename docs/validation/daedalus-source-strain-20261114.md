# Daedalus: current beam compatibility and its Jacobian

An independent construction of the remaining **618 strain/curvature rows**
agrees with the current source-equation model. Together with the preceding
[aircraft balance check](daedalus-source-balance-20261114.md), this closes all
**2,044 equations** along the saved responses at 0.2 and 1.157378 Hz. It finds
no structural-equation correction that explains the rudder Bode discrepancy:
yaw remains **0.074218 versus 0.033986 deg/s/F3** at the reference dip frequency.
No production equation, physical parameter or ISAE fraction changed.

## Reference and construction

The [steady technical description](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf),
printed pp. 5–8 and 12–13, supplies the rotation products (Eqs. 3/10), section
law (Eqs. 18–19) and endpoint compatibility (Eqs. 48/50–54). The fixture is
the accepted literal `dae.asw`, source-equation/SEGSPL, 6.7 m/s equilibrium:
108 nodes, 103 beam intervals and 2,044 dynamic coordinates.

The [independent evaluator](../../scripts/daedalus_source_strain_reference.py)
forms the surface and fuselage rotation products directly. It derives each
curvature-map column as the axial vector of `R.T @ dR/dq`; it does not import
the production Euler decomposition, curvature map, compliance or derivatives.
SciPy decomposes the supplied real frames, and recomposition checks every
endpoint. Complex-step derivatives at two widths supply the map derivatives.

The material law is solved on the finite-stiffness subspace, with rigid
directions retaining zero compliance. The translational relation uses the
endpoint-average frame, unloaded interval length and section strain. The
rotational relation uses the endpoint-average curvature map, endpoint Euler
angle difference, unloaded curvature and constitutive curvature. Its tangent
includes both `dKbar @ delta_q` and `Kbar @ delta_dq`. The first term is
nonzero on every beam in this case and is present in the production matrix.

Parsed endpoint properties, right/left sampling, fixed unloaded interval
lengths and averaging stiffness before inversion are disclosed inputs and
discrete interpretations. The actual fixture has no material damping or
stepped reference axes; this check does not exercise those features. Both
loaded states and internal resultants are supplied, not independently solved.

## Results

| Comparison | Maximum absolute difference |
| --- | ---: |
| Base compatibility, independent versus production | 8.882e−16 |
| 618 response rows versus either native finite-difference width | 5.506e−13 |
| 618 response rows versus saved matrix action | 9.277e−14 |
| Complete 618 × 2,044 compatibility Jacobian | 1.365e−11 |
| Independent Jacobian action versus independent directional tangent | 1.541e−18 |
| All 2,044 reconstructed response rows versus saved matrix action | 8.958e−12 |

These are normalized equation/state quantities, not aerodynamic error
percentages. The full Jacobian comparison covers **1,263,192 entries**,
including zero columns. Its fixed entrywise gate is
`2e-7 + 2e-7 * abs(expected)`; the largest gate ratio is 6.823e−5. The
compatibility mass and input rows are exactly zero. Directional residual
comparisons use a fixed absolute gate of 2e−8.

Frame reconstruction differs by at most 7.402e−16; changing the complex-step
width changes curvature-map derivatives by at most 4.441e−16. The largest
endpoint Euler-angle difference is 0.04807 rad and the largest curvature-map
condition number is 1.0335, so this fixture is far from an Euler singularity.
The base compatibility residual is 4.762e−11. After adding the preceding
independent force, moment, constraint, circulation and kinematic rows, the
complete harmonic residual is at most 8.958e−12 at either frequency.

The [result JSON](../../artifacts/daedalus-source-strain-20261114/analyze/result.json)
retains per-beam and per-frequency values. The
[full Jacobian arrays](../../artifacts/daedalus-source-strain-20261114/analyze/matrix.npz)
and [response arrays](../../artifacts/daedalus-source-strain-20261114/analyze/arrays.npz)
retain the comparisons. This checks equation implementation at the chosen
states; it is neither an independent prediction of those states nor proof
that the historical ASWING Bode run used the same setup or discretization.

## Execution and consequence

Both jobs in the [bounded driver](../../scripts/check_daedalus_source_strain.py)
completed successfully and were reaped. Each used one BLAS thread with limits
of 512 MiB address space, 15 CPU seconds and 25 wall seconds. Maximum observed
usage was 111.68 MiB RSS, 2.23 CPU seconds and 5.75 wall seconds. The capture
reconstructed the fixture without evaluating a native residual; analysis used
saved data. No new full-aircraft solve or browser/build job was started.

The [1989 wing-paper comparison](daedalus-wing-paper-20261113.md) remains useful
independent steady evidence, but neither that static comparison nor this
equation audit establishes the later dynamic response. Historical operating
settings, full-system versus reduced-model provenance, and remaining numerical
resolution limits remain open. A reduced-model explanation is only a
hypothesis; there is no evidence identifying the published Daedalus plot as
a reduced-model result.
