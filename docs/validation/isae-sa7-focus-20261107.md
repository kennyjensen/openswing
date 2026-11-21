# Current OpenSwing against the documented SA-7 case

2026-11-07. **682/812 checks pass at 5%** using the aircraft geometry in the
ISAE report and the unchanged archived ASWING results. This is the selected
SA-7 progress scope. All 116 operating-point/mesh jobs are numerically valid;
passing the complete family is still unresolved.

| Documented aircraft | Passing checks | Remaining discrepancy |
|---|---:|---|
| Complete tandem aircraft | 406/406 | None above the current 5% allowance |
| Isolated fore wing | 276/406 | Drag/CD, low-lift condition, post-stall CDi |
| Combined, each target counted once per mesh | **682/812** | **130 failed checks** |

These are 406 distinct native output cells compared on two meshes, not 812
independent experimental cases. The full-aircraft results reuse the completed
[fresh SA rerun](isae-sa-rerun-20261107.md). All 58 fore-wing jobs were rerun
with current OpenSwing in this study. No aerodynamic equation, production
setting, native output or acceptance tolerance changed.

## Which aircraft input is being used?

Earlier notes called this the “historical model.” That means an original
**aircraft `.asw` input**, not an old OpenSwing solver or different mathematics.
The [ISAE report](../../.reference/isae-validation/reports/Experimental_validation_of_ASWING_Part_1_Aerodynamics_V4.txt)
specifies a **1.29 m span and 0.22 m chord** for SA-7's fore wing (lines 2189–2191).
The [original fore-wing input](../../artifacts/isae/sa7-drag-source-audit-20261028/history-http/earliest-Tandem_GAW2_L163_G05_Fore_Only.asw)
has those dimensions. The later file under the same name has a **9.144 m span
and 0.3048 m chord**, while its adjacent driver and output table are unchanged.

The retained [source-history audit](../../artifacts/isae/sa7-drag-source-audit-20261028/history.json)
authenticates the original model, driver and table in public commit
`f745fb40b308d85a2a99e039665457177686a9bd`. The current comparison uses those
original aircraft dimensions, without editing either model or any reference
value. The producing executable and exact startup settings remain unverified.
The report discusses total-aircraft drag; the additional fore-only drag
columns in the repository remain included, including their negative values.

The previous **406/812** score paired the later, different fore-wing input
with the old results. It is retained as a source-mismatch diagnostic, rather
than the primary measure of reproducing the documented case. Selecting the
documented geometry changes the displayed count by 276; **this is an input
pairing correction, not a new solver accuracy gain**. The same 812 target
identities and denominators are retained. Alternative predictions are not added
to those totals. The existing generic registry still preserves the literal
latest files; its explicit `sa7-fore-f745fb40` source-pairing option provides
the original fore-wing input used here.

## Remaining fore-wing failures

| Output | Passing checks | Failed-value error |
|---|---:|---|
| Lift | 56/58 | 9.49% at −6° only |
| CL | 56/58 | 9.49% at −6° only; absolute CL difference 0.000410 |
| Drag | 0/58 | Median 150.46%; minimum 15.95% |
| CD | 0/58 | Median 150.46%; minimum 15.95% |
| CDi | 48/58 | 5.19–6.10% at 19°, 20°, 21°, 23°, 24° |
| CM | 58/58 | All within 5% |
| Span efficiency | 58/58 | All within 5% |

All 29 archived fore-wing Drag/CD rows fail on both meshes. Twenty-one rows,
starting at 3°, have negative archived Drag and CD. Relative error reaches
about 29,434% near an almost-zero reference drag; this is why the median and
the signed curves are more useful than that maximum alone. At 10°, for example,
archived CD is **−0.0717415**, while current OpenSwing gives **+0.0462866**.
The cause remains unresolved; no sign correction or reference replacement is
justified. The 14 failures outside Drag/CD are listed individually in the
[verification](../../artifacts/isae/sa7-focus-20261107/verification.json).

![Current OpenSwing against archived SA-7 fore-wing outputs](../../artifacts/isae/sa7-focus-20261107/documented-fore-comparison.svg)

## Driver settings and verification

Both original SA-7 drivers enter OPER/K and toggle `F` once. The ASWING
[guide](../../.reference/aswing_doc.txt) shows frozen matrices enabled in its
default menu (line 2244), describes `F` as the fast/slow toggle (2293–2313), and
specifically mentions nearby canard/wake interaction as a reason for the slow,
wind-aligned treatment. Therefore these tests explicitly use evolving
influences while new unspecified OpenSwing analyses retain the frozen default.
This follows the supplied driver under the documented startup assumption.

Eight separate frozen-setting pilots at −6°, 3°, 10° and 24° produce zero
additional matches and lose 15 existing matches. Fore-wing passes fall from
17/28 to 10/28; full-aircraft passes fall from 28/28 to 20/28. No sampled
fore-wing Drag/CD value is recovered. The predeclared extension condition
fails, so no further frozen sweep is justified. These pilots add no targets or
passes to the main comparison.

The 66 new cold solves finish in six small serial batches, all with one BLAS
thread and successful process exits. Total batch runtime is 98.81 seconds;
the largest circulation residual is **2.15e−13**, below the unchanged 1e−8
gate. Independent rational arithmetic checks all 462 fresh comparison
decisions and all 812 selected primary decisions. Fresh fore-wing outputs
match earlier same-setting calculations within **2.75e−15** on the normalized
comparison scale. Thus the refreshed numbers do not imply a new algorithmic
improvement. Two report-reader errors were corrected without rerunning any
solver: unwrapping nested result records and excluding unfinished unrelated
families. Premature verification attempts produced no result files.

Next investigate the unexplained fore-wing force/output disagreement and the
14 remaining non-drag failures, preserving the passing full-aircraft results.
Previously rejected receiver substitutions, simple sign/axis changes, and the
frozen alternative should not be repeated without new evidence.

The [force-consistency and mesh follow-up](isae-sa7-force-consistency-20261107.md)
now shows that 23/29 archived fore-wing rows violate a conditional CD/CDi lower
bound even at 5%. Twenty-four new mesh solves retain all sampled non-drag
failures; 80/160 refinement changes every coefficient by less than 0.004%.
Counts remain 682/812. The runner's `sa7-documented` comparison selector now
reproduces this input pairing without manually combining alternative scopes.

Evidence: [plan](../../artifacts/isae/sa7-focus-20261107/plan.json),
[analysis](../../artifacts/isae/sa7-focus-20261107/analysis.json),
[selected comparison](../../artifacts/isae/sa7-focus-20261107/documented-case-comparison.json),
[independent verification](../../artifacts/isae/sa7-focus-20261107/verification.json),
[PNG plot](../../artifacts/isae/sa7-focus-20261107/documented-fore-comparison.png).

SA-6 is deferred at the user's request, with 470/528 static and 370/528
supplemental F1 matches retained. Its profile-load feasibility study was only
prepared: two preliminary LP pilots returned, but none of the planned 88-state
batch ran. That prepared study is not a completed validation result.
