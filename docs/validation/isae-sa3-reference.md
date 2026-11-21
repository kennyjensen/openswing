# SA-3: complete archived-output comparison

This report retains the earlier kernel and results. See the [corrected-arc
rerun](isae-sa3-accurate-arc.md) for the current production source.

SA-3 has a source-pinned `physical-breaks-v1` comparison of all seven predicted outputs across its full 22-row archived ASWING polar. **Reference reproduction remains incomplete:** all 66 numerical states pass, but none of the 154 finest-mesh output values agrees within half its last printed unit. Experimental agreement is not an acceptance condition.

The original model is unchanged. The run uses each exact `!A` command, from 0.01739130434782643° to 10.017391304347827°, at commanded IAS 89.4 m/s. Assigned true speed is 89.4 m/s with declared density 1.2256 kg/m³, updated influences and fixed PG Mach zero. The archived script toggles K/F once; its startup value, PG setting and ambient history are not recovered. The script requests 100 ASWING **nodes**; this comparison uses 100, 200 and 400 OpenSwing cosine **intervals**, without claiming identical original node locations, endpoint conventions or spacing. The archived output alpha is rounded, so the earlier verifier's rounded-alpha inputs have been replaced by the exact source commands.

Each mesh contains 22 independent cold rigid solves and 22 fresh prescribed-Gamma residual evaluations: 66 of each overall. Maximum fresh normalized residual is 1.221e-14; maximum strip-force/moment normalization discrepancy is 1.475e-16. Fresh outputs match their solved counterparts exactly. The independent saved-data audit passes 8,528 checks, including all raw residual arrays, strip force/couple sums, reference maps, 462 output differences and 308 mesh comparisons. Native public solves total 15.981 s; the sequential batch took 42.701 s. These checks establish numerical consistency within the declared model, not archived agreement.

At 400 intervals, errors relative to the 22 archived values are:

| Output | Unit | RMSE | Maximum absolute difference |
|---|---|---:|---:|
| Lift | N | 1.0037574 | 1.385238 |
| Drag | N | 1.0147178 | 2.2154846 |
| CL | dimensionless | 0.00034334467 | 0.00047456396 |
| CD | dimensionless | 0.00034729876 | 0.00075838199 |
| CDi | dimensionless | 3.9103524e-07 | 6.6244882e-07 |
| CM | dimensionless | 1.3764639e-05 | 2.286647e-05 |
| efficiency | dimensionless | 0.0022052561 | 0.0023223154 |

The printed-precision criterion is a source-resolution diagnostic, not a fitted engineering tolerance. All 22 complete rows remain outside it. Dimensional lift/drag use the original reference area; CM uses the original zero moment reference. Span efficiency uses Trefftz CLi/CYi and CDi, not the printed total CL.

The predeclared mesh criterion is 1% relative successive-mesh change, divided by the absolute finer value with no floor. **286/308 checks pass.** From 100→200, all 22 CM checks fail (2.8032–3.1761%); the other six channels pass at every incidence. From 200→400, all 154 checks pass; CM remains the largest change (0.6553–0.7791%). Meeting this scalar criterion does not establish asymptotic or local-flow convergence.

A separate saved-only force decomposition passes 1,178 checks. At the last incidence and 400 intervals, CD exceeds the archive by 0.000758382. The near-field-minus-Trefftz contribution is 0.000694684, the Trefftz-minus-archive contribution is 0.000000536086, and the profile-minus-archived-remainder contribution is 0.000063162. The inner 90% of semispan contributes about 0.000638 to the near/far difference, persisting under refinement. Replacing the saved integration vector by endpoint displacement while holding circulation and velocity fixed slightly worsens CD agreement; it does not explain the main gap. The supported force and moment identities remain internally consistent. This diagnostic establishes no incorrect force formula and does not justify replacing total drag with a Trefftz expression. Its initial pressure-only assumption failure is retained; the corrected decomposition includes the documented smooth leakage contribution.

**Local tip-flow qualification:** at the last incidence, the maximum section-normal speed grows from 193.78 to 255.21 to 332.27 m/s on the three meshes; local normal Mach grows from 0.56959 to 0.75016 to 0.97667 near the zero-chord tip. The section Mach uses atmospheric sound speed independently of PG Mach. This near-sonic, refinement-sensitive behavior limits physical and continuum interpretation, although all recorded numerical gates pass at the finer pair. It does not by itself explain the persistent inner-span drag term.

One additional built-browser/Pyodide solve at 400 intervals and the last incidence passes 352 checks offline after startup. It matches the native result under the declared 2e-8 absolute/relative comparison, excluding evaluation counters, and restores the downloaded project result byte-exactly without another solve. Solve time is 6.8486 s and total browser-check time 51.48 s. The first launch failed on missing `libnspr4` before any solve; that environment failure remains recorded. This platform replay is separate from the 66 native states and does not establish ASWING parity.

The next discriminating check is a single saved-Gamma force-point capture separating bound-segment and trailing-leg induced velocities, while retaining endpoints, own-bound exclusion and force-point placement. Compare these with the saved half-Trefftz velocity before proposing any correction. Historical settings and original discretization remain explicit unknowns; no property fitting or default change is justified by the present evidence.

[Comparison plots](isae-sa3-reference-comparison.png) ·
[Summary and provenance](isae-sa3-reference-summary.json) ·
[All values](isae-sa3-reference-comparison.csv) ·
[Full comparison](isae-sa3-reference-comparison.json) ·
[Force diagnostic](isae-sa3-reference-forces.md) ·
[Browser report](isae-sa3-reference-browser.json) ·
[Importable project](../../examples/isae-sa3-reference-project.json) ·
[Raw evidence archive](isae-sa3-reference-20261025-evidence.zip)

No production kernel, model properties or application defaults changed.
The full project remains incomplete.

## Subsequent velocity diagnosis

The [saved-state velocity study](isae-sa3-velocity.md) separates bound and
trailing contributions and independently checks the sampled kernels. A tested
JVL curvature analogue is too small and increases drag. No solver change or
ASWING match follows; the original full-polar results above remain unchanged.
