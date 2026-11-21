# Bounded rank equilibration for the finer Flare20 mesh

The 211-node Flare20 model now gets past its unloaded rank bottleneck and
saves accepted load states. Two small native jobs complete in **42.72 and
44.67 seconds**, each below its 90-second limit. Their rebuilt residuals are
**6.4350e-13** and **7.7938e-13**, with two accepted steps and no rejection.
This remains a partial continuation, not a full-load equilibrium or gust
comparison. Native coverage is unchanged at **200/8,000** for FFWT-4.

## Algorithm and scope

The existing physical and numerical rank checks remain first. If the first
mechanical SVD is inconclusive or exceeds its original 32 MiB input scope,
the new route can continue the same invertible row/column norm scaling to at
most **300 total updates**. It permits one additional SVD with at most
**64 MiB of dense input**; LAPACK workspace is additional. Zero/nonfinite
norms and nonpositive/nonfinite accumulated scaling factors cannot certify
rank. Unsupported or still inconclusive matrices retain the full fallback.

The rank gate stays at **1e-10**. The optional maximum log-norm error target
of 0.001 only stops scaling early; it is not a rank certificate. The literal
211-node block reaches the update cap without meeting that norm criterion,
but its actual singular-value ratio is about **1.57e-10**, which passes the
unchanged rank gate. The earlier 30-update ratio was 8.17e-11. The previous
90-second timeout and both diagnostic matrices remain in the
[mesh study](isae-ffwt4-pm2-mesh-20261106.md).

The Newton matrix, nonlinear physical residual, 5-degree rotation guard,
continuation increments and rejection limits are unchanged. Scaling is only
used for the rank decision; the original matrix is returned to the solver.
Existing cases that pass the earlier checks retain their earlier path.
No source geometry, material law, load, stall parameter or comparison target
is changed to obtain a pass.

## Native verification

All **66 focused checks pass**: 33 rank/scaling checks and 33 continuation
regressions. The rank suite includes the actual cached 2,532-row Flare20
mechanical block, four original physical hinge matrices, their explicitly
released-axis controls, near-dependent rows, redundant constraints,
noninvertible scales and the dense-input limit. Independent transformed
matrices retain the same rank decisions. Continuation regressions preserve
bit-for-bit final states and hinge charts on three synthetic formulations.

The two fresh literal jobs use 211 nodes, 208 elements and 2,740 unknowns.
The first nonzero load target is reached at 23.42 seconds in the first job;
the old attempt was still constructing the initial full Jacobian when its
90-second limit expired. That is a startup comparison, not a claimed ratio
of complete solve times. The saved load fractions are 3.24916e-6 and
7.96455e-6. Load fraction is not computational completion percentage.

Both jobs use one BLAS thread and a 512 MiB process address-space cap. Each
result is rebuilt on a fresh network; the chain assessor also checks physical
residuals, exact requests, source/kernel/predecessor hashes, rotation guards
and counters. The literal 16-degree sideslip and both qualified rigid-pylon
attachments remain unchanged. Historical attachment semantics and startup
defaults retain their existing qualifications.

The generating kernel is frozen in
`.reference/solver-snapshots/ffwt4-rank-refined-20261106/`. Earlier checkpoints
stay with their original kernels; an unfinished checkpoint cannot migrate to
the changed kernel merely by editing its hash. Completed equilibrium evidence
from the 55/107-node study remains preserved.

## Browser and package verification

All **29 built-browser checks pass**. `scripts/test-refined-rank-browser.mjs`
runs the actual built worker on the literal 211-node request, with a full
page/worker reload between its first two accepted load steps. The steps take
**39.41 and 37.96 seconds**, with physical residuals **6.4360e-13** and
**7.7611e-13**. Maximum coordinate differences from the corresponding native
states, normalized by `1 + abs(native coordinate)`, are **3.24e-16** and
**3.74e-16**. These timings cover one accepted load step each, not a complete
equilibrium. The browser rank ratio is 1.57366e-10 against the unchanged gate.

The checks also reject released mechanisms, redundant constraints, a changed
checkpoint checksum and a changed flight condition. Both qualified pylons,
16-degree sideslip, bounded rank work and all 139 kernel hashes are retained.
There are no page errors or external requests. The report, complete result
packets, progress records and executed runner are retained under
`artifacts/isae/ffwt4-rank-refinement-20261106/browser/`.

`scripts/verify-isae-rank-refinement.py` checks the frozen/current/shipped
module hashes, test evidence, literal continuation audit, browser evidence
and source/local downloads. The study directory retains process receipts
and `verification.json`. The regular workbench still has no equilibrium
checkpoint resume controls; these checks exercise its solver API.

The [subsequent complete continuation](isae-ffwt4-pm2-211-20261107.md) reaches
full load in 17 accepted steps. Its 107/211-node comparison fails all seven
root/nodal mesh gates (0.108–0.236% changes against 0.1%). That follow-up
retains one process timeout and independently validates its complete saved
boundary before reuse. The original two-step evidence above remains unchanged.
Mesh accuracy, element/circulation fields and PM2 gust histories remain open.
