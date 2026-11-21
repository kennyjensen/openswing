# AE-2: negative-coupling 1° comparisons

Observed 2026-11-10 UTC. AE-2 advances from **784/2,200 to 852/2,200** at the
existing 5% tolerance. All 68 newly completed comparisons pass: sixteen original
negative-coupling conditions at 1–8 m/s on both meshes, plus the previously
unresolved nominal-80 condition at 17 m/s. This is increased verified coverage;
production equations, defaults and acceptance gates are unchanged.

## What the new results establish

At commanded beta 1°, both original meshes now recover the positive-deflection
branch of the archived 17 m/s result. This contrasts with the still-unresolved
5° comparison, where some cold solutions reach an opposite-deflection branch.
It does not establish historical startup settings, branch stability or uniqueness.

| 17 m/s channel | Archived ASWING | OpenSwing nominal 80 | Error, nominal 80 | Error, nominal 160 |
|---|---:|---:|---:|---:|
| Sensor Earth Y (m) | 0.102923 | 0.10118049 | 1.69302% | 1.70280% |
| Heading (deg) | 7.97538 | 7.84077694 | 1.68773% | 1.70642% |
| Sensor speed (m/s) | 16.9978 | 16.99828010 | 0.00282% | 0.00282% |
| Sensor flow angle (deg) | −7.59521 | −7.28729745 | 4.05404% | 4.07235% |

The two meshes differ by **0.00994% in deflection** and **0.01901% in heading**
at that condition. The nominal-80 retry uses the exact original cold request;
no reference value supplies an initial guess or fitted parameter.

All **64 new low-speed comparisons** pass. Their median error is **0.34048%**;
the largest error is **2.25128%**, in sensor flow angle.

| Channel, 1–8 m/s on both meshes | Median error | Maximum error |
|---|---:|---:|
| Sensor Earth Y | 0.34928% | 0.44871% |
| Heading | 0.32943% | 0.43210% |
| Sensor speed | 0.00093% | 0.00128% |
| Sensor flow angle | 2.21368% | 2.25128% |

Across all currently computed 1° values, **304/304 pass**, including 80 from
negative coupling and 224 from the completed finite uncoupled sweep. Their
median/max error is **0.38435% / 4.07235%**. These computed-only summaries are
not additional progress scopes. The uncoupled tracked fraction remains
**224/232**, retaining its eight unavailable original values.

![Original 1° references and current predictions](../../artifacts/isae/ae2-beta1-negative-sweep-20261110/beta1.png)

## Full accounting and remaining work

| Outcome | Scalar comparisons |
|---|---:|
| Pass at 5% | **852** |
| Computed mismatch | 12 |
| Unresolved execution output | 16 |
| Finite reference, comparison not yet run | 1,224 |
| Unavailable original reference | 96 |
| Total required | **2,200** |

The **216 accepted states / 864 computed values** pass **3,888 physical checks**.
All **107 mesh pairs** pass 214 deflection/heading checks, with maximum change
**0.04078%**. Maximum fresh full residual is **9.995e−13**. Overall computed
median error is **0.35651%**.

The twelve computed mismatches are unchanged: 5° negative coupling at 17–19 m/s,
with median error **249.161%**, range **227.303–356.704%**. Four original 5°
conditions still lack accepted full solutions. The original 1° plan now has
**78/162 terminal records**; its terminal slots contain 304 passes and eight
unavailable values, with no unresolved execution outputs. **84 records remain
unrun**, including the remaining negative-coupling speeds and all positive
coupling. All 10°/15° sweeps also remain. Branch diagnostics add no native votes.

Next: continue the negative-coupling 1° sweep from 9 m/s in small serial jobs,
then positive coupling. Preserve the separate 5° branch discrepancy.

## Execution and evidence

Fifteen of the sixteen new original workers finish normally. The 1 m/s
nominal-80 worker hits its supervisor deadline after saving a complete state;
an independent restore passes all eighteen physical checks at full residual
**1.895e−13**, without another equilibrium solve. The separate 17 m/s cold retry
also finishes normally. All eighteen numerical children are terminal and reaped.
The new timeout and every earlier failed execution receipt remain preserved.

There are now 21 retained original failed executions: twelve conditions have
independently verified saved completions, five have normally completed retries,
and four remain unresolved. Including the earlier failed retry, 22 failed
execution attempts remain recorded. Each condition contributes at most once.

The chained reconciliation helper resolves each strict result from its recorded
original or retry location, verifies the existing policy view exactly, then
applies the unchanged acceptance policy once. Four new tests cover source-path
selection and rejection of missing, ambiguous, conflicting or changed evidence.
The final audit verifies all original inputs and comparisons, preserves every
previously accepted scalar row, and freshly checks 791 distinct files before
publication. It completes in **14.02 CPU seconds** under the existing 15-second
CPU limit. No solver or physical check is bypassed.

Numerical jobs retain one BLAS thread, 512 MiB, 15 CPU seconds and a 25-second
supervisor deadline. Browser/build checks remain held. The setup remains the
literal archived models/scripts interpreted with Jan Part IV §3.2, pp. 8–12,
and the [authoritative reference index](aswing-authoritative-references.md).
Original ASWING output remains the comparison target; experimental curves and
alternative numerical branches are kept separate.

[Full audit](../../artifacts/isae/ae2-beta1-negative-sweep-20261110/assessment.json) ·
[Declared low-speed jobs](../../artifacts/isae/ae2-beta1-negative-sweep-20261110/plan.json) ·
[Declared 17 m/s retry](../../artifacts/isae/ae2-beta1-coupled17-retry-20261110/authorization.json) ·
[Reconciled attempts](../../artifacts/isae/ae2-beta1-negative-sweep-20261110/accepted-run/reconciliation.json) ·
[Independent saved-state check](../../artifacts/isae/ae2-beta1-negative-sweep-20261110/saved-completion/AE-2-m15_02-b01-ias001-m80/report.json) ·
[Chained reconciliation helper](../../scripts/reconcile_isae_ae2_retry_chain.py)
