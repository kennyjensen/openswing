# AE-2: complete uncoupled 10° sweep

Observed 2026-11-10 UTC. AE-2 advances from **1,164/2,200 to 1,324/2,200**
at the existing 5% tolerance. All **160 available comparisons** in the
uncoupled wing's 10° sweep pass: 20 archived speeds, four sensor channels,
and both nominal meshes. Median/max relative error is **0.16670% / 2.68729%**.
Production equations, defaults, model bytes, reference values and numerical
acceptance gates are unchanged.

This subset is **160/168**, including eight unavailable zero-speed values.
It belongs to the existing primary AE-2 total and is not an independent
progress scope. AE-2 as a whole remains open.

## Agreement across the speed range

The original `[03_90].asw` model and its shell driver command literal beta
10° for the vertically mounted wing. The table gives the larger error across
the nominal 80/160 meshes. Every intermediate integer speed was tested too.

| IAS, m/s | Earth Y error | Heading error | Sensor speed error | Sensor flow-angle error |
|---:|---:|---:|---:|---:|
| 1 | 0.15580% | 0.05300% | 0.08712% | 2.23663% |
| 5 | 0.16975% | 0.03329% | 0.08925% | 2.23988% |
| 10 | 0.14324% | 0.10584% | 0.09784% | 2.27103% |
| 15 | 0.21679% | 0.64857% | 0.11783% | 2.45320% |
| 20 | 0.83448% | 1.06375% | 0.15173% | 2.68729% |

![AE-2 10-degree comparison; coupled predictions remain unrun](../../artifacts/isae/ae2-beta10-sweeps-current-20261110/uncoupled-review/beta10.png)

Only the uncoupled predictions are complete in this figure. The coupled rows
show their archived reference curves; they do not imply computed results.

All **40 accepted states** pass **720 physical checks**, including a freshly
rebuilt full residual, force/moment balance and sensor reconstruction. All
**20 mesh pairs** pass; the largest deflection/heading change on refinement
is **0.01266%**. The new sweep's maximum fresh full residual is
**9.65393e−13**, below the unchanged 1e−12 gate.

## Execution accounting

The 40 original numerical jobs produced 39 complete states and one wall
timeout, at 1 m/s on the coarse mesh. That timeout used 3.55 CPU seconds
and saved no complete state. One separately declared retry, with identical
inputs and limits, completed successfully and passed its four comparisons.
The original failure remains immutable. The retry replaces its unresolved
comparison slot once; it does not add another reference slot.

All **41 numerical children** were reaped. They ran serially with one BLAS
thread, 512 MiB address space, 15 CPU seconds and a 25-second wall deadline.
The two original zero-speed records were classified without numerical jobs;
their eight literal unavailable references remain required. All 42 original
records in this uncoupled sweep now have terminal outcomes.

The saved-evidence audit rehashed **2,509 files** and freshly checked
**2,573 path mappings** before publication. Its first invocation exhausted a
60-second file-audit deadline before publishing a final report. The complete
rerun used 15.70 CPU seconds / 74.08 wall seconds under a 30-CPU-second,
180-wall-second, 512-MiB metadata limit. It imported no production solver and
performed no physics calls. Numerical worker limits and gates did not change.
The existing strict-result reconciliation helper applies the 5% policy once;
the older direct helper rejected the already-adjusted report view without
publishing a result.

## Full AE-2 accounting

| Outcome | Scalar comparisons |
|---|---:|
| Pass at 5% | **1,324** |
| Computed mismatch | 16 |
| Unresolved execution output | 20 |
| Finite reference, comparison not yet run | 744 |
| Unavailable original reference | 96 |
| Required | **2,200** |

The **335 accepted states / 1,340 computed values** pass **6,030 physical
checks** and **166 mesh pairs**. Maximum mesh change remains **0.04079%**;
maximum fresh full residual remains **9.99455e−13**. All **1,180 earlier
comparison records are exactly unchanged**.

The sixteen earlier mismatches remain: twelve negative-coupling 5° values
have median error **249.161%**, range **227.303–356.704%**; four negative-
coupling 1°/16 m/s values have median **12.2094%**, range **8.6983–15.7294%**.
Five unresolved mesh conditions retain twenty outputs. None of these outcomes
is resolved by the new uncoupled sweep.

Next: the negative- and positive-coupling 10° sweeps, then all three 15°
sweeps. These contain the remaining 744 finite unrun values. Keep the earlier
negative-coupling discrepancies and unfinished executions open. Browser/build
checks remain held; no background numerical jobs were started.

Setup follows Jan, **Part IV §3.2, pp. 8–12**, with the original models,
drivers and sensor exports. The target is archived ASWING output, distinct
from experiment. Exact historical startup settings and executable provenance
remain unresolved. See the [authoritative reference index](aswing-authoritative-references.md).

Evidence: [full audit](../../artifacts/isae/ae2-beta10-sweeps-current-20261110/uncoupled-review/assessment-extended.json),
[summary](../../artifacts/isae/ae2-beta10-sweeps-current-20261110/uncoupled-review/summary.json),
[original source review](../../artifacts/isae/ae2-beta10-sweeps-current-20261110/source-review.json),
[execution receipts](../../artifacts/isae/ae2-beta10-sweeps-current-20261110/uncoupled-review/attempts.json),
[retry declaration](../../artifacts/isae/ae2-beta10-sweeps-current-20261110/uncoupled-retry/authorization.json),
[accepted comparison report](../../artifacts/isae/ae2-beta10-sweeps-current-20261110/uncoupled-review/accepted-run/report.json).
