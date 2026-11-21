# AE-2: finer-grid inverse-speed verification completed

Observed 2026-11-10 UTC. All three nominal-40 inverse-speed diagnostics now
pass their full physical, tangent-rank and smoothness checks. The 17 m/s
discrepancy persists: its archived tip deflection requires **18.952812 m/s**
on the computed positive branch, **11.487%** above the archived speed.
The grid change from nominal 20 is only **0.07255%** in required speed.

| Archived point | Prescribed tip Earth Y (m) | Required speed, nominal 20 | Required speed, nominal 40 | Fine speed error |
|---|---:|---:|---:|---:|
| 17 m/s | +0.191155 | 18.966563 | **18.952812** | **+11.487%** |
| 18 m/s control | +0.218111 | 18.049824 | 18.039670 | +0.2204% |
| 19 m/s control | +0.190580 | 18.991455 | 18.977654 | −0.1176% |

The neighboring controls recover airspeed within 0.221% and heading within
0.030%. At the disputed point, heading differs by 0.144%. Maximum change
between the two meshes over solved airspeed, heading and local sensor flow is
0.1872%. These are diagnostics with prescribed deflection, not independent
fixed-speed native passes.

![Two-grid inverse-speed comparison](../../artifacts/isae/ae2-staged-inverse-20261110/inverse-speed.png)

## Complete checks in small stages

The previous nominal-40 monolithic attempt ended with SIGKILL before producing
an accepted result. It remains intact. This new attempt checkpoints the
unchanged production corrector immediately before its final custom-tangent
verification and interrupts normal return. The candidate is explicitly
**pending verification**, and cannot seed another solve until accepted.

Each candidate then requires six serial tangent blocks and a final verification
process. Every one of the **546 columns** retains the original centered pair
and two extra one-sided residual evaluations. The same full-matrix rank test,
normalization, difference steps and smoothness limits apply. Duplicate, missing,
overlapping, wrong-shaped and nonfinite blocks are rejected.

The partitioned calculation reproduces the already accepted nominal-20
production check: the smoothness ratio is identical and the reciprocal rank
measure differs by 3.62e−14. **Eight focused tests pass**, including analytic
complete-tangent agreement and the original nonsmooth/singular rejection gates.

All three finer states pass **45 physical checks**, **1,638 complete tangent
columns** and **6,552 centered/one-sided perturbations**. Maximum fresh residual
is 1.815e−11. Full tangent reciprocal condition measures are
0.0004638–0.0005097, above the unchanged 1e−10 gate; the largest smoothness
ratio is 4.57e−6, below its unchanged limit of one.

All **25 stages** exited zero and were reaped. Peak recorded resource use was
**104.7 MiB** and **8.08 CPU seconds** per stage, within the original
512 MiB / 15 CPU-second limits. One stage's UTC timestamps differ from its
monotonic duration by 41.23 seconds; the audit preserves both and uses actual
resource receipts for CPU/memory statements. No whole-browser speedup is
claimed. No production source, physical input, default or tolerance changed.

## Reusing the matrices

The audit reuses each complete saved tangent to compute the local change in
airspeed with tip-Y target. This requires three linear solves and **zero new
physical residual evaluations**. Near the two almost-equal 17/19 m/s reference
deflections, the mean local derivative is −43.20256 (m/s)/m; the independently
computed equilibrium secant is −43.20244 (m/s)/m. They differ by **0.000274%**.
The largest linear-system defect is 2.85e−14.

This supports the local branch calculation. It does not establish global
uniqueness, dynamic stability, original ASWING settings, or that the archived
17 m/s point failed to converge. Jan Part IV §3.2 and the literal driver/output
pair remain the authoritative targets; the [preceding source review](isae-ae2-branch-current-20261110.md)
records the unresolved historical initialization and iteration evidence.

The primary AE-2 count remains **34/2,200**, including six failures at 17 m/s.
No inverse diagnostic is pooled into it. Next: resume the broader current
native sweeps in small serial jobs, retaining this branch discrepancy and
testing any different initialization as a separately declared comparison.
Browser/build tests remain held; the overall project goal remains incomplete.

[Plan](../../artifacts/isae/ae2-staged-inverse-20261110/plan.json) ·
[Complete audit and matrix sensitivities](../../artifacts/isae/ae2-staged-inverse-20261110/assessment.json) ·
[Control parity](../../artifacts/isae/ae2-staged-inverse-20261110/control.json) ·
[Execution receipts](../../artifacts/isae/ae2-staged-inverse-20261110/executions/)
