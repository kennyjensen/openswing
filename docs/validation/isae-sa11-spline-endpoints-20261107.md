# SA-11: spline endpoint conditions

2026-11-07. Spline endpoint conditions cannot explain the baseline-wing
discrepancy: every explicit input segment has just two knots, so both retained
cubic policies describe the same affine or constant functions. For the
three-knot extension geometry, the alternative changes drag errors by only
0.289–0.315 percentage points. None of the sampled 5% decisions changes.
The primary comparison remains **163/4,592**; no default or model is changed.

## Source evidence and fixed comparison

The [ASWING guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
specifies cubic interpolation in the supplied beam parameter, but does not
specify endpoint conditions. The retained [Drela JVL spline source](../../reference/third_party/jvl/src/spline.f)
provides two candidates: `SPLINE` uses zero second derivatives at the ends;
`SEGSPL` calls `SPLIND(-999,-999)`, imposing zero third derivatives on the end
intervals. Both reduce to a straight line for two knots. OpenSwing already
implements these as `natural-v1` and `drela-segspl-v1`; neither native SA-11
caller is authenticated. The earlier [compiled-routine audit](../../artifacts/isae/sa4-input-spline-audit-20261030/report.md)
checks these implementations independently of the SA-11 results.

The theory, section 3.1, permits both pointwise and Fourier circulation.
The extended manual's NODE example shows 180 nodes and 19 modes, but does not
establish SA-11 startup defaults. Version 5.60 notes a correction to circulation
defaults on LOAD without specifying their values. This review supplies no
reason to select a new mesh or mode count.

Twelve predeclared physical calls compare the two endpoint policies:

- Literal baseline and the previously declared donor-slope/drag diagnostic,
  each at 1° and 240 m/s.
- Original extension at 0° and 1°, each at 240 and 272 m/s.

All calls use the registered N64 mesh request, evolving influences, dynamic
PG Mach, original stall parameters and unchanged validity guards. Endpoint
policy is the only change within each pair. No post-stall states are tested.

## Results

The literal baseline and donor baseline agree between policies within
1.99e-15 in predictions scaled by `max(1, abs(value))`. Their circulation
vectors differ by at most 5.35e-13. Literal baseline drag remains **20.654%
high** at the control point; donor-baseline drag remains **5.324% low**.

For the original extension, signed total-drag errors are:

| Alpha | Speed (m/s) | Natural endpoints | SEGSPL endpoints | Decisions at 5%, either policy |
|---:|---:|---:|---:|---:|
| 0° | 240 | −3.722% | −3.407% | 7/7 |
| 0° | 272 | −4.389% | −4.088% | 7/7 |
| 1° | 240 | −5.927% | −5.617% | 5/7 |
| 1° | 272 | −6.923% | −6.634% | 5/7 |

These are paired diagnostic subsets, not additional primary passes. Drag
and CD are the two failed channels at 1°. Lift, CL, CDi, CM and efficiency
pass under both policies at all four extension states.

The geometry-only check evaluates all explicit beam distributions and their
first two derivatives, including both sides of doubled stations. Baseline
vortex coordinates differ by at most 7.78e-16 m on N64/N128. The extension
vortex coordinates move by up to **2.045 mm**. N128 was checked for geometry
only; no aerodynamic refinement claim follows.

## Verification and remaining work

All 12 calls return valid states. Maximum circulation residual is 1.98e-14;
maximum local normal Mach is 0.893. Every section is at least 25.71 stall
transition widths inside its limits. Returned force/moment components
reconstruct the reported wrench. The longest measured solve/check call is
0.124 s, excluding interpreter startup and serialization. Six natural-policy
results reproduce previously saved predictions within 6.19e-16 scaled error.

The first geometry collector called the single-mesh restoration helper as if
it constructed model meshes and stopped with a TypeError before any physical
solve. A separate corrected collector uses `model_meshes`; the original
driver, plan and failed-attempt record are retained. All physical batches
finish successfully, in the foreground, with three calls and one BLAS thread
per batch. All 141 production Python modules and `ISAE_STATUS.md` retain their
pre-study hashes.

Endpoint ambiguity can now be excluded for the baseline and is too small to
resolve the sampled extension drag failures. The remaining investigation is
the native producing section inputs and swept-wing force-point velocity
treatment. Native mesh/mode settings remain unknown; this study does not
authenticate them, establish aerodynamic mesh convergence or validate SA-11.

[Frozen plan](../../artifacts/isae/sa11-spline-endpoints-20261107/plan.json),
[serial driver](../../artifacts/isae/sa11-spline-endpoints-20261107/run.py),
[corrected geometry collector](../../artifacts/isae/sa11-spline-endpoints-20261107/geometry-audit.py),
[geometry results](../../artifacts/isae/sa11-spline-endpoints-20261107/geometry.json),
[numerical analysis](../../artifacts/isae/sa11-spline-endpoints-20261107/analysis.json).
