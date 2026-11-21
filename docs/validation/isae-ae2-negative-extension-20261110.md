# AE-2: remaining negative-coupling 1° speeds

Observed 2026-11-10 UTC. AE-2 advances from **852/2,200 to 920/2,200** at the
existing 5% tolerance. All 68 newly accepted scalar comparisons pass, with
median/max error **0.80990% / 3.65962%**. Every finite negative-coupling 1°
condition has now been attempted on both original meshes. Production equations,
defaults, native targets and numerical acceptance gates are unchanged.

The negative-coupling 1° subset is **148/168**: 148 computed values pass, twelve
outputs remain unresolved from three executions, and eight unavailable original
values remain required. Its computed median/max error is **0.54922% / 4.07235%**.
This subset is part of the primary total, not an independent progress scope.

## Agreement across the speed range

The new results match the large negative deflection at 15 m/s and the positive
branch at 18–20 m/s where completed. The earlier 17 m/s comparison already
matches on both meshes. The unresolved 16 m/s condition lies near the archived
branch change; its execution failures do not yet establish a reference mismatch.

The table gives the largest error across the newly accepted meshes at each
speed. Only nominal 80 is available at 18 m/s.

| IAS (m/s) | Accepted meshes | Earth Y error | Heading error | Sensor speed error | Sensor flow-angle error |
|---:|---|---:|---:|---:|---:|
| 9 | 80, 160 | 0.50038% | 0.48348% | 0.00140% | 2.05436% |
| 10 | 80, 160 | 0.57129% | 0.55463% | 0.00177% | 1.98031% |
| 11 | 80, 160 | 0.67421% | 0.65770% | 0.00220% | 1.87497% |
| 12 | 80, 160 | 0.83308% | 0.81496% | 0.00199% | 1.71495% |
| 13 | 80, 160 | 1.10527% | 1.08645% | 0.00299% | 1.44379% |
| 15 | 80, 160 | 1.65071% | 1.61465% | 0.02188% | 3.65962% |
| 18 | 80 | 1.22365% | 1.23414% | 0.00217% | 3.64619% |
| 19 | 80, 160 | 0.90102% | 0.92454% | 0.00169% | 3.34856% |
| 20 | 80, 160 | 0.70300% | 0.72783% | 0.00161% | 3.15295% |

![Original 1° references and current predictions](../../artifacts/isae/ae2-beta1-negative-extension-20261110/beta1.png)

## Remaining execution gaps

| Condition | Latest outcome | Complete saved solution |
|---|---|---|
| 16 m/s, nominal 80 | Exit −9 after 15.24 CPU seconds, with a 15-second hard CPU limit | None |
| 16 m/s, nominal 160 | Exit −9 after 15.18 CPU seconds, with the same limit | None |
| 18 m/s, nominal 160 | Original wall timeout; exact-input retry exits −9 after 15.19 CPU seconds | None |

The original 12 m/s coarse run also timed out without a complete state. Its
predeclared exact-input retry completes normally and passes all four references.
The finer 18 m/s retry remains a failure; it is not replaced by its coarse result.
No failed or partial state earns a comparison pass.

Twenty new original jobs and two retries ran serially with one BLAS thread,
512 MiB address space, 15 CPU seconds and a 25-second supervisor deadline per
numerical worker. All 22 children are terminal and reaped: seventeen successful
completions and five retained failures. These seventeen accepted states add
306 physical checks. No saved-state recovery was available for the new failures.

Next: trace the cold continuation at 16 m/s and fine-grid 18 m/s in bounded
stages, with a completed neighboring case as a control. Keep full residual,
force/moment balance and original input checks. Positive-coupling 1° and the
10°/15° sweeps remain subsequent coverage work; the existing 5° branch
discrepancy stays open.

## Full accounting

| Outcome | Scalar comparisons |
|---|---:|
| Pass at 5% | **920** |
| Computed mismatch | 12 |
| Unresolved execution output | 28 |
| Finite reference, comparison not yet run | 1,144 |
| Unavailable original reference | 96 |
| Total required | **2,200** |

The **233 accepted states / 932 computed values** pass **4,194 physical checks**.
All **115 mesh pairs** pass 230 deflection/heading checks; maximum mesh change
is **0.04078%** and maximum fresh full residual is **9.995e−13**. Overall computed
median error is **0.36722%**. All **372 computed 1° values pass**, with median/max
error **0.42870% / 4.07235%**. The uncoupled 1° subset remains **224/232**, with
all 224 available values passing.

The twelve computed mismatches remain the original 5° negative-coupling values:
median **249.161%**, range **227.303–356.704%**. Seven conditions lack accepted
solutions: four at 5° and three at 1°. The original 1° plan has **98/162 terminal
records** and **64 unrun records**: the positive-coupling sweep and the two
negative-coupling zero-speed records whose unavailable values remain required.

All earlier accepted scalar rows remain exactly unchanged. Twenty-five original
failed executions remain recorded: twelve conditions have verified saved
completions, six have successful exact-input retries, and seven are unresolved.
Including two unsuccessful retries, 27 failed execution attempts are retained.
Each condition contributes at most once; branch diagnostics add no native votes.

## Audit reliability

The first full saved-file audit exits 142 without publishing a candidate or
assessment, consistent with its 60-second alarm. A new process-local path cache
removes repeated filesystem path resolution while retaining the unchanged
assessor and digest checks. Every cached mapping is resolved afresh before the
final report is published. Changed symlinks or working directory abort
publication; strict missing-path behavior is preserved.

Five tests pass, including a changed symlink whose targets have identical bytes,
working-directory changes, strict resolution, fresh final checks, and rejection
of publication while restoring the original resolver. The final full audit
passes within the existing 15-CPU-second / 60-second-alarm limits. It freshly
checks **1,012 distinct file digests** and **1,071 path mappings**; the cache
reuses 2,644 of 3,715 resolution requests. No numerical or reference check is
omitted. The intermediate 916-pass assessment and failed-audit receipt remain
preserved alongside the final 920-pass assessment.

The setup remains the literal archived models/scripts, Jan Part IV §3.2,
pp. 8–12, and the [authoritative reference index](aswing-authoritative-references.md).
Native ASWING output remains the target. Historical startup settings and exact
executable provenance are not newly established. Browser/build checks remain held.

[Full final audit](../../artifacts/isae/ae2-beta1-negative-extension-20261110/assessment-after-retries.json) ·
[Original attempts](../../artifacts/isae/ae2-beta1-negative-extension-20261110/attempts.json) ·
[Declared retries](../../artifacts/isae/ae2-beta1-negative-extension-20261110/wall-retries/authorization.json) ·
[Reconciled receipts](../../artifacts/isae/ae2-beta1-negative-extension-20261110/accepted-after-retries/reconciliation.json) ·
[Path-audit driver](../../scripts/assess_isae_ae2_resolved.py) ·
[Integrity tests](../../tests/test_isae_ae2_resolution_cache.py)
