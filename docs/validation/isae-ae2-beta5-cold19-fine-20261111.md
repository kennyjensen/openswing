# AE-2: completed 5°/19 m/s fine-grid condition

Observed 2026-11-11 UTC. AE-2 advances to **2,070/2,200 at 5%** after completing
the original negative-coupling 5°/19 m/s condition on nominal mesh160. Its sensor
speed passes; three outputs retain the opposite-deflection branch discrepancy.
All **2,088 earlier computed comparisons remain exactly unchanged**. Production
equations, defaults, model inputs and numerical gates are unchanged.

| Quantity | Archived ASWING | OpenSwing | Relative error | Result |
|---|---:|---:|---:|---|
| Tip Earth Y, m | +0.190580 | −0.32018287 | 268.004% | Fail |
| Heading, degrees | +14.7329 | −27.16058 | 284.353% | Fail |
| Sensor speed, m/s | 18.9791 | 18.95730 | 0.11486% | Pass |
| Sensor beta, degrees | −11.0481 | +28.36522 | 356.743% | Fail |

![Current five-degree native comparison](../../artifacts/isae/ae2-beta5-cold19-fine-20261111/complete-review/beta5.png)

## Bounded execution, unchanged solver

The [serial runner](../../scripts/run_isae_ae2_load_steps.py) uses the existing
production continuation and diagnostic worker. A same-model, same-mesh 15 m/s
control completed first: its entire saved equilibrium state and sensors match
the original ordinary cold solve exactly, and all **20 physical/parity checks**
pass. The original failed 19 m/s attempt remains retained.

The candidate required six accepted load boundaries:
**25%, 50%, 75%, 87.5%, 96.875%, 100%**. The production algorithm rejected two
larger full-load attempts, at residuals **0.002586** and **9.273e−9**, and reduced
the increment using its existing rules. It reached full load at
**8.61157e−13**, passing all **18 physical checks**. It required **183 Newton
iterations**, including **136 damped iterations**; splitting the execution does
not establish a solver speedup.

All **ten staged children**—four control and six candidate steps—completed and
were reaped. Maximum CPU/wall time was **14.19 /24.85 seconds**, with maximum
RSS **145,400 KiB**, below the unchanged **15 CPU /25 wall /512 MiB** limits.
Each job used one BLAS thread. Checkpoint requests, source hashes and original
inputs were checked before and after execution.

A separate final restore made **one fresh full-residual evaluation and no new
solve**, again passing all 18 checks at **8.61157e−13**. It completed in
**2.52 CPU /6.01 wall seconds**. The existing collector then rechecked the
complete original chain and filled its four original slots exactly once.
Neither control repeats nor intermediate boundaries add reference votes.

## Current complete sensor accounting

| Literal beta | Passes / required | Computed mismatches | Unresolved outputs | Unavailable references |
|---:|---:|---:|---:|---:|
| 1° | 616/648 | 4 | 4 | 24 |
| 5° | 550/600 | 18 | 8 | 24 |
| 10° | 488/512 | 0 | 0 | 24 |
| 15° | 416/440 | 0 | 0 | 24 |
| Total | **2,070/2,200** | **22** | **12** | **96** |

All 550 registered sensor records have terminal outcomes; no finite reference
remains unrun. The **523 accepted states /2,092 computed values** pass
**9,414 physical checks and 261 mesh pairs**. Maximum deflection/heading mesh
change remains **0.04079%**. The eighteen 5° failures have median error
**267.995%**, range **227.303–356.743%**. The four 1°/16 m/s failures retain
median **12.2094%**, range **8.6983–15.7294%**. The new mismatches were previously
unresolved; no earlier computed result changed.

The saved-file audit freshly verifies **5,065 digests and 5,133 path mappings**,
finishing in **38.53 CPU /155.12 wall seconds** at 214,876 KiB peak RSS. It
performs no physics calls. The 96 unavailable reference values and the primary
scope remain unchanged.

Three negative-coupling conditions remain incomplete: **1°/18 m/s on mesh160**
and **5°/20 m/s on both meshes**. These and the native branch discrepancies
remain open. Jan's **Part IV §3.2, pp. 8–12**, the original scripts and the
[authoritative reference policy](aswing-authoritative-references.md) continue
to govern the comparison. Exact historical startup settings and executable
provenance remain unknown. The [duplicate-export source finding](isae-ae2-supplemental-source-review-20261111.md)
and two additional unpaired models remain qualified. The whole family is not
declared validated; browser/build checks remain held.

Evidence: [execution summary](../../artifacts/isae/ae2-beta5-cold19-fine-20261111/execution-summary.json),
[chain audit](../../artifacts/isae/ae2-beta5-cold19-fine-20261111/recovery/assessment.json),
[complete assessment](../../artifacts/isae/ae2-beta5-cold19-fine-20261111/complete-review/assessment.json),
[summary](../../artifacts/isae/ae2-beta5-cold19-fine-20261111/complete-review/summary.json).
