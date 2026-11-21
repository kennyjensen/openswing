# AE-2: uncoupled 1° sweep through 28 m/s

Observed 2026-11-10 UTC. The current score advances from **724/2,200 to
764/2,200 at 5%**. Ten new original states at IAS 24–28 m/s, on nominal 80/160
meshes, add **forty passing native comparisons**. All ten workers finish
normally. Production equations, defaults, source models and tolerances are
unchanged; this is additional validation coverage.

## Original comparisons

All new cases use the literal uncoupled model, original 1° incidence, and
independent cold starts. Maximum error across the two meshes at each speed:

| IAS (m/s) | Sensor Earth Y | Heading | Sensor speed | Sensor flow angle | Passes |
|---:|---:|---:|---:|---:|---:|
| 24 | 0.73891% | 0.66171% | 0.00180% | 1.83732% | 8/8 |
| 25 | 0.82519% | 0.74007% | 0.00229% | 1.76010% | 8/8 |
| 26 | 0.94426% | 0.84554% | 0.00221% | 1.65707% | 8/8 |
| 27 | 1.12287% | 1.00096% | 0.00267% | 1.50682% | 8/8 |
| 28 | 1.43603% | 1.26509% | 0.00311% | 1.25117% | 8/8 |

The new comparisons have median error **0.88910%**, maximum **1.83732%**.
Each state also passes the eighteen original physical checks. The ten numerical
workers use 3.682–5.615 CPU seconds each, with maximum peak RSS 130,292 KiB.
They retain one BLAS thread, 512 MiB address-space, 15 CPU-second and 25-second
supervisor limits. These are local worker timings, not browser performance.

![Original 1° references and current predictions](../../artifacts/isae/ae2-beta1-uncoupled-extension-20261110/beta1.png)

Every original uncoupled 1° row has now been attempted. That subset passes
**204/232**: twenty outputs from five earlier timed-out runs and eight unavailable
zero-speed reference values remain required. The unresolved runs are 4 m/s on
nominal 80, 18 and 19 m/s on nominal 160, and 21 m/s on both meshes. They have
no accepted complete saved state. The separate negative-coupling 17 m/s,
nominal-80 run also remains unresolved. These are execution gaps, not measured
reference mismatches.

Across the 1° sweeps, **all 216 computed values pass**, with median/max error
**0.39851% / 4.07235%**. The original 162-record plan now has 62 terminal records
and **100 unrun records**. Its terminal 248 slots contain 216 passes, 24 unresolved
execution outputs and eight unavailable values. Positive-coupling 1° and all
10°/15° sweeps remain unrun. Subsets are not separate progress scopes.

| Full AE-2 outcome | Scalar comparisons |
|---|---:|
| Pass at 5% | **764** |
| Computed mismatch | 12 |
| Unresolved execution output | 40 |
| Finite reference, comparison not yet run | 1,288 |
| Unavailable original reference | 96 |
| Total required | **2,200** |

The **194 accepted states / 776 computed values** pass **3,492 physical checks**.
All **94 compared mesh pairs** pass their 188 separate deflection/heading checks;
maximum change remains **0.04078%**. Maximum full residual is **9.995e−13**.
Overall computed median error is **0.35604%**. The twelve 5° negative-coupling
mismatches at 17–19 m/s remain: median **249.161%**, range **227.303–356.704%**.
Twenty original process failures remain recorded; ten have independent saved-state
completion, and ten remain unresolved. No prior execution receipt is replaced.

## Both roots satisfy a common physical operator

The [previous branch study](isae-ae2-turning-branch-20261110.md) found two
equilibria at beta 2.7143953415279096°, IAS 17 m/s, nominal 160. The
[mesh study](isae-ae2-branch-mesh-and-sweeps-20261110.md) then found the sampled
turn on nominal 80 too. This check tests a different possible explanation:
whether frozen influences or cache history change the equations between roots.

The source constructs frozen influences from the original undeformed geometry.
Following Drela's steady §4.6, p. 36, the selected K/F approximation freezes
influence geometry and wind alignment; circulation and local physical frames
remain variable. The exact historical K/F setting is not logged in the archive.

The new check removes `initial_state` from the otherwise identical requests and
constructs **one shared network**. It restores and evaluates the lower, upper,
lower and upper saved states in that order, without any equilibrium solve.
All four full residuals pass the unchanged 1e−12 gate:

| State | Sensor Earth Y (m) | Full residual |
|---|---:|---:|
| Lower deflection | 0.1992731115461498 | 3.224e−13 |
| Upper deflection | 0.2100000000000000 | 9.897e−15 |

All four sensor values match their original saved outputs exactly. Repeated
residual differences are zero. The frozen coefficient owner, geometry, Mach
transform, core settings, ground plane and sampled control-point coefficient
matrix remain identical. This rules out that cache/initial-guess explanation
for these two roots. It does not establish stability, identify historical
ASWING's selected branch, or resolve the original 5° mismatch. The diagnostic
adds **zero native votes** and its physical evaluations remain separate from
the primary checks. Its supervised child finishes normally in 0.913 CPU seconds.

Next, resolve the five remaining uncoupled 1° execution gaps using separate
verified attempts that preserve the original failures, continue the coupled
sweeps, and investigate the branch at the actual 5° reference conditions.
Browser/build checks remain held. All eleven numerical children in this
follow-up are terminal and reaped.

[Authoritative reference index](aswing-authoritative-references.md) ·
[Native audit](../../artifacts/isae/ae2-beta1-uncoupled-extension-20261110/assessment.json) ·
[Original frozen execution](../../artifacts/isae/ae2-beta1-sweeps-current-20261110/snapshot-0062/report.json) ·
[Common-operator check](../../artifacts/isae/ae2-common-operator-20261110/report.json) ·
[Reproducible checker](../../scripts/verify_isae_ae2_common_operator.py)
