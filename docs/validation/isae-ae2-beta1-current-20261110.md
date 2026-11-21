# AE-2: first 1° batch adds 60 native comparisons

Observed 2026-11-10 UTC. The independently audited current score rises from
**548/2,200 to 608/2,200 at 5%**. This comes from new original-input coverage;
production physics, defaults and numerical tolerances are unchanged. The full
three-layup, twelve-sweep denominator remains 2,200, including all 96 unavailable
native values. AE-2 and the overall project remain incomplete.

| New original 1° selection | Terminal records | Accepted physical states | Native matches / required slots in terminal records |
|---|---:|---:|---:|
| Uncoupled, IAS 0–9 m/s, both meshes | 20 | 15 | **60/80** |

The 80 slots contain 60 passes, 12 outputs from three deadline failures, and eight
unavailable zero-speed values. The full 1° plan contains 162 records: 156 numerical
jobs and six original all-NaN zero-speed records. **142 records remain unrun in
that plan.** Other layups have no new 1° predictions yet. This batch is not an
additional independent progress scope.

All 60 computed new values pass. Median error is **0.30365%**, maximum
**2.25212%**. All **270 new physical checks** pass, including fresh restored
residuals, force/moment balance, clamp conditions, sensor reconstruction and load
summation. Maximum new fresh residual is **7.239e−13**. All seven newly completed
mesh pairs pass the original deflection/heading mesh gates.

![1° native curves and current predictions, with gaps preserved](../../artifacts/isae/ae2-beta1-sweeps-current-20261110/curves-0020.png)

All finite native points are shown, including speeds and layups not yet run.
Missing predictions and failed mesh points remain absent; they are not filled
by interpolation or by a different solver setting.

## Full current accounting

**608 passes + 12 computed mismatches + 28 failed-run outputs + 1,456 finite
unrun comparisons + 96 unavailable reference values = 2,200.**

The accumulated current runs contain **155 accepted states / 620 computed
values**, **2,790 passing physical checks**, and **76 completed mesh pairs**
(152 deflection/heading checks). Maximum mesh change remains **0.04078%** and
maximum full residual remains **9.995e−13**. The existing twelve negative-coupling
5° mismatches remain, with median error **249.161%**, range
**227.303–356.704%**. No new computed native mismatch was found in this batch.
No timeout or partially verified state contributes a pass.

## Deadline failures and their evidence

Three new original jobs hit the 25-second supervisor deadline:

| Original job | Saved evidence at termination | Primary outcome |
|---|---|---|
| 3 m/s, nominal 160 | Converged result and worker report; solve-only time 1.645 s, fresh residual 2.292e−13, 18 physical checks pass; suite reporting incomplete | Retained timeout; four outputs unresolved |
| 4 m/s, nominal 80 | Worker-start marker; no completed physical result | Retained timeout; four outputs unresolved |
| 4 m/s, nominal 160 | Converged result at residual 4.150e−13; physical verification/report incomplete | Retained timeout; four outputs unresolved |

The first failure establishes that post-solve work can consume the remaining
budget; it does not identify the exact active instruction at termination or
explain every timeout. The 4 m/s fine result does not carry a completed physical
verification report. None of these processes was restarted or converted into a
successful suite run. Independent completion of the missing checks would be
required before reconsidering those outputs.

All **18 numerical subprocesses** are terminal and reaped: 15 exit zero and
three are terminated by the supervisor. Two unavailable rows are validated
without starting a solver. Numerical children retain one BLAS thread, **512 MiB,
15 CPU seconds and the 25-second supervisor deadline**. A live `/proc` receipt
verifies the inherited limits and four single-thread environment variables.
Successful solve-only timings range from **0.591 to 1.979 seconds**, median
**1.244 seconds**; these exclude startup, source verification and reporting and
are not whole-browser timings.

## Pinned batches and source interpretation

A preceding coordinator invocation exited 137 while rescanning the complete
source catalog, before starting any numerical worker. Its exact kill cause was
not recorded; that metadata process had inherited the same 15 CPU-second and
512 MiB limits. The failed coordinator and the absence of started jobs are
recorded separately from case outcomes.

The new `execute_isae_pinned_batch.py` coordinator loads the already verified
plan and checks its source-code pins, reuses only complete terminal receipts,
rejects incomplete job folders, and calls the original suite execution/report
functions. Each numerical child receives the same caps at process creation.
This avoids repeating the unrelated full catalog scan for every small batch;
it does not bypass any numerical worker, canonical input or physical check.
Two serial batches of four and sixteen records have completed. Their receipts
pin the coordinator script and plan. No production module was edited.

The current result is frozen in **snapshot-0020/** before publication, so later
batches can update the working report without rewriting this observation's
inputs. The saved-only assessor independently reconstructs the complete original
AE-2 scope, verifies current source pins and disjoint job identities, and combines
only the three preceding current runs with this snapshot. It makes no solver or
physical-residual calls and retains original-source ambiguities.

The authoritative reference index and checksummed Part IV PDF/text were
consulted. **Figure 3 on PDF/printed p. 12** was visually inspected: its legends
show **1°, 5°, 10° and 15°**, agreeing with the literal `!B` commands. The earlier
suggestion to run 7° was a planning error from neighboring AE-1 material, not
an AE-2 source conflict. The vertical-wing scripts command beta with alpha zero;
that body-axis convention is retained rather than relabeling the request.
Jan **Part IV §3.2, pp. 8–12** continues to govern the model and ASWING 5.96
reference. The unchanged 81/161-interval meshes are not asserted identical to
the report's original 40-node arrays. Sensor, atmosphere, frozen-influence and
historical initialization qualifications remain as recorded in the registration.

Next: continue this pinned 1° plan at uncoupled IAS 10 m/s, then the two coupled
layups. Preserve the three new deadline failures and inspect reporting overhead
before attempting any recovery. The separate correction-merit experiment remains
unpromoted, and all 10°/15° sweeps remain required. Browser/build tests stay held.

[Independent full-scope assessment](../../artifacts/isae/ae2-beta1-sweeps-current-20261110/assessment-0020.json) ·
[Immutable observation snapshot](../../artifacts/isae/ae2-beta1-sweeps-current-20261110/snapshot-0020/report.json) ·
[Current plan](../../artifacts/isae/ae2-beta1-sweeps-current-20261110/plan.json) ·
[Source review](../../artifacts/isae/ae2-beta1-sweeps-current-20261110/source-review.json) ·
[Live resource check](../../artifacts/isae/ae2-beta1-sweeps-current-20261110/live-resource-check.json)
