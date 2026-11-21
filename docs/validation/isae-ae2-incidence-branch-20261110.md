# AE-2: the negative-coupling branch matches at 1°

Observed 2026-11-10 UTC. The current score advances from **680/2,200 to
708/2,200 at 5%**. All **28 newly accepted comparisons pass**, with median
error **0.54261%** and maximum **4.07235%**. No production equation, model
property, default or numerical tolerance changed.

The most useful new result is the original negatively coupled wing at **1°,
17 m/s, nominal 160**. OpenSwing reaches the positive-deflection branch and
matches all four archived ASWING outputs. This contrasts with the existing 5°
comparison at the same speed, where independent cold starts reach a negative
branch. The 1° result passed a fresh independent restore and all 18 physical
checks; its maximum full residual is **2.053e−13**.

| Original 1°, 17 m/s output | Archived ASWING | OpenSwing, nominal 160 | Error |
|---|---:|---:|---:|
| Sensor Earth Y (m) | +0.102923 | +0.101170432 | 1.70280% |
| Heading (degrees) | +7.97538 | +7.83928684 | 1.70642% |
| Sensor speed (m/s) | 16.9978 | 16.9982798 | 0.00282% |
| Sensor flow angle (degrees) | −7.59521 | −7.28590647 | 4.07235% |

At **14 m/s and 1°**, both nominal 80/160 meshes also pass all eight native
comparisons. Deflection errors are 1.689–1.691%; heading errors are
1.657–1.665%. The 17 m/s coarse case remains unresolved, so mesh convergence
of that particular positive-branch point has not yet been established.

These results establish that the negative-coupling model can reproduce the
archived positive branch at one incidence. They do not resolve the 5° mismatch,
prove uniqueness or stability, or recover the original iteration history.
The earlier [inverse-speed study](isae-ae2-branch-current-20261110.md) remains
relevant: the archived 5°, 17 m/s tip displacement corresponded to a computed
positive-branch configuration near 19 m/s, while neighboring inverse controls
were close. The new 1° state provides an independently checked starting point
for a diagnostic continuation in incidence.

![Original 1° references and current predictions](../../artifacts/isae/ae2-beta1-recovery-staged-0048-20261110/curves-visible.png)

## Current accounting

| Full AE-2 outcome | Scalar comparisons |
|---|---:|
| Pass at 5% | **708** |
| Computed mismatch | 12 |
| Unresolved execution output | 40 |
| Finite reference, comparison not yet run | 1,344 |
| Unavailable original reference | 96 |
| Total required | **2,200** |

There are **180 accepted physical states / 720 computed values**, with
**3,240 passing physical checks** and **87 passing mesh pairs** (174 separate
deflection/heading checks). Maximum mesh change remains **0.04078%** and maximum
full residual remains **9.995e−13**. The twelve 5° negative-coupling mismatches
are unchanged: median error **249.161%**, range **227.303–356.704%**.

All **160 computed 1° values pass**: 148 for the uncoupled wing and twelve for
the negatively coupled wing. Their median/max errors are **0.36380% / 4.07235%**.
The 1° plan has 48 terminal records and **114/162 records unrun**. Its terminal
192 slots contain 160 passes, 24 unresolved execution outputs and eight
unavailable zero-speed values. The positive-coupling 1° sweep and all 10°/15°
sweeps remain unrun. These subsets do not add independent progress scopes.

## Execution and verification

Twelve new original jobs were attempted. The uncoupled 18–21 m/s batch had
one normal completion and seven deadline failures. The four selected coupled
jobs had two normal completions at 14 m/s and two deadline failures at 17 m/s.
Four completed saved solutions were independently checked without another
equilibrium solve: uncoupled 18/19/20 m/s coarse, and coupled 17 m/s fine.
All four rechecks passed their 18 physical checks. No saved solution exists
for the other new failures; they remain unresolved.

Across the accumulated runs, nineteen original process failures are retained.
Nine also have separate successful saved-state verification receipts; ten
remain unresolved. A deadline failure alone does not establish failure of the
physical equations. The accepted comparisons use only the original requests,
unchanged current source, converged full-load states and completed checks.

The new `execute_isae_ae2_staged.py` coordinator puts canonical input preparation
and final reporting in the parent. It calls the **unchanged original physical
worker** in a supervised child: one cold solve, one fresh restored residual and
the same checks. Source verification remains mandatory before and after.
Each numerical child retains one BLAS thread, 512 MiB address-space limit,
15 CPU seconds and a 25-second deadline. Existing job folders are never retried.

For the two completed 14 m/s jobs, numerical-worker wall times were **7.710 s**
and **23.860 s**, with **3.796 s** and **6.494 s** CPU time. Input preparation
took 5.807/9.478 s and final collection 2.946/5.073 s. Keeping that metadata
outside the child deadline allows completed numerical work to be reported.
This is not a browser speed benchmark or a claim that all timeouts are fixed:
both 17 m/s children still timed out, and only the fine one saved a solution.

Two focused unit tests pass, including parity with a retained original adapter
result and ten adverse acceptance scenarios. The saved-only full-scope audit
also passes, independently checking the staged provenance and both sets of
saved-state completions. It imports no production solver and makes no physical
calls. All numerical children and verification children are terminal and reaped.

## Reference interpretation and next work

The [authoritative index](aswing-authoritative-references.md) and checksummed
catalog govern the comparison. Jan Part IV §3.2, pp. 8–12, Figure 3 describes
the three laminates and notes that negative bending/torsion coupling can cause
local stall even at low root incidence. That discussion concerns comparison
with experiment; it does not justify discarding an archived native comparison.
The original 1°/5°/10°/15° commands, model bytes, sensor definitions, atmosphere
and frozen-influence settings remain as registered.

Next: use the verified 1°, 17 m/s positive-branch state for a separate incidence
continuation toward 5°, checking every accepted step. Such a diagnostic must
not replace the original cold-start comparisons or select a branch by agreement
with the reference. Continue the remaining original sweeps and resolve missing
executions. Browser/build testing remains held; AE-2 is not yet validated.

[Full assessment](../../artifacts/isae/ae2-beta1-recovery-staged-0048-20261110/assessment.json) ·
[Immutable original-run snapshot](../../artifacts/isae/ae2-beta1-sweeps-current-20261110/snapshot-0048/report.json) ·
[New independent verification plan](../../artifacts/isae/ae2-beta1-recovery-staged-0048-20261110/plan.json) ·
[Previous observation](isae-ae2-beta1-verified-20261110.md)
