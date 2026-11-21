# AE-2: branch mesh check and four more original states

Observed 2026-11-10 UTC. The current comparison advances from **708/2,200 to
724/2,200 at 5%**. All sixteen new native comparisons pass. Separately, the
previously observed turn in the equilibrium curve persists on both nominal
80 and 160 meshes, with maximum compared-output change **0.01521%**. Production
equations, defaults, input models and acceptance tolerances are unchanged.

## Original native comparisons

The four new states use the original uncoupled wing at 1°, IAS 22 and 23 m/s,
on both meshes. These are independent cold starts, not continuation points or
fits to reference values. Errors against archived ASWING are:

| IAS (m/s) | Nominal mesh | Sensor Earth Y error | Heading error | Sensor speed error | Sensor flow-angle error | Passes |
|---:|---:|---:|---:|---:|---:|---:|
| 22 | 80 | 0.61661% | 0.54318% | 0.001733% | 1.94768% | 4/4 |
| 22 | 160 | 0.62097% | 0.55209% | 0.001732% | 1.94295% | 4/4 |
| 23 | 80 | 0.66766% | 0.59065% | 0.001592% | 1.89819% | 4/4 |
| 23 | 160 | 0.67326% | 0.60080% | 0.001592% | 1.89248% | 4/4 |

Three original workers finish normally. The fourth reaches its supervisor
deadline after writing a complete solution. Its original timeout remains
recorded. A separate restore of that exact saved state passes all eighteen
physical checks, with fresh full residual **9.971e−13**. No second solve or
changed request is used to complete that state's comparison. The independent
completion occupies the original four slots exactly once.

![Original 1° references and current predictions](../../artifacts/isae/ae2-branch-mesh-native-0052-20261110/beta1.png)

Black points show all finite archived references, including unrun conditions.
Gaps in predictions are retained. These plots compare documented ASWING outputs;
experimental curves and diagnostic branches are not substituted for them.

| Full AE-2 outcome | Scalar comparisons |
|---|---:|
| Pass at 5% | **724** |
| Computed mismatch | 12 |
| Unresolved execution output | 40 |
| Finite reference, comparison not yet run | 1,328 |
| Unavailable original reference | 96 |
| Total required | **2,200** |

The **184 accepted states / 736 computed values** pass **3,312 physical checks**.
All **89 compared mesh pairs** pass their 178 deflection/heading checks, with
maximum change **0.04078%**. Maximum full residual remains **9.995e−13**.
The overall computed median error is **0.35072%**. The twelve mismatches remain
in the negative-coupling 5° sweep at 17–19 m/s: median **249.161%**, range
**227.303–356.704%**, associated with opposite equilibrium branches.

All **176 computed 1° comparisons pass**, with median/max error
**0.37085% / 4.07235%**: 164 uncoupled and twelve negative-coupling outputs.
The original 1° plan has **52 terminal records and 110/162 records unrun**.
Its terminal 208 slots contain 176 passes, 24 unresolved execution outputs and
eight unavailable references. The positive-coupling 1° and all 10°/15° sweeps
remain unrun. Across accumulated execution, twenty original process failures
remain recorded; ten now also have independent saved-state verification and
ten remain unresolved. Subsets are not additional progress scopes.

## Does the sampled turn survive a mesh change?

The [previous study](isae-ae2-turning-branch-20261110.md) verified two different
positive-deflection equilibria at identical beta and IAS on nominal 160.
This follow-up uses the original nominal-80, 1°, 14 m/s equilibrium as its own
starting point; no state is interpolated from the fine mesh. Repeating that
control reproduces all sensor outputs exactly, with maximum normalized
coordinate difference **6.94e−18**.

The same complete coupled equations are then solved with sensor Earth Y
prescribed and beta as the extra unknown, at IAS 17 m/s. A declared 1% mesh
gate compares solved beta, heading, sensor speed and sensor flow angle.
Prescribed Y is excluded from independent mesh checks.

| Prescribed sensor Y (m) | Nominal-80 beta (degrees) | Nominal-160 beta (degrees) | Largest change among four compared outputs |
|---:|---:|---:|---:|
| 0.202 | 2.736646901 | 2.737030302 | 0.01401% |
| 0.210 | 2.713982494 | 2.714395342 | 0.01521% |

On both meshes beta decreases between these increasing deflections. The coarse
intermediate Y = 0.100 m point has beta = 0.985331034°, below both later points.
All **eight mesh checks pass**. The four coarse states pass **86 physical,
control, constraint and rank checks**, with maximum residual **2.158e−13**.
All twelve numerical stage children finish successfully and are reaped.

This supports a turning equilibrium relation on both tested meshes. It does
not locate an exact fold, establish stability or formal continuum convergence,
or identify historical ASWING's branch. These diagnostic conditions have no
paired native rows, so they add **zero native comparisons**. Their checks remain
separate from the primary totals above. The original 5° mismatch stays open.

## References and next work

The [authoritative source index](aswing-authoritative-references.md) and its
checksummed catalog govern the setup. Jan Part IV §3.2, pp. 8–12 and Figure 3
describe the three laminates, four incidence sweeps, early negative-coupling
stall and ASWING 5.96 results. Drela's steady §3.8 supplies the full coupled
Newton elimination framework. The diagnostic retains every physical equation;
neither source identifies sensor-deflection continuation as a historical default.

Next, complete remaining original sweeps and unresolved executions in bounded
serial jobs, while investigating whether the traced branch connects to the
original 5° reference conditions. The centered tangent and continuation code
remain diagnostic and require regression work before production promotion.
Browser/build tests remain held. All numerical children in this follow-up are
terminal and reaped; jobs use one BLAS thread and unchanged resource limits.

[Native saved-data audit](../../artifacts/isae/ae2-branch-mesh-native-0052-20261110/assessment.json) ·
[Frozen original execution](../../artifacts/isae/ae2-beta1-sweeps-current-20261110/snapshot-0052/report.json) ·
[Independent saved-state check](../../artifacts/isae/ae2-beta1-recovery-staged-0052-20261110/AE-2-b01-ias023-m160/report.json) ·
[Mesh plan](../../artifacts/isae/ae2-branch-mesh-20261110/plan.json) ·
[Mesh audit](../../artifacts/isae/ae2-branch-mesh-20261110/assessment.json) ·
[Coarse branch runner](../../scripts/probe_isae_ae2_coarse_branch.py) ·
[Mesh assessor](../../scripts/assess_isae_ae2_branch_mesh.py)
