# AE-2: completing the negative-coupling 16 m/s cases

Observed 2026-11-10 UTC. The current comparison advances from **920/2,200 to
924/2,200 at 5%**. Both previously incomplete 1°, 16 m/s cases now converge
with the original equations and load-stepping rules. Four newly available
comparisons pass and four fail. All **36 physical checks** pass; freshly
rebuilt residuals are **7.3280e−14** and **1.2941e−13**.

## Actual disagreement with ASWING

These are the original negative-coupling model and sensor channels. The
reference is the archived ASWING output, not the experimental curve.

| Channel | Archived ASWING | OpenSwing nominal 80 | OpenSwing nominal 160 | Relative error | At 5% |
|---|---:|---:|---:|---:|---|
| Earth Y, m | −0.187930 | −0.20427668 | −0.20427759 | 8.6983–8.6988% | Fail |
| Heading, degrees | −13.3859 | −15.491420 | −15.490162 | 15.7200–15.7294% | Fail |
| Sensor speed, m/s | 16.0104 | 16.005196 | 16.005199 | 0.03248–0.03250% | Pass |
| Sensor flow angle, degrees | 17.0859 | 17.062896 | 17.062017 | 0.13464–0.13978% | Pass |

The failed-value median is **12.2094%**. Mesh changes are only **0.00045%** in
deflection and **0.00813%** in heading. The discrepancy therefore persists
under the tested refinement; these results do not establish its cause.

![Original 1° references and current predictions](../../artifacts/isae/ae2-beta1-attempt-boundaries-20261110/beta1.png)

## Why the earlier jobs did not finish

The accepted-load checkpoint API allowed several expensive rejected attempts
inside one bounded job. Traces show repeated damped Newton iterations and
matrix refreshes, rather than an idle solver. Both 16 m/s meshes reached an
accepted 87.5% load before further work exceeded the execution budget. Fine
18 m/s reached 62.5% load and remains incomplete.

The diagnostic hook now yields after one completed rejected attempt, using
the last converged state and the next increment already selected by production.
It discards the failed trial, retains the rejection count, rechecks the unloaded
rank on restart, and retains the **1e−12 full residual gate**. It changes no
equation, airfoil property, geometry, branch seed, load increment or tolerance.
It is an execution aid in the validation scripts, not a new application default.
No reduction in total solve time is claimed.

| Mesh | Accepted load fractions after 87.5% | Additional rejected targets | Newton iterations after 87.5% |
|---|---|---|---:|
| Nominal 80 | 0.921875, 0.9921875, 1 | 1, 0.96875 | 93 |
| Nominal 160 | 0.8984375, 0.93359375, 0.986328125, 1 | 1, 0.96875, 0.921875 | 154 |

Four controls check the partitioning. The completed 15 m/s solves reproduce
the original full coordinates exactly on the fine mesh and within 8.882e−16
on the coarse mesh. Splitting the known 16 m/s rejection and subsequent
accepted step reproduces its saved coordinates exactly on the coarse mesh and
within 2.443e−15 on the fine mesh. All original failed executions remain saved.
The 37 diagnostic children are terminal and reaped: 35 successful jobs and two
retained failures from the earlier accepted-step-only attempt. Every numerical
worker uses one BLAS thread, 512 MiB, 15 hard CPU seconds and a 25-second
supervisor deadline.

## Accounting and verification

The independent chain audit checks original requests, every checkpoint
handoff, rejected-state rollback, source hashes, complete-state physical checks
and control parity. The primary collector then places each complete result
in its original comparison slot. Neither controls nor partial states add
comparisons. All four mismatches are retained alongside the four new passes.

The full saved-file audit passes, rehashing **1,209 files** and freshly checking
**1,267 path resolutions**. Fourteen targeted acceptance/cache tests pass,
including rejection of partial states, changed inputs, substituted sensor
values, failed physical checks and unreaped processes. Production solver
source is unchanged. Browser/build checks remain held.

| Current outcome | Scalar comparisons |
|---|---:|
| Pass at 5% | **924** |
| Computed mismatch | 16 |
| Unresolved execution output | 20 |
| Finite reference, comparison not yet run | 1,144 |
| Unavailable original reference | 96 |
| Required | **2,200** |

The **235 accepted states / 940 computed values** pass **4,230 physical checks**
and **116 mesh pairs**. Maximum mesh change remains 0.04078%. The negative-
coupling 1° subset is now **152/168**: four computed failures, four unresolved
fine-18 m/s outputs and eight unavailable references remain. Across all
registered 1° results, **376/380 computed values pass**; the median error is
0.42870% and the maximum is 15.7294%.

Next: finish the fine-18 m/s continuation, then extend positive-coupling 1°
coverage. Keep the 16 m/s deformation discrepancy and the older 5° branch
discrepancy open. The positive-coupling 1° series and all 10°/15° sweeps still
need coverage; partial progress is not whole-family validation.

## Reference interpretation

Jan, **Part IV §3.2, p. 10**, specifies the composite properties, ground plane,
cosine clustering and NACA0012 section parameters. It also reports early local
stall with negative bending–torsion coupling. That is a relevant mechanism to
investigate, not permission to discard the ASWING comparison or tune parameters.
Drela's steady description **§3.8** requires the beam decomposition to retain
the complete Newton equations; **§4.6** describes implicit circulation and
lagged weak geometry dependence. This work changes neither formulation.
See the [authoritative reference index](aswing-authoritative-references.md).

Evidence: [primary assessment](../../artifacts/isae/ae2-beta1-attempt-boundaries-20261110/primary-assessment.json),
[cold-chain audit](../../artifacts/isae/ae2-beta1-attempt-boundaries-20261110/assessment.json),
[attempt plan](../../artifacts/isae/ae2-beta1-attempt-boundaries-20261110/plan.json),
[original traces](../../artifacts/isae/ae2-beta1-cold-stages-20261110/plan.json).
