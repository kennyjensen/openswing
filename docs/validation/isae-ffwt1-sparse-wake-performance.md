# Sparse wake-derivative performance

Updated 2026-10-16. This follows the
[mounted geometry integration](isae-ffwt1-influence-performance.md). The
optimization is included in the tested 105-module local browser release.
It changes work performed when forming derivatives, without
changing equations, mesh, continuation settings or acceptance tolerances.

## Change

Wake motion is still accumulated with the original compensated endpoint
grouping and separate source ownership. The derivative contraction now selects
only groups with an exactly nonzero accumulated direction. Core derivatives
retain their receiver-specific exclusion masks, and entirely zero core
directions skip their contraction. Small nonzero contributions remain included.
Bound and wake coefficients remain separate.

## Recorded comparisons

| Check | Result |
| --- | --- |
| Full Daedalus tangent, revision 05 | 78.365 s |
| Same tangent, sparse wake derivatives | 5.805 s |
| Complete matrix comparison | All 12,369,289 entries exactly equal |
| Residual before and after tangent assembly | Exactly equal, including fresh-network replay |
| Cold mounted Daedalus solve | 41.450 s |
| Fresh full physical residual | 8.50847e-14 |
| Cold outputs, physical replay, captured arrays and iteration history versus revision 05 | Exactly equal |

The tangent timings are one sequential pair of fresh single-threaded processes,
with other numerical work and archive compression held. They show a 13.5-fold
improvement for this tangent assembly, not a general timing distribution. The
cold solve used `dae.asw`, 48 discretization intervals, speed 30 ft/s, incidence
5 degrees and Mach 0.1, starting without a saved solution. Its 3,517 unknowns
and all solver settings match the earlier revision-05 run. That run took
179.233 seconds during concurrent verification, so the two cold times are not
a controlled speedup ratio.

All three full tangents used the complete geometry path without unsupported
geometry fallbacks. A separately declared comparison against the complete
saved revision-05 result passed with zero difference. This does not change the
original fixture result: the same ten shell shear-stress fields still fail
the unchanged `1e-8 + 1e-8*abs(reference)` fixture bound. Their diagnosed
sensitivity to tiny state differences remains recorded in the prior study.

## Verification and limits

Before integration, 127 focused native checks passed, including dense original
derivative comparisons and existing geometry/ownership controls. Source review
found no material ownership or core-mask defect. The portable regression file
preserves those 46 added comparisons and adds cases with fully excluded core
directions and simultaneous dense endpoint/core changes. All 169 checks against
the integrated source pass in 103.74 seconds, covering sparse and original
vortex derivatives, shared-source ownership, mounted corrections, frequency
inputs, time-circulation derivatives and frame caches.

The earlier full-matrix comparator's sparse-indexing error and the cold-run
launch-coordination error are retained as harness failures. They added no
scientific solve: there was one cold attempt, and the existing driver reaped
its worker. Its original tool-session metadata was lost during interruption;
the recorded shell, driver and worker processes are all absent.

A separate fresh offline browser solve returned in 100.189 seconds between
the observed request and worker completion, after 31.984 seconds from context
start to offline readiness. Its full residual was 9.03558e-14 and all 49,485
numeric output comparisons passed the unchanged bounds. The actual JSON
download completed and retains every worker-result field exactly. The saved
image visibly shows the bent aircraft, grid, loading plot and coefficients.
All 105 kernel modules, runtime/UI bytes and offline requests were verified.

The original browser harness remains failed on two exact checks: an omitted
circulation-mode map versus explicit zero entries, and twelve floating strip
coordinates differing by at most 1.42109e-14. Existing circulation code treats
omitted and zero counts as the same pointwise representation. Discrete strip
beam/lifting identities and order agree. The existing public mesh-identity
validator passes in both directions, and both mode maps select 217 pointwise
unknowns. A separate saved-data qualification records this equivalence without
rewriting either output. These exact failures remain recorded; the numerical
comparison was not weakened. Later live Fit/WebGL-health and
status-history checks were skipped in that attempt. Saved-data checks, export
evidence and image inspection are reported separately.

A later public saved-project import completes the display/export checks with
zero scientific solves. Desktop and mobile aircraft, loading and structure
plots are visible; Fit and WebGL health pass. Both actual result downloads
retain the complete saved output exactly. The status reads "Saved solution
opened", and does not imply a fresh convergence check. All 105 served module
hashes, the literal manifest and observed runtime/UI assets pass. The first
saved-result attempt is retained as a test-server encoding failure: its
response observer re-encoded non-ASCII bytes, while every loaded worker hash
was correct. A server with explicit UTF-8 text headers resolves that failure.

The release's source and offline-app ZIPs pass complete member/byte checks.
This source-only build preserves all code, tests, examples, report summaries
and the 150-entry archive catalog. Optional raw experiment ZIPs are absent
from these downloads, and the UI correctly omits their download link. They
remain preserved in the original research workspace; raw archive links in
reports require those optional files.

This diagnostic preserves the historical fixture failure and does not relabel
the previously held browser experiment. The local served app is updated to
105 modules without restarting its server. No original ASWING executable is available.
ISAE coverage remains **17 partial / 24 pending / 0 fully validated**; physical
agreement and full ASWING feature parity remain unfinished.

Detailed working records are in
`/tmp/openswing-isae-ffwt1-20261015/influence-performance-17`, under
`sparse-ray-prototype`, `sparse-ray-tangent-benchmark`, `sparse-ray-mounted`,
`sparse-ray-integration-review`, `integrated-06` and `browser-sparse06`.
The [recorded-results summary](isae-ffwt1-sparse-wake-performance.json) includes
the native, browser, source-review and identity-qualification records.
Release preparation, UI replay, package checks and publication receipts are
recorded separately under
`/tmp/openswing-isae-ffwt1-20261015/release-sparse06`.
