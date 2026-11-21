# Flare20 frozen-matrix refinement: 107 nodes

The separate K/F=True Flare20 case now reaches a cold coupled equilibrium on
**107 nodes**. Its initial root moment remains close to the archived ASWING
value: **0.6866% error**, compared with 0.6939% at 55 nodes. The 55/107 pair
passes **3/7 numerical mesh checks**, so spatial accuracy remains incomplete.
The native FFWT-4 count stays **200/8,000**; this study adds no gust history
or native pass.

This follows the [joint-aerodynamic sensitivity study](isae-ffwt4-joint-aero-20261107.md).
The documented freeze option is an explicit comparison setting. The
historical ASWING_R_5_92 startup value remains unauthenticated, and OpenSwing's
production default is unchanged. The original evolving-matrix 211-node
equilibrium and its 0/7 mesh results remain separate.

## Equilibrium and mesh results

| Quantity | Frozen, 55 nodes | Frozen, 107 nodes |
| --- | ---: | ---: |
| Initial sensor-1 root moment | 0.5263612392 N m | 0.5263999398 N m |
| Error from native 0.530039 N m | -0.69387% | -0.68656% |
| Right hinge angle | 50.16402 degrees | 50.12312 degrees |
| Left hinge angle | -4.97956 degrees | -4.95941 degrees |

The root moment changes only **0.007352%**. The remaining fields require their
own checks; a small change in this integrated load cannot establish their
accuracy.

| Mesh check | Change relative to finer field scale | 0.1% limit |
| --- | ---: | --- |
| Sensor-1 root moment | 0.007352% | Pass |
| Beam 1 displacement | 0.357982% | Fail |
| Beam 1 finite rotation | 1.044063% | Fail |
| Beam 2 displacement | 0.090845% | Pass |
| Beam 2 finite rotation | 0.085964% | Pass |
| Beam 3 displacement | 0.434939% | Fail |
| Beam 3 finite rotation | 0.440429% | Fail |

Each displacement and rotation check uses that beam's own fine-grid field
scale. This prevents the roughly 50-degree right-tip fold from hiding errors
in the main wing's much smaller deformation. The worst main-wing rotation
change is **5.333e-5 rad**, relative to a fine-grid maximum of **0.005108 rad**.
All shared stations are compared exactly, with no interpolation, and finite
rotations use the SO(3) angular distance.

![Initial moment and seven mesh checks](../../artifacts/isae/ffwt4-frozen-refinement-20261107/refinement-107.png)

## Execution and verification

The run starts from the unloaded configuration and completes **19 accepted
load steps**, with **zero rejected attempts**. All **seven** serial solver
processes exit successfully. Three-step jobs take 35.25–46.57 seconds; the
final one-step job takes 25.27 seconds. Each process retains a 90-second cap,
512 MiB address-space limit and one BLAS thread.

An independent assessment restores every saved boundary, checks the complete
checkpoint chain and source/kernel identities, and rebuilds the physical
residual. The largest boundary residual, including the final one, is
**5.16231e-13**, below 1e-12. Separate root-moment and nodal-field assessors
also exit successfully. The 0.1% gates and both planned refined meshes were
recorded before this run began. All 139 production modules remain identical
to the rank-refined kernel used by the comparison.

## Rank-check feasibility probes

Larger cold meshes currently spend substantial time in the startup singular
value calculation. Two small, read-only probes reuse the saved 2,532-row
mechanical matrix; they do not run a new equilibrium or change the solver.
They estimate tighter reciprocal-condition lower bounds using sparse matrix
norms instead of a dense SVD.

| Estimate | Value | Existing threshold |
| --- | ---: | ---: |
| Frobenius norms | 3.4312e-12 | 1e-10 |
| Matrix one/infinity norm bound | 8.9614e-11 | 1e-10 |
| Sparse Gram-matrix norm bound | 9.8961e-11 | 1e-10 |

Even these preliminary floating-point estimates remain below the threshold.
They do not include the complete outward-rounding proof required for a new
certificate, and none is used to accept a matrix. No rank threshold or
production path changes. A faster certificate remains possible work, not a
delivered optimization.

## Evidence and next step

The retained study is `artifacts/isae/ffwt4-frozen-refinement-20261107/`:

- `study-plan.json` pins both 107/211 meshes, the frozen 55-node result,
  source, kernel and seven numerical gates.
- `nodes-107/job-007/result.json` is the full equilibrium;
  `nodes-107/assessment.json` verifies all seven boundaries.
- `comparison-55-107.json` and `nodal-fields-55-107.json` contain the full
  field comparisons; `summary-107.json` combines the verified results.
- Individual process receipts, rank-probe reports, helper scripts and
  PNG/SVG plots are retained without rewriting prior results.

Complete the planned **211-node frozen cold run**, using one accepted load
step per bounded process, and repeat all seven mesh checks. That run has not
yet been computed. Element loads, circulation fields, full gust histories,
historical startup and attachment qualifications, other PM2 configurations,
the separate Fixed-1 refinement, and shared suite registration remain open.
