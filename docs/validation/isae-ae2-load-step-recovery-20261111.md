# AE-2: accepted cold-continuation result at 5° and 18 m/s

Observed 2026-11-11 UTC. AE-2 advances to **2,069/2,200 at 5%**. The existing
nominal-160 negative-coupling solution at 5°/18 m/s now completes its four
original comparison slots after independent verification and collector support.
One value passes; three retain the opposite-branch discrepancy. All **2,084
previously computed values and their comparison results are exactly unchanged**.

| Quantity | Archived ASWING | OpenSwing | Relative error | Result |
|---|---:|---:|---:|---|
| Tip Earth Y, m | +0.218111 | −0.28175235 | 229.178% | Fail |
| Heading, degrees | +16.7860 | −21.87831 | 230.337% | Fail |
| Sensor speed, m/s | 17.9747 | 17.98541 | 0.05956% | Pass |
| Sensor beta, degrees | −13.4885 | +24.92066 | 284.755% | Fail |

![Current 5-degree sensor comparison](../../artifacts/isae/ae2-load-step-recovery-20261111/complete-review/beta5.png)

## What changed

The [collector extension](../../scripts/isae_ae2_load_step_acceptance.py) supports
the earlier [accepted-load-step diagnostic](isae-ae2-cold-stages-20261110.md).
It checks the entire cold chain from the original input: each request must
contain exactly the preceding checkpoint, with no alternate initial guess,
changed condition or modified numerical setting. Every stage must have a
successful, reaped process and a valid physical residual. The staged control
matches the ordinary cold result's entire saved equilibrium state and sensors
exactly. Original failure and diagnostic receipts remain intact.

A new independent restore performs **one full residual evaluation and no
equilibrium solve**, passing all **18 physical checks** at residual
**3.62997e−14**. It takes **4.33 CPU seconds / 16.84 wall seconds**, under the
unchanged 15 CPU /25 wall /512 MiB limits with one BLAS thread. The earlier
stages' 30-second outer-supervisor receipts are retained with their original
limits; they are not relabeled as current-limit runs.

Six acceptance tests pass, including rejection of changed inputs, substituted
checkpoints, skipped steps, incomplete results, failed processes and invalid
residuals. Production solver equations, defaults, source models and reference
values are unchanged. The collector fills each original slot once and keeps
reference agreement separate from physical convergence.

## Current accounting

| Literal beta | Passes / required | Computed mismatches | Unresolved outputs | Unavailable references |
|---:|---:|---:|---:|---:|
| 1° | 616/648 | 4 | 4 | 24 |
| 5° | 549/600 | 15 | 12 | 24 |
| 10° | 488/512 | 0 | 0 | 24 |
| 15° | 416/440 | 0 | 0 | 24 |
| Total | **2,069/2,200** | **19** | **16** | **96** |

All 550 registered records have terminal outcomes, with no finite reference
unrun. The **522 accepted states /2,088 computed values** pass **9,396 physical
checks** and **260 mesh pairs**; maximum deflection/heading mesh change remains
**0.04079%**. The fifteen 5° failures have median error **230.337%**, range
**227.303–356.704%**. The four 1°/16 m/s failures retain median **12.2094%**,
range **8.6983–15.7294%**. More mismatches are now measured because a previously
unresolved state has been verified; earlier results have not regressed.

The complete saved-file audit rechecks **4,992 file digests** and **5,059 path
mappings**, finishing in **46.86 CPU /260.13 wall seconds**, with 215,368 KiB
peak RSS under the existing metadata limits. It imports no production solver
and makes no physics calls.

Four negatively coupled conditions remain incomplete: **1°/18 m/s on mesh160,
5°/19 m/s on mesh160, and 5°/20 m/s on both meshes**. These and the native branch
discrepancies remain open. The [source review](isae-ae2-supplemental-source-review-20261111.md)
establishes that the supposed span export is a duplicate; two other input
variants remain unpaired. Historical startup settings and executable provenance
remain qualified under the [authoritative reference policy](aswing-authoritative-references.md).
AE-2 is not declared fully validated. Browser/build checks remain held.

Evidence: [complete assessment](../../artifacts/isae/ae2-load-step-recovery-20261111/complete-review/assessment.json),
[chain audit](../../artifacts/isae/ae2-load-step-recovery-20261111/assessment.json),
[fresh verification](../../artifacts/isae/ae2-load-step-recovery-20261111/AE-2-m15_02-b05-ias018-m160/report.json).
