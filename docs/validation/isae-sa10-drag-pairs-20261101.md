# SA-10 drag difference by interacting strip pairs

2026-11-01. The six retained Louvered states localize the positive coarse-mesh
near-field/Trefftz drag difference to interactions between the central wing
and bent tips. Wind-parallel quarter-chord offsets strongly affect those
interactions. This gives a specific geometry question to investigate; it
does not establish a different native source construction or a solver fix.

No equations, solved circulation, production files or reference scores change.
The [preceding reporting diagnostic](isae-sa10-drag-reporting-20261101.md)
remains unadopted. Registered SA-10 stays 1,256/2,268, and the retained
strength-20 physical comparison stays 1,088/1,134.

The later [exact geometry/parameter audit](isae-sa10-geometry-parameter-20261101.md)
confirms the six source geometries against independent piecewise-line formulas
and a parameter-change invariant. It excludes a t/arc-length mix-up, without
authenticating the native corner endpoint construction.

## Decomposition at fixed circulation

The six states use the original Louvered model at 5°, 15° and 25°, strength
20, zero PG Mach, and both requested 100/200 meshes (102/202 actual strips).
For every receiver/source pair, the calculation forms its contribution to
the near-field induced force and the Trefftz energy sum. Their difference
is then grouped by the left tip, central wing and right tip.

| Incidence | Requested intervals | Near CDi − Trefftz CDi | Within straight sections | Between sections |
|---|---:|---:|---:|---:|
| 5° | 100 | +0.000050715 | −0.000029408 | +0.000080123 |
| 5° | 200 | −0.000012385 | −0.000001147 | −0.000011238 |
| 15° | 100 | +0.003017875 | −0.000665909 | +0.003683784 |
| 15° | 200 | +0.000378973 | −0.000148255 | +0.000527228 |
| 25° | 100 | +0.007979736 | −0.001996941 | +0.009976677 |
| 25° | 200 | +0.000884962 | −0.000757020 | +0.001641982 |

Central-wing self interactions agree with Trefftz to roundoff. Direct
left-tip/right-tip differences are negligible in this sample. The important
cross-section terms involve a tip and the central wing, and their two
receiver/source orders partly cancel. The slanted tip sections also have a
negative net contribution, so the total is not a single uncancelled term.

At 15°/100, the largest symmetric pair contributions are the strips immediately
on either side of the two bends: about 0.00107576 per ordered pair. Four
such entries sum to about 0.00430306, exceeding the total 0.00301788 because
other contributions offset them. This identifies where a native local-field
or discretization comparison would be most informative.

## Quarter-chord offsets and an analytic control

Equation (155) places the force point downstream of the beam axis along the
wind by a distance proportional to `1 / |wind × section_span|`. That distance
is constant within each of Louvered's three straight sections but differs
across a bend. Production extends this construction to the one-sided vortex
endpoints. The previous [bend audit](isae-sa10-louvered-basis-20261031.md)
measures the resulting streamwise endpoint separation.

To measure its influence, the diagnostic subtracts each section's constant
wind-parallel quarter-chord shift from its endpoints and force receivers.
It then recalculates the force with the original circulation. This moves the
source/receiver line onto the beam axis and preserves the transverse wake
trace. It is a sensitivity calculation, not a new equilibrium or a proposed
replacement for equation (155); control-point tangency is not re-solved.

| Incidence | Requested intervals | Original drag difference | Difference with offsets removed | Original minus offset-removed |
|---|---:|---:|---:|---:|
| 5° | 100 | +0.000050715 | −0.000019467 | +0.000070181 |
| 5° | 200 | −0.000012385 | −0.000034940 | +0.000022555 |
| 15° | 100 | +0.003017875 | −0.000495231 | +0.003513106 |
| 15° | 200 | +0.000378973 | −0.000781915 | +0.001160888 |
| 25° | 100 | +0.007979736 | −0.001662960 | +0.009642696 |
| 25° | 200 | +0.000884962 | −0.002339592 | +0.003224554 |

Removing the offsets does not make the two drag definitions equal. It
demonstrates that their relative placement contributes strongly to the gap.
It also differs from adding a zero-length corner horseshoe, whose complete
field cancels, as the earlier [corner-interval audit](isae-sa6-sa10-corner-kinematics-20261031.md)
proved. Nothing here contradicts that cancellation or removes the documented
sharp-corner velocity singularity.

A second control projects all endpoints and receivers into one plane normal
to the wind, retaining their transverse coordinates and circulation. In this
plane, bound-vortex velocity is wind-parallel and contributes no drag. Each
semi-infinite wake velocity is exactly half its infinite-line value.
Therefore near-field and Trefftz drag must agree pair by pair. The computed
maximum pair discrepancy is 1.29e−16 in CD contribution; the original
Trefftz matrix is unchanged to roundoff. This checks the force signs and
half-wake factor independently of the native comparison.

## Verification and next question

The production-kernel decomposition takes 0.324 seconds after imports. A
separate standard-library implementation uses endpoint-vector finite-filament
integrals and scalar ray formulas. Three serial jobs, each covering two saved
states, perform 307,248 pair evaluations across the original and offset-removed
geometries. Their block sums and total forces are compared against the first
calculation and the original saved outputs. No nonlinear solve, browser or
build is required. Maximum block/total coefficient discrepancy is 2.16e−16.
The [receipt](../../artifacts/isae/sa10-drag-pairs-20261101/receipt.json)
records the numerical errors, source hashes and completed processes.

The [steady description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf)
equations (67), (150)–(156) and (207)–(211) remain the implementation target.
Equation (155) explicitly describes the midpoint. The exact native extension
to one-sided endpoints at duplicated corner nodes is still unverified.
The next source question is that construction together with its force
quadrature, rather than an arbitrary drag replacement. A different source
line would require consistent tangency, forces, moments and derivative checks.

- [Recorded hypotheses and inputs](../../artifacts/isae/sa10-drag-pairs-20261101/plan.json)
- [All block sums and largest pair contributions](../../artifacts/isae/sa10-drag-pairs-20261101/analysis.json)
- [Independent scalar verifier](../../artifacts/isae/sa10-drag-pairs-20261101/verify.py)
