# AE-3: current finite-aileron replay

Observed 2026-11-11T04:19:22.288176+00:00. AE-3 is the active focus after the tested
[AE-2 memory recovery](isae-ae2-sparse-recovery-20261111.md). All six archived
finite-control states complete on both existing meshes. The current comparison
is **50/725 at 5%**, with **72 computed values, 22 mismatches and
653 uncomputed targets**. This refresh adds no passes over the historical
50/725 tally. AE-3 remains open; no complete six-coefficient state matches.

All **348 physical checks pass**, including a freshly restored full residual,
force/moment balance, root clamp, literal model/setup identity and independent
coefficient normalization. Maximum fresh residual is **3.67561e-13**.
The rolling coefficient misses all twelve mesh/condition comparisons. Forty-eight
matches are zero-reference coefficients; two are CX at the last speed. These
passes do not establish aileron effectiveness or reversal agreement.

| Speed (m/s) | Archived Cl | OpenSwing nominal 80 | OpenSwing nominal 160 | Fine-grid error |
|---:|---:|---:|---:|---:|
| 27.0934 | -0.002056 | -0.001562894 | -0.001575255 | 23.38% |
| 38.5020 | -0.001957 | -0.001238636 | -0.001252539 | 36.00% |
| 43.0429 | -0.001878 | -0.001020419 | -0.001035107 | 44.88% |
| 47.2340 | -0.001759 | -0.000737837 | -0.000753259 | 57.18% |
| 50.9245 | -0.001578 | -0.000386569 | -0.000402473 | 74.49% |
| 59.4556 | 0.000450 | 0.001272751 | 0.001260742 | 180.16% |

Across both meshes, failed Cl comparisons have median **51.42%**
error (range **23.38–182.83%**). The ten failed CX
comparisons have median **51.04%** error (range
**36.84–61.35%**). These are relative errors against
the corresponding nonzero archived coefficient, not percentage points.
The largest adjacent Cl mesh change is **3.952%**.
Mesh changes remain descriptive: the old adapter has no independent mesh
acceptance gate, and this study does not claim continuum convergence.

![Archived and current AE-3 rolling and axial coefficients](../../artifacts/isae/ae3-current-20261111/coefficients.png)

The shaded band uses the larger of 5% and original print precision. Lines connect
the six archived/computed sample locations; they do not estimate a reversal speed.
The other four coefficient channels remain in the [complete CSV](../../artifacts/isae/ae3-current-20261111/coefficients.csv).

## Setup and source findings

The [authoritative index](aswing-authoritative-references.md) and checksummed
Jan Part IV / Drela steady sources were checked before running. Jan **Part IV
§3.3, pp. 10 and 13**, distinguishes the locked rolling-moment test from free
roll and original ASWING 5.96's fixed section slopes from ASWING-m's local
Reynolds-number lookup. Native original outputs, modified-code arrays and
experiment remain separate.

The original `Roll_rate.sh` commands the six archived speeds and `!!F1 1.0`,
which applies the finite control setting to every stacked point. The literal
`Straight_20O.asw` bytes, zero-scaled Weight rows, stiffnesses and section
properties are unchanged. The file uses lift/moment control slopes
**0.0581/−0.0102**; the report states **0.0581/−0.0107**. Other literal aileron-span
files also differ, as retained in the [source catalog](isae-ae3-reference.md).
The native export title is `Mowe_temp`, unlike the supplied model title. Neither
observation proves which input generated the export; neither licenses fitting
the current model to its results.

This refresh deliberately repeats the existing comparison setup: mounted,
zero incidence/sideslip/rates, Mach zero, density 1.2256, TAS equal to the
driver's IAS, updated aerodynamic influences, core ratio 0.25 and literal
reference dimensions. Nominal 80/160 cosine meshes have 82/162 actual intervals
because root and control discontinuities are mandatory. Exact historical node
arrays, startup constraints and K/F choice remain unknown. Updated influences
are an explicit comparison setting, not a change to the production frozen
default. A separate frozen-influence check is still needed.

## Complete scope and next work

| Required comparison group | Required slots | Computed slots |
|---|---:|---:|
| Six finite coefficients at six speeds, both meshes | 72 | 72 |
| Native stability and control derivatives | 252 | 0 |
| Native real/apparent mass, inertia and centroids | 252 | 0 |
| Normalized-rate report outputs | 36 | 0 |
| Embedded original-ASWING locked-control arrays | 43 | 0 |
| Embedded ASWING-m locked-control arrays | 43 | 0 |
| Embedded ASWING-m roll arrays | 27 | 0 |
| **Total** | **725** | **72** |

The 689 distinct source values and 36 deliberate mesh repeats are unchanged.
Five further models retain inventory records without invented targets. The 653
uncomputed slots include unavailable adapter capabilities and unresolved
generating setups; they are not discarded or filled with zeros. The selected
steady source policy still rejects the derivative option. The newer source
airflow/dynamic path needs a separate parity and observable audit before using
it to extend these comparisons.

Next, isolate rigid control effectiveness from elastic washout, compare the
documented control-slope inputs explicitly, and check frozen versus updated
influences without fitting. Use the archived local control derivatives as an
additional constraint once the matching source derivative path is established.
Keep the original finite-control baseline and every uncomputed target visible.

All twelve solver children ran serially with one BLAS thread and **512 MiB
address space /15 CPU seconds /25 wall seconds**, exited zero and were reaped.
Each used one cold solve plus one fresh restored residual, with no retries.
One aggregate source-only audit hit its 25-second alarm after writing nineteen
unavailable records. That failed audit is retained; completing the records in
small serial batches and reducing saved results required no solver reruns.
An initial reduction correctly hit the guard against applying the 5% policy
twice to an unavailable record; the corrected reducer validates its existing
policy and missing-value contract directly. Both failed audit attempts remain
linked in the assessment; no acceptance rule was relaxed.
Browser/build checks remain held. No solver or physical-input changes were
made during this AE-3 replay.

Evidence: [prospective plan](../../artifacts/isae/ae3-current-20261111/plan.json),
[complete assessment and process receipts](../../artifacts/isae/ae3-current-20261111/assessment.json),
[retained audit timeout](../../artifacts/isae/ae3-current-20261111/audit-attempt1-terminal.json),
[earlier comparison](isae-suite-ae3-20261027.md).
