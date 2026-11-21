# Flare20 frozen-matrix refinement: 211 nodes

The separate K/F=True Flare20 case completes its **211-node cold coupled
equilibrium**, with **0.5344% initial root-moment error** from the archived
ASWING value. The 107/211 pair passes **1/7 numerical mesh checks**. Six
changes remain **0.1218–0.1530%**, above the unchanged 0.1% mesh limit.
FFWT-4 native coverage remains **200/8,000** at 5%; this initial-state study
does not add a gust history or native pass.

This follows the [107-node study](isae-ffwt4-frozen-refinement-20261107.md).
The documented K/F frozen-influence option remains an explicit sensitivity
setting. The historical ASWING_R_5_92 setting is unauthenticated. The separate
evolving-matrix 211-node result and its 0/7 mesh checks remain preserved,
and the production default is unchanged.

## Equilibrium and spatial accuracy

| Quantity | Frozen, 55 nodes | Frozen, 107 nodes | Frozen, 211 nodes |
| --- | ---: | ---: | ---: |
| Initial sensor-1 root moment, N m | 0.5263612392 | 0.5263999398 | 0.5272064407 |
| Signed error from native 0.530039 N m | -0.69387% | -0.68656% | -0.53441% |
| Right hinge angle, degrees | 50.16402 | 50.12312 | 50.18441 |
| Left hinge angle, degrees | -4.97956 | -4.95941 | -4.96720 |

| 107/211-node mesh check | Change relative to finer field scale | 0.1% limit |
| --- | ---: | --- |
| Sensor-1 root moment | 0.152976% | Fail |
| Beam 1 displacement | 0.134946% | Fail |
| Beam 1 finite rotation | 0.069782% | Pass |
| Beam 2 displacement | 0.125962% | Fail |
| Beam 2 finite rotation | 0.121770% | Fail |
| Beam 3 displacement | 0.138489% | Fail |
| Beam 3 finite rotation | 0.145033% | Fail |

All 107 shared stations are compared without interpolation. Each beam's
displacement and finite-rotation errors use its own finer-grid field scale;
rotation differences use the SO(3) angular distance. The largest main-wing
displacement change is 1.872 micrometres. Right-tip displacement and rotation
change by at most 0.13790 mm and 0.00106968 rad respectively.

The earlier 55/107 pair passed 3/7 checks. Passing a coarser pair did not
establish convergence: its small root-moment change of 0.00735% grows to
0.15298% for the next pair. Closer agreement with one native value cannot
replace the independent numerical mesh checks.

![Initial moment and seven mesh checks](../../artifacts/isae/ffwt4-frozen-refinement-20261107/refinement-211.png)

## Execution and verification

The unloaded start reaches full load in **19 accepted steps**, each in its
own bounded process. All **19 processes exit successfully**, with **zero
rejected load attempts** and no timeouts. Individual process durations are
40.42–57.90 seconds. Their sum is 883.20 seconds, excluding the gaps between
jobs; this is not a browser or uninterrupted solve timing. Each job retains
a 90-second cap, a 512 MiB address-space limit, and one BLAS thread.

The independent assessor restores every checkpoint, verifies its source,
kernel and continuation chain, and rebuilds the physical residual. The
maximum rebuilt boundary residual, including the final boundary, is
**8.04552e-13**, below 1e-12. Root-moment and nodal-field assessors also exit
successfully. Both refined meshes and all seven 0.1% gates were pinned before
the study. All **139 production modules** remain identical to its archived
kernel.

## Startup rank work and remaining work

The next nested mesh has 419 nodes and 5,028 mechanical unknowns. A dense
mechanical SVD would exceed the current bounded allocation. Previous sparse
condition estimates remained below 1e-10, so they are not used as certificates.

A separate [source-tree nullspace argument](source-flexible-tree-rank-20261107.md)
uses conservative force/moment balance followed by source beam compatibility
at zero load. Eight independent small-system tests now pass, including all
mechanical first-variation columns, section offsets, flexible/rigid sections,
signed hinges, nonzero circulation, and singular Ground counterexamples.
The initial two failed test runs are retained: their fixture issues were an
unsupported two-panel mesh and the constructor's expected missing-Ground
rejection. No production equations were changed to make these tests pass.

The proposed argument concerns algebraic rank, not a numerical condition
bound. It is not enabled in production. A large-mesh scope check does not
establish a 419-node equilibrium or a delivered startup optimization.
The completed scope preflight accepts the literal 55/107/211/419-node
configurations and rejects all eight invalid/unsupported controls.
Production integration, fallback and browser verification remain necessary
before using a new certificate. Circulation rank and physical residual
checks must remain separate.

Further spatial refinement, element loads/circulation fields, full PM2 gust
histories, other PM2 configurations, historical startup and attachment
qualifications, the separate Fixed-1 refinement, and shared execution
registration remain open.

## Retained evidence

The study is `artifacts/isae/ffwt4-frozen-refinement-20261107/`:

- `nodes-211/job-019/result.json` contains the final equilibrium;
  `nodes-211/assessment.json` independently verifies all 19 boundaries.
- `comparison-107-211.json` and `nodal-fields-107-211.json` retain every
  evaluated field and the unchanged numerical gates.
- `summary-211.json`, `refinement-211.png` and `refinement-211.svg` collect
  the verified equilibrium and mesh results.
- `source-tree-oracle-tests-v3.xml` records the eight passing oracle tests.
  Original failed logs, XML files and process receipts are preserved.
- The study plan, frozen helpers, per-process execution receipts and all
  original 55/107-node results are retained without rewriting them.
