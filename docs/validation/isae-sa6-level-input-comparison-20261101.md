# SA-6: five level-flight configurations match under a fixed input hypothesis

The later [complete roll/yaw table comparison](isae-sa6-span-native-20261101.md)
extends this qualified scope to all seven configurations and both regimes:
616/616 checks pass, maximum error 1.927%, with an explicit 10-inch span
reconstruction and retained failed alternatives. The five-model study below
remains unchanged; native setup and post-stall derivative errors remain unresolved.

The current solver matches **220/220** tabulated ASWING roll/yaw coefficients
within the existing 3% tolerance, with maximum error **0.885%**, for five
level-flight configurations under an explicit input hypothesis. The hypothesis
combines the control-gain ratios from the
[printed-response identities](isae-sa6-native-tables-20261101.md) with stall
strength 20, already examined in the earlier SA-6 raw-export comparison.

This supports an input explanation for these level-flight differences. It is
not authentication of the original ASWING settings, a production-default
change, or completion of the entire SA-6 family. The raw post-stall state-
derivative comparison and its pitch-rate failures remain separate.

## Complete comparison at strength 20

Each row covers both `Cl` and `Cn`, all eleven physical deflections from 4° to
44°, and both requested meshes, 64 and 128 intervals. Mandatory source breaks
produce 66 and 130 actual strips. Body incidence is 0°, speed 20 m/s, density
1.2256 kg/m³ and PG Mach zero. Influences remain current; at this zero-angle
rigid geometry, no frozen-influence substitution is needed.

| Model | Literal inputs, strength 20 | Identity-based inputs, strength 20 | Median / maximum hypothesis error |
|---|---:|---:|---:|
| 20b_15c | 44/44 | 44/44 | 0.355% / 0.818% |
| 20b_20c | 44/44 | 44/44 | 0.342% / 0.480% |
| 20b_25c | 4/44 | 44/44 | 0.342% / 0.642% |
| 20b_30c | 2/44 | 44/44 | 0.340% / 0.547% |
| 20b_35c | 44/44 | 44/44 | 0.345% / 0.884% |
| Total | 138/220 | 220/220 | Maximum 0.885% |

There are 82 gains and no losses in this strength-20 comparison. Failed
literal-input errors are typically 7.83% (maximum 8.88%) for `20b_25c`, and
10.40% (maximum 11.94%) for `20b_30c`.

All original `.asw` files are retained byte-for-byte. The hypothesis explicitly
rescales the F1 request so that effective gain magnitudes are 0.040, 0.045,
0.060, 0.055 and 0.070 for the five rows above. These values were fixed before
the new solves, from the prior exact printed identities and a 0.040 anchor.
The literal gains are 0.040, 0.045, 0.055, 0.061 and 0.071 respectively.
The span-file sign reversal is retained. Only input values change; neither
the section law nor the wake, force, moment, or discretization equations change.

The native pairs used to infer the gain ratios account for 68 of the 220
checks. The other **152/152** checks also match, with maximum error 0.884%.
This is a fixed source-data hypothesis checked across the full table, not a
blind validation study: the tables and previous predictions had already been
inspected.

## The default-strength pilot did not qualify for extension

The first pilot used production-default stall strength 40, controls 4°/44°,
both meshes, and all five same-geometry variants. Thirty-two cold calls cover
the literal and identity-based inputs, sharing only exactly identical requests.
Matches improve from **21/40 to 31/40**, with twelve gains and two losses.
The two losses are rolling moment for `20b_30c` at 44°, on both meshes. After
the gain change, failed rolling-moment errors remain about 3–5% low. The
predeclared no-loss gate fails, so the 144-call extension does not run.

A separate plan then uses the already examined strength-20 hypothesis with
the same inputs and pilot points. Its pilot gives **28/40 to 40/40**, with
twelve gains and no losses. This satisfies the same extension rule, so all
remaining deflections run. That study completes 176 cold calls, including
its 32-call pilot. No wrapper retries, fitted gains, or changed gates occur.

## Numerical and source verification

All **208 cold calls** complete serially with one BLAS thread. The first study
takes 20.93 seconds and the second 28.02 seconds in the worker timing scopes.
No browser, Vite server, packaging job or full build runs.

Every state independently reconstructs the control-modified section normals,
finite bound-vortex and semi-infinite wake velocities, nonlinear stall
residual, and strip forces/moments from the saved geometry and circulation.
The verifier imports no OpenSwing routines. Across both studies:

- Maximum reconstructed velocity discrepancy is 3.77e−14 of freestream speed.
- Maximum independently evaluated circulation residual is 4.25e−13.
- Maximum normalized force/moment discrepancy is below 9.59e−16.
- Maximum coefficient discrepancy is 6.11e−16.
- All original convergence and local-Mach validity gates pass.

A separate scalar audit checks the original MATLAB tokens, all 520 decisions
across the two studies and two input definitions, source hashes, task coverage,
extension decisions, and summed strip wrenches. It confirms the original
42 registered status rows are unchanged.

## Limits and remaining work

The gain anchor, original NODE spacing/count, stall strength and producing
run state are still not authenticated. The 0° body-incidence choice follows
the report's 4° level-flight wing incidence minus the decks' 4° built-in twist.
The default strength remains 40. These results are a qualified comparison
scope and add no registered default passes.

The other two level-flight span variants are outside this five-model study.
The literal 10-inch deck still has a known 15-inch control-span conflict.
Post-stall span-incidence ambiguity and the existing post-stall pitch-rate
discrepancy also remain unresolved. No claim of complete SA-6 reproduction follows.

Evidence: [strength-40 pilot plan](../../artifacts/isae/sa6-level-gain-pilot-20261101/plan.json),
[pilot result](../../artifacts/isae/sa6-level-gain-pilot-20261101/analysis.json),
[strength-20 plan](../../artifacts/isae/sa6-level-gain-strength20-20261101/plan.json),
[complete result](../../artifacts/isae/sa6-level-gain-strength20-20261101/analysis.json),
[independent field checker](../../artifacts/isae/sa6-level-gain-strength20-20261101/verify.py),
[scalar/source audit](../../artifacts/isae/sa6-level-gain-strength20-20261101/verification.json).
