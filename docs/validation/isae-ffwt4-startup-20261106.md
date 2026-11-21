# FFWT-4 PM2 startup and complete matrix assembly

The literal Flare20 PM2 model now starts continuation sooner and assembles its
complete Newton matrix without probing every unknown separately. Its coupled
equilibrium is **not yet computed**: both optimized attempts below reached their
150-second process limit. Native coverage remains **200/8,000 at 5%**.

All attempts retain the original model, driver A=6°, V=22 and B=16°, finite
hinge law, source beam and moving-airflow equations, and qualified rigid-pylon
attachments. Nominal eight panels produces 55 nodes, 52 elements and 712
unknowns because source stations remain mandatory. This is a small solver
preflight, not the driver's original mesh or a mesh-converged comparison.
Other declared setup choices are recorded in each request and plan.

## What changed

At zero external load, the force/circulation block is exactly zero. The existing
sparse inverse-norm bound was inconclusive, even though an SVD of the already
assembled, two-sided equilibrated 660-row mechanical block has singular ratio
4.62568e-10 and passes the unchanged 1e-10 gate. The new bounded certificate
uses that block before rebuilding the complete physical Jacobian. It requires
a nonsingular circulation block, retains the full fallback when inconclusive,
and limits dense input to 2,048 rows. Released-hinge negative controls still
fail the same rank gate. No rigid-tree proof is assumed for the finite main beam.

The optional first-load predictor now supports the source moving-vacuum and
moving-airflow operators. The literal model's explicit load derivative agrees
with centered physical residual differences to 1.34e-12 (scaled maximum error).
It proposes 3.21264e-6 instead of 0.25 as the first target, because the initial
hinge rotation sensitivity is large. It changes no state and accepts no
equilibrium; each target still gets fresh Newton equations, physical line
searches and the existing 5° rotation guard. The full physical convergence
target remains min(requested tolerance, 1e-12).

The complete source Newton fallback now uses the existing exact internal-load,
reaction and circulation derivatives. For source coupled and moving-airflow
networks, it also uses the complete moving-field geometry decomposition.
Source beam compatibility stays in grouped residual probes: midpoint beam
derivatives are not used for source constitutive laws. Unsupported derivatives,
unknown source rate laws and unavailable geometry helpers retain physical
finite differences. Geometry captures are confined to the current state and
load fraction; they do not freeze the nonlinear residual.

## Retained runs

Each process uses one BLAS thread and a 512 MiB address-space cap. Elapsed
numbers below come from each run's monotonic progress clock; they are individual
observations on UserLAnd, not a controlled whole-solve benchmark.

| Kernel | First nonzero load target attempted at | Complete matrix observation | Terminal result |
| --- | --- | --- | --- |
| Before this change | 82.516 s | Initial full rank matrix: 78.068 s | 150 s cap, exit 124 |
| Rank certificate and predictor only | 4.327 s | Loaded full rebuild still incomplete at the cap | 150 s cap, exit 124 |
| Rank, predictor and full source matrix | 7.969 s | Loaded 712-column matrix: 8.653 s | 150 s cap, exit 124 |

The final run starts 11 nonzero load attempts; the last requested factor is
0.000271475. This is not a converged full-load result or a percentage of solver
completion. No final equilibrium or native predictions are saved. Remaining
work is to complete and audit the soft-hinge continuation, preserve useful
accepted state between bounded jobs, and establish the other PM2 equilibria
and histories. Full-window mesh/time accuracy and shared execution registration
remain separate requirements.

## Verification and evidence

The rank/predictor group passes 52 tests, including threshold boundaries,
physical saved matrices, released mechanisms, frame motion and predictor
fallbacks. The full-matrix and existing network regression group passes 27
tests. It compares complete matrices with original scalar physical stencils,
checks every source pose column against centered complete residual differences
at loaded states, exercises frozen influences and moving frames, and verifies
exception cleanup and helper fallbacks. Scaled derivative differences are
required below 2e-6. Dense and sparse assembly preserve identical entries.
These are algorithm checks, not new archived ASWING comparisons.

Evidence is under
[`artifacts/isae/ffwt4-startup-20261106/`](../../artifacts/isae/ffwt4-startup-20261106/):
`probe.json`, `tests.xml`, `rank-predictor-final.xml`, `full-tangent-regression.xml`, and each attempt's
`plan.json`, `request.json`, `progress.jsonl` and terminal `execution.json`.
The earlier failed native test assertion is retained in `full-tangent-tests.xml`;
it incorrectly assumed an ungrouped internal-load baseline. Physical matrix
comparisons passed; the corrected test compares actual evaluation counts.

Exact 138-module kernels before this work and after only rank/predictor changes
are archived under `.reference/solver-snapshots/ffwt4-before-startup-rank-20261106/`
and `.reference/solver-snapshots/ffwt4-rank-predictor-20261106/`. Historical plans
are not rebound to the newest code. The final attempt verifies all its current
kernel, model, driver and helper hashes. The independent ongoing Fixed-1 history
continues to use its own older pinned kernel.
The final optimized kernel is separately archived under
`.reference/solver-snapshots/ffwt4-startup-full-20261106/`.

The first WASM run is retained in `wasm/report.json`. Its comparison to the
old forward-difference geometry stencil failed a 2e-6 threshold. The native
`full-geometry-stencil-diagnostic.json` identifies a 3.2611e-6 error in that
reference, stable across centered steps from 1e-4 to 3e-7; the optimized
column differs from centered equations by at most 1.787e-7. The corrected WASM
check uses centered differences of the complete physical residual for every
matrix column, keeping the same 2e-6 accuracy gate. The original forward matrix
remains a recorded performance/control comparison. No production equation or
solver tolerance changed in response to this test failure.

The corrected built-kernel WASM check passes in `wasm-verified/report.json`.
The literal PM2 rank check takes 7.443 s, passes at singular ratio 4.62568e-10,
and uses zero full rank rebuilds. The predictor agrees with native arithmetic;
all four threshold controls and the explicitly released-hinge rejection pass.
For the separate 128-unknown moving-frame synthetic fixture, the complete matrix
takes 26 residual calls instead of 129 (1.910 versus 4.525 s). All 128 columns
agree with centered physical derivatives to a maximum scaled error of
1.877e-7, below the unchanged 2e-6 test gate. All 138 built module hashes match
the current kernel. This timing is a matrix measurement, not a full-equilibrium
speedup.

The actual built Chromium app also passes all 21 checks in `browser/report.json`:
three literal PM2 imports preserve source and point positions, compatibility
notes remain visible, independent point forces/moments agree, and a bounded
source time history resumes with exact checkpoint agreement. Altered attachment
identity is rejected. There are no page errors or external requests. These
browser tests cover import, mechanical loads and checkpoint integration; the
separate WASM test above covers the new rank and complete source-matrix paths.
The application build succeeds, and `verification.json` binds these results to
the archived and shipped kernel. All 79 final native tests pass (52 rank/predictor
plus 27 source-matrix/network checks); repeated earlier groups are not added.
