# AE-4: current flutter-boundary comparison

Observed 2026-11-12 UTC. The registered undeformed-wing scope advances from
**19/1,200 to 50/1,200 at 5%**. Six current-code states at IAS 68, 69 and
70 m/s on nominal 40/80 meshes produce **31/36 matches**. The critical mode
changes from decay to growth between 69 and 70 m/s on both meshes, agreeing
with the archived ASWING bracket. Damping accuracy and mesh convergence remain
open; this is not complete AE-4 validation.

## Native results and remaining discrepancy

| IAS (m/s) | ASWING critical real part (1/s) | Nominal 40 | Error | Passes | Nominal 80 | Error | Passes |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 68 | −0.99432374 | −0.91210191 | 8.269% | 5/6 | −0.94750135 | 4.709% | 6/6 |
| 69 | −0.17807850 | −0.09116090 | 48.809% | 5/6 | −0.12546391 | 29.546% | 5/6 |
| 70 | +0.63928722 | +0.72824345 | 13.915% | 5/6 | +0.69693352 | 9.017% | 5/6 |

All eighteen frequency comparisons pass, with maximum error **0.1894%**.
The five failures are critical real components; their absolute discrepancies
are only 0.0526–0.0890/s, but the original componentwise 5% rule still applies.
No near-neutral exception or frequency-only acceptance was introduced.

The four 69/70 critical roots reproduce the earlier
[crossing study](isae-ae4-crossing-20261105.md) exactly. These are fresh solves
registered in the full sweep, not a new physical improvement or four new
independent historical targets. IAS 68 is new sampled coverage.

Linear interpolation between 69 and 70 m/s gives an onset estimate of
**69.1113 m/s on nominal 40**, **69.1526 m/s on nominal 80**, versus
**69.2179 m/s for ASWING**. Differences are 0.1540% and 0.0944%. These are
interpolated diagnostics, not exact neutral-speed solutions. The verified
bracket remains one metre per second wide.

The separate **0.1% mesh gate passes 9/18 components**, three at each speed.
Critical-real changes are 3.736%, 27.341% and 4.493% at 68, 69 and 70 m/s.
Native agreement on the fine 68 m/s grid does not establish mesh convergence.
All **96 helper physical/source checks** pass, together with the adapter's
independent full-pencil, mass-normalization and root-clamp contracts.

The cumulative registered ledger has **56 finite paired components: 50 pass
and six fail**. Its selected denominator is **84**, retaining twelve blocked
initial-point components and sixteen unmatched 103 m/s components.
**1,116 further declared components remain unrun.** The six finite failures
have median error **11.466%**, range **5.913–48.809%**, including the retained
100 m/s damping failure. Thirteen modal jobs have numerical evidence: seven
from the previous ledger and six here. Five of the inherited jobs remain
historical evidence, not fresh current-code replays.

The overlapping accumulated sample becomes **86/108**: the previous 75/96
plus IAS 68's 11/12. Repeating 69/70 does not increase that count. All eighteen
historical modal tables and their **9,480 components** remain separately
inventoried. Neither alternative ledger is added to the primary sweep.

## Bounded execution and validation changes

The reusable [runner](../../scripts/replay_isae_ae4_bounded.py) plans all 236
historical/declared jobs, runs at most one selected job per invocation, and
retains failed attempts and unavailable values. A live advisory lock prevents
overlapping invocations. Terminal jobs are never silently rerun. Repeating the
completed IAS 68 / nominal 80 selection was verified to start no new worker.

```sh
.venv/bin/python scripts/replay_isae_ae4_bounded.py \
  --output-dir artifacts/isae/NEW_AE4_RUN --plan-only
.venv/bin/python scripts/replay_isae_ae4_bounded.py \
  --output-dir artifacts/isae/NEW_AE4_RUN --speed 68 --nominal 80
```

Use a fresh directory after a source change. Each numerical child retains
**one BLAS thread, 512 MiB address space, 15 CPU seconds and 25 wall seconds**.
Library preload is separately bounded. The parent waits for and reaps each
child before returning. No background solver or additional watcher is started.

Validation now loads complete matrices into sparse storage without first
allocating dense square copies. Only exact zeros are implicit; even the
smallest nonzero subnormal entry is retained. Real and imaginary vector
actions, complete left/right equations, Frobenius norms and mass pairing
remain checked. No matrix approximation, reduction or threshold is introduced.
The numerical child releases its inherited full-sweep bookkeeping while the
parent retains the complete plan. The adapter also reuses the helper's checked
raw result instead of decoding the entire 71 MiB export a second time.

The final **68 m/s / nominal 80 cold solve and full validation complete in
7.13 CPU /8.21 supervised wall seconds**, peak RSS **298.8 MiB**, within the
unchanged limits. This is one native run, not a browser performance benchmark.
The coarse counterpart completes in 4.68 CPU /6.33 wall seconds.

The earlier fine 69 and 70 m/s cold solves had both saved their results before
validation allocation failures. Separate authenticated assessments recover
them without repeating either numerical solve. The final recovery workers use
2.75 and 1.63 CPU seconds respectively. Original failed receipts, raw matrices,
requests and source hashes remain intact. One additional saved-result assessment
failed during JSON decoding before inherited bookkeeping was released; it too
remains recorded. All nine numerical/recovery children are terminal and reaped.

**85 distinct focused regressions have passing evidence across serial runs**:
25 matrix-action/classification tests, 35 existing adapter checks, 24 scope/
runner tests and one new result-reuse regression. The combined first test run
hit its wall cap; smaller runs exposed two remaining dense-array length calls,
which were corrected. Intermediate fixture failures in the new transport test
are retained in its XML receipts. Production equations, browser code, reference
targets, pairing policy and numerical gates are unchanged. Browser/build checks
remain held.

## Setup, evidence and next work

The literal original `2-Flutter_Undeformed/Pazy_wing.asw` and `alpha_0.sh`
remain authoritative. The declared scope retains the vertical solid-wall mount,
fixed frame, density 1.23, Mach zero, zero incidence, lag, pointwise circulation,
updated influences, four-mode local search and shift `0+200i`. Updated influences
are an explicit declared alternative, not a recovered historical default.
Nominal cosine 40/80 retain the material break, giving 41/81 elements. The
literal insertion-stack map remains native index = IAS + 1; historical startup,
node generation and restraint settings are not authenticated.

Jan Part IV §3.4, pp.13–16, distinguishes the unloaded vertical Pazy wing,
flutter/divergence and nonlinear limit cycles. Drela's unsteady §13.3.1,
Eqs.147–152, pp.28–29, specifies the shifted-LU/Arnoldi modal method. See the
[authoritative reference index](aswing-authoritative-references.md). Original
ASWING exports remain the targets; experimental curves are not substituted.

- [Combined audit, every retained comparison and mesh errors](../../artifacts/isae/ae4-crossing-current-audit-20261112/assessment.json)
- [Process closure, regression receipts and unchanged production hashes](../../artifacts/isae/ae4-crossing-current-audit-20261112/closure-audit.json)
- [Final bounded cold-run summary](../../artifacts/isae/ae4-current-crossing-r3-20261112/summary.json)
- [69 m/s saved-result recovery](../../artifacts/isae/ae4-crossing-sparse-recovery-r2-20261112/summary.json)
- [70 m/s saved-result recovery](../../artifacts/isae/ae4-crossing70-recovery-20261112/summary.json)
- [Previous 101/103 m/s findings](isae-ae4-current-20261112.md)

Next, resolve spatial convergence and near-onset damping before treating the
close flutter-speed estimate as validation. The 103 m/s modal identity and
wall/frame formulation, the remaining speed/incidence sweeps, divergence,
sensor histories and nonlinear limit cycles remain open. AE-3 remains open
at 434/725 while AE-4 is the user's selected priority.
