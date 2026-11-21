# AE-2: complete positive-coupling 1° sweep

Observed 2026-11-10 UTC. AE-2 advances from **924/2,200 to 1,164/2,200** at the
existing 5% tolerance. All **240 new scalar comparisons pass**, covering every
archived finite speed from 1 to 30 m/s on both nominal meshes. Median/max
relative error is **0.28418% / 2.38680%**. Production equations, defaults,
original model bytes, reference values and numerical gates are unchanged.

The positive-coupling 1° subset is **240/248**. Its eight unavailable original
zero-speed values remain in the denominator. These comparisons are part of
the primary AE-2 total, not an additional independent scope.

## Agreement across the speed range

This is the original `[p15_02]_S` composite model with the literal commanded
beta of 1°. The table shows the larger relative error across the two meshes
at selected speeds. All intermediate integer speeds were also tested.

| IAS, m/s | Earth Y error | Heading error | Sensor speed error | Sensor flow-angle error |
|---:|---:|---:|---:|---:|
| 1 | 0.27626% | 0.38769% | 0.00059% | 2.25296% |
| 5 | 0.31438% | 0.38609% | 0.00083% | 2.25882% |
| 10 | 0.29469% | 0.36756% | 0.00076% | 2.27547% |
| 15 | 0.26249% | 0.33977% | 0.00095% | 2.30001% |
| 20 | 0.22321% | 0.30654% | 0.00068% | 2.32901% |
| 25 | 0.18154% | 0.27091% | 0.00062% | 2.35876% |
| 30 | 0.13889% | 0.23625% | 0.00066% | 2.38680% |

![All three 1° layups against archived ASWING](../../artifacts/isae/ae2-beta1-positive-sweep-20261110/beta1.png)

The 60 fresh cold solves pass **1,080 physical checks** and add **30 complete
mesh pairs**. Every numerical child finished successfully and was reaped.
Workers ran serially with one BLAS thread, 512 MiB address space, 15 CPU
seconds and a 25-second supervisor deadline. No retry or parameter adjustment
was needed for this sweep.

## Complete 1° accounting

All 162 records in the original 1° execution plan now have terminal outcomes.
This includes six zero-speed mesh records with unavailable native values;
the four previously unprocessed records were classified without launching a
numerical worker. They add no passes. One finite condition remains unresolved.

| Layup | Passes / required values | Computed failures | Unresolved outputs | Unavailable references |
|---|---:|---:|---:|---:|
| Uncoupled | 224/232 | 0 | 0 | 8 |
| Negative coupling | 152/168 | 4 | 4 | 8 |
| Positive coupling | 240/248 | 0 | 0 | 8 |
| All 1° sweeps | **616/648** | **4** | **4** | **24** |

Across the **620 computed 1° values**, 616 pass. Median/max error is
**0.34632% / 15.72939%**. The four failures are the already documented negative-
coupling 16 m/s deflection and heading comparisons; neither their values nor
their acceptance outcomes changed.

The fine negative-coupling 18 m/s case remains incomplete. A new attempt from
its verified 62.5%-load boundary hit the 25-second supervisor deadline after
11.32446 CPU seconds, before saving a new boundary. Its terminal receipt and
source checks are retained. It adds no comparison and does not establish a
physical reference mismatch. No failed job was restarted in its original folder.

## Full AE-2 status

| Outcome | Scalar comparisons |
|---|---:|
| Pass at 5% | **1,164** |
| Computed mismatch | 16 |
| Unresolved execution output | 20 |
| Finite reference, comparison not yet run | 904 |
| Unavailable original reference | 96 |
| Required | **2,200** |

The **295 accepted states / 1,180 computed values** pass **5,310 physical checks**
and **146 mesh pairs**. Maximum deflection/heading mesh change is **0.04079%**;
maximum rebuilt full residual remains **9.99455e−13**. All 940 earlier scalar
comparison records are exactly unchanged.

The older twelve 5° negative-coupling failures have median error **249.161%**,
range **227.303–356.704%**. The four 1° failures have median **12.2094%**, range
**8.6983–15.7294%**. Five unresolved mesh conditions still account for twenty
outputs. The 904 finite unrun comparisons belong to the 10° and 15° sweeps.
AE-2 is not yet validated as a whole family.

## Audit and next work

The combined saved-file audit passes after preserving all original failed
executions, earlier declared retries, recovered complete states and the two
audited cold continuations. Each original comparison slot contributes at most
once. It freshly rehashes **1,989 files** and checks **2,049 path resolutions**.
No production solver code was changed. Browser/build checks remain held.

Next: extend coverage to the literal 10° sweeps on the same three models.
Keep the negative-coupling 16 m/s deformation error, 5° branch discrepancy
and unfinished executions open. Further convergence work should address the
actual iteration cost without fitting the archived output or loosening gates.

Setup follows Jan, **Part IV §3.2, pp. 8–12**, together with the original
models, shell drivers and ASWING sensor exports. The target remains the
documented ASWING results, distinct from experiment. The report's early-stall
discussion is relevant to negative coupling; it does not exempt those
comparisons. Exact historical startup settings and executable provenance remain
unresolved; this agreement does not establish that they were identical.
See the [authoritative reference index](aswing-authoritative-references.md).

Evidence: [full audit](../../artifacts/isae/ae2-beta1-positive-sweep-20261110/assessment.json),
[selected original jobs](../../artifacts/isae/ae2-beta1-positive-sweep-20261110/selection.json),
[execution receipts](../../artifacts/isae/ae2-beta1-positive-sweep-20261110/attempts.json),
[zero-speed accounting](../../artifacts/isae/ae2-beta1-positive-sweep-20261110/zero-records.json),
[reconciled report](../../artifacts/isae/ae2-beta1-positive-sweep-20261110/accepted-run/report.json).
