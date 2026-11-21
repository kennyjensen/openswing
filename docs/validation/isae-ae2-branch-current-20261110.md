# AE-2: the 17 m/s branch discrepancy

The [subsequent staged verification](isae-ae2-staged-inverse-20261110.md)
completes all three finer-grid inverse diagnostics without changing production
code or acceptance checks. Their 17 m/s discrepancy persists; the earlier
failed attempt and the primary six failures below remain retained.

Observed 2026-11-10 UTC. Four fresh fixed-speed states add **10 native passes**.
The current full-scope replay is now **34/2,200**: 40 values computed, six
failed comparisons, 2,064 finite comparisons unrun, and 96 unavailable native
values retained. No production equation, model property, default or acceptance
gate changed. The historical strict baseline and branch diagnostics remain
separate.

## Direct comparison on the registered meshes

The literal negatively coupled wing is tested at beta 5°, IAS 16 and 17 m/s,
with the same frozen-influence setup and independent cold-start policy as the
[initial current checkpoint](isae-ae2-current-20261110.md).

At **16 m/s**, all eight comparisons on nominal 80/160 meshes pass. Maximum
error is 4.025% in sensor flow angle; deflection error is 3.481% and heading
error 3.238% or less. At **17 m/s**, sensor speed passes on both meshes, but
deflection, heading and local flow angle have the opposite sign to the archive:

| Quantity at 17 m/s | Archived ASWING | OpenSwing, nominal 160 | Absolute relative error |
|---|---:|---:|---:|
| Sensor Earth Y (m) | +0.191155 | −0.248455748 | 229.976% |
| Heading (degrees) | +14.8018 | −18.8430885 | 227.303% |
| Sensor speed (m/s) | 16.9703 | 17.0008912 | 0.1803% |
| Sensor flow angle (degrees) | −11.6441 | +22.8019785 | 295.824% |

All four states pass the original full-equation, balance, clamp, source and
sensor checks. Their solve times are 4.33–10.07 seconds. The combined current
replay has **180 passing physical checks** and **10 passing mesh checks**.
Maximum fresh residual is 7.16e−13; maximum deflection/heading mesh change
over the full current sample is 0.03861%. The six native failures span
227.303–295.829%, median 229.975%. This is a branch disagreement, not a failure
to satisfy the equations at the accepted OpenSwing state.

## Inverse-speed diagnostic

To test the positive branch independently of fixed-speed Newton initialization,
the original archived tip-Y values were prescribed and airspeed solved as an
additional unknown. Material properties, geometry, section laws, wall, beta,
gravity and atmosphere were unchanged. A current cold full-load solution at
20 m/s supplied the seed. The production custom-equation solver retained its
complete tangent/rank and smoothness checks.

| Archived point | Prescribed Earth Y (m) | Solved speed, nominal 20 (m/s) | Speed difference | Heading difference |
|---|---:|---:|---:|---:|
| 17 m/s | +0.191155 | **18.966563** | **+11.568%** | −0.0133% |
| 18 m/s control | +0.218111 | 18.049824 | +0.2768% | +0.1554% |
| 19 m/s control | +0.190580 | 18.991455 | −0.0450% | +0.1606% |

The 17 m/s reference deflection and heading therefore correspond closely to a
computed positive-branch configuration near 19 m/s. The neighboring controls
recover their archived speeds within 0.277%. This strengthens the hypothesis
of a branch or archived-convergence issue; it does **not** prove that the
archived point is invalid, recover its original settings, establish uniqueness,
or exclude another equilibrium at 17 m/s.

![Inverse-speed diagnostic](../../artifacts/isae/ae2-inverse-speed-20261110/inverse-speed.png)

Five diagnostic states computed: both cold 20 m/s seeds and the three
nominal-20 inverse targets. All **69 physical checks** pass. The nominal-40
inverse control terminated with SIGKILL before saving a result; its two
dependent probes remain unrun. The process was reaped, with no retry. It had
15 CPU-second, 512 MiB address-space and 25-second elapsed limits; the signal
is consistent with the CPU cap, but its exact cause was not recorded. Thus
the inverse-speed result is **not yet established on a finer mesh**. No
diagnostic state adds primary native passes.

## Source interpretation and next work

Jan's **Part IV**, §3.2, pp. 8–12, Figure 3, remains authoritative. The literal
`[m15_02]_s_A5.sh` pairs every printed row with the commanded IAS and issues
one `XX` at line 54. The `t` column is the stack coordinate, not airspeed.
There is no recovered per-point convergence log or historical `.set` file.

Drela's original manual, **Computation of an operating point**, explains that
`X` can be repeated when the iteration limit is reached; **Option selection /
Iteration Limit** likewise describes repeating `X` or `XX`. Its example menu
shows an iteration limit of ten. That example is not proof of the historical
run's limit. A single `XX` and an output table do not independently establish
convergence of every archived point. Conversely, missing logs do not establish
nonconvergence. The [source review](../../artifacts/isae/ae2-inverse-speed-20261110/source-review.json)
retains exact local line locators and hashes.

Next, complete the inverse diagnostic's finer-mesh residual/tangent verification
as separate bounded stages, preserving every equation and acceptance check.
Continue the full current native sweep, keeping the six 17 m/s failures required.
Historical influence/atmosphere settings, other branches and stability remain
open; no property fit or branch selection by reference agreement is justified.
Browser/build testing remains held.

[Combined current assessment](../../artifacts/isae/ae2-branch-fixed-current-20261110/assessment.json) ·
[Fixed-speed evidence](../../artifacts/isae/ae2-branch-fixed-current-20261110/report.json) ·
[Inverse plan](../../artifacts/isae/ae2-inverse-speed-20261110/plan.json) ·
[Inverse assessment and retained failure](../../artifacts/isae/ae2-inverse-speed-20261110/assessment.json)
