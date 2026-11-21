# AE-2: all available uncoupled 1° references pass

Observed 2026-11-10 UTC. The uncoupled 1° sweep now matches **224/224 available
native ASWING values** at the existing 5% tolerance: all 28 nonzero speeds,
four sensor channels and both nominal 80/160 meshes. Its tracked fraction is
**224/232**, retaining eight unavailable zero-speed values. The full AE-2 score
advances from **764/2,200 to 784/2,200**. The family remains incomplete.

## Closing the five execution gaps

Five independent cold retries use the exact original models, conditions,
discretization and acceptance gates. Four workers finish normally. The 19 m/s
fine-grid worker times out after saving a complete solution; a separate restore
passes all eighteen physical checks at full residual **2.471e−13**. No additional
equilibrium solve is used for that verification. All six numerical children
are terminal and reaped; one timeout receipt remains alongside the five
successful execution/verification receipts.

| IAS (m/s) | Nominal mesh | Sensor Earth Y error | Heading error | Sensor speed error | Sensor flow-angle error | Passes |
|---:|---:|---:|---:|---:|---:|---:|
| 4 | 80 | 0.34989% | 0.28356% | 0.00080% | 2.24584% | 4/4 |
| 18 | 160 | 0.48921% | 0.42529% | 0.00123% | 2.07898% | 4/4 |
| 19 | 160 | 0.51415% | 0.44973% | 0.00131% | 2.05228% | 4/4 |
| 21 | 80 | 0.57546% | 0.50408% | 0.00134% | 1.98907% | 4/4 |
| 21 | 160 | 0.57879% | 0.51194% | 0.00134% | 1.98512% | 4/4 |

All twenty new comparisons pass; median/max error is **0.49664% / 2.24584%**.
Across the complete finite uncoupled 1° subset, median/max error is
**0.39851% / 2.25212%**. Across all currently computed 1° values, **236/236 pass**,
with median/max error **0.40754% / 4.07235%**. These computed-only summaries are
not additional progress scopes.

![Original 1° references and current predictions](../../artifacts/isae/ae2-beta1-uncoupled-retries-20261110/beta1.png)

## Full AE-2 accounting

| Outcome | Scalar comparisons |
|---|---:|
| Pass at 5% | **784** |
| Computed mismatch | 12 |
| Unresolved execution output | 20 |
| Finite reference, comparison not yet run | 1,288 |
| Unavailable original reference | 96 |
| Total required | **2,200** |

The **199 accepted physical states / 796 computed values** pass **3,582 physical
checks**. All **98 compared mesh pairs** pass 196 deflection/heading checks,
with maximum change **0.04078%**. Maximum full residual remains **9.995e−13**.
Overall computed median error is **0.35748%**. The twelve 5° negative-coupling
mismatches remain unchanged: median **249.161%**, range **227.303–356.704%**.

The 1° plan still has 62 distinct terminal records and **100/162 records unrun**;
retries do not add conditions. Its terminal 248 slots now contain 236 passes,
four unresolved outputs from negative coupling at 17 m/s on nominal 80, and
eight unavailable references. Positive-coupling 1° and all 10°/15° sweeps remain
unrun. The existing branch diagnostics remain separate from native totals.

Twenty original failed executions remain recorded. Ten were completed from
their original saved states, four now have normally completed retries, and
one has a verified state from its timed-out retry; five original conditions
remain unresolved. The additional retry timeout brings retained failed
execution attempts to twenty-one. No earlier receipt or progress event is edited.

## Reconciliation and verification

The ordinary report reader rejects duplicate job identities. A separate,
predeclared retry ledger therefore records both attempts and supplies one result
per original slot. Only unresolved failed executions qualify. Every retry must
retain the exact original inputs, source pins, numerical gates and reference
policy. Selection is independent of reference agreement: a computed mismatch
would remain a mismatch. Unaffected results are checked for exact equality.

An initial metadata-only reconciliation was rejected because the report writer
requires original strict results rather than already policy-adjusted views.
The corrected wrapper reads the original raw result files, verifies exact
reproduction of each existing policy view, and applies the unchanged allowance
once. Six tests cover changed inputs, incomplete checks, already accepted states,
failed retries and strict-versus-policy result handling.

The first full saved-file audit was killed with exit 137 before publishing;
its precise cause was not recorded. The succeeding auditor reuses duplicate
file digests within one transaction and freshly rehashes every cached file
before publication. Three additional tests verify schema parity, rejection of
same-size file changes and protection against caller mutation. The unchanged
assessor completes in **8.91 CPU seconds**, with **3,870 cache hits across 4,442
pin requests**, followed by fresh checking of **569 distinct files**. No physical
or reference check is omitted. Original limits remain: one BLAS thread, 512 MiB
address space, 15 CPU seconds per numerical worker/audit, 25-second numerical
supervision and 60-second metadata-audit alarm.

Production equations and defaults are unchanged. This validates agreement for
the current literal-file replay, not recovery of every historical startup
setting or executable revision. The [authoritative reference index](aswing-authoritative-references.md),
Jan Part IV §3.2, pp. 8–12, and the archived models/scripts remain the setup
sources. Browser/build checks remain held.

Next: complete the negative-coupling 1° coarse case at 17 m/s and the remaining
coupled sweeps, while keeping the original 5° branch discrepancy open.

[Full native audit](../../artifacts/isae/ae2-beta1-uncoupled-retries-20261110/assessment.json) ·
[Declared retries](../../artifacts/isae/ae2-beta1-uncoupled-retries-20261110/authorization.json) ·
[Both execution receipts](../../artifacts/isae/ae2-beta1-uncoupled-retries-20261110/accepted-run/reconciliation.json) ·
[Independent saved-state check](../../artifacts/isae/ae2-beta1-uncoupled-retries-20261110/saved-completion/AE-2-b01-ias019-m160/report.json) ·
[Reconciliation wrapper](../../scripts/reconcile_isae_ae2_retry_results.py) ·
[Auditor with digest reuse](../../scripts/assess_isae_ae2_cached.py)
