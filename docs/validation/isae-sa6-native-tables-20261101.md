# SA-6: additional ASWING tables and control-input inconsistencies

The author-labelled `Cl_ASW` and `Cn_ASW` columns supply **220 additional
tabulated ASWING coefficients** beyond the roll/yaw values in the 44 raw
`.fmat` exports. They also give evidence that some level-flight results used
different control-effectiveness inputs from the supplied `.asw` decks.
This does not resolve the post-stall pitch-rate discrepancy or add registered
passes.

The later [complete current-equation comparison](isae-sa6-span-native-20261101.md)
covers all 14 native series on both meshes: 616/616 checks pass under explicit
gain, strength, incidence and 10-inch geometry hypotheses, maximum error 1.927%.
Literal-deck and competing-incidence failures are retained. This does not
authenticate native inputs or change the registered default comparison.

The subsequent [current-solver comparison](isae-sa6-level-input-comparison-20261101.md)
tests the fixed gain hypothesis with strength20 across five level-flight
variants and all eleven deflections on both meshes. It gives 220/220 matches,
maximum error 0.885%, versus 138/220 for the literal inputs at that strength.
The native settings remain unverified and registered counts remain unchanged.
The older cached predictions below retain their original separate scope.

## Reference coverage

The new [source reader](../../scripts/isae_sa6_native_tables.py) reads data;
it does not execute MATLAB or open a spreadsheet application. It pins the
original files, follows the native plot columns and ASWING legends, checks
ODS native-column headers and stored/displayed values, and retains source
line and cell addresses. Experimental columns and synthetic zero rows are
excluded. The earlier source audit had already retained these tables; this
change gives their native columns a dedicated catalogue and comparison.

| Source group | Variants | Native scalars | Raw export witness |
|---|---:|---:|---|
| Level-flight chord variants | 4 | 88 | None |
| Level-flight span variants | 3 | 66 | None |
| Post-stall chord variants | 4 | 88 | All 88 match exactly |
| Post-stall span variants | 3 | 66 | None |
| Total | 14 series | 308 | 88 |

All 308 native selections agree with the separately retained ODS/MATLAB
source audit. Its known invalid cells and numerical conflicts concern
experimental columns, not these native targets. Raw-export matching supplies
an independent witness for the 88 post-stall chord values. The other 220
values are author transcriptions without retained run headers, not equivalent
to complete raw ASWING output.

## Evidence of different level-flight control inputs

Five original decks—the four chord variants and `20b_25c`—are identical after
whitespace normalization and removal of the single `dCLdF1` multiplier. The
control signs differ between the chord/span families, so the comparison uses
the magnitude for the same physical deflection direction.

There are **10 exactly equal printed roll/yaw pairs** across those level-flight
series at different deflections. For example, `20b_15c` at 44° and `20b_30c`
at 32° both print `(Cl, Cn) = (0.169069, -0.017330)`.
These identities consistently imply the following relative control gains,
**if** the native series share their operating/setup state and the equal
printed response identifies the same effective control input:

| Variant | Supplied gain magnitude | Ratio implied relative to 15c | Gain if 15c used the supplied 0.040 |
|---|---:|---:|---:|
| 20b_15c | 0.040 | 1 | 0.040 |
| 20b_20c | 0.045 | 9/8 | 0.045 |
| 20b_30c | 0.061 | 11/8 | 0.055 |
| 20b_35c | 0.071 | 7/4 | 0.070 |
| 20b_25c | 0.055 | 3/2 | 0.060 |

Nine of the ten pairwise ratios disagree with the supplied multipliers.
This is a source-data inference from matching printed values, not a numerical
fit or authenticated recovery of the native inputs. The absolute 0.040 anchor
is itself a deck value: report Table 4 gives 0.039 for the 15%-chord aileron.
Table 4 otherwise distinguishes 0.055 for 25% chord from 0.061 for 30% chord.
No input deck, solver coefficient, or production default is changed.

## Comparison with existing saved predictions

The earlier SA-6 study contains literal-model predictions at 40/80/160
requested intervals, current/frozen influences, and body incidence 0°/8°/12°.
This audit reuses 1,122 of those saved results and makes 2,244 scalar comparisons.
It verifies every reused cache hash and independently reconstructs stability
moments from the saved body moments. No aircraft solves run. These predictions
come from the older study's recorded code, not a fresh verification of current
production.

For level flight, using the report's 4° wing incidence and the decks' 4° built-in
twist gives the provisional body-incidence choice 0°. At the finest saved mesh,
current/frozen influences coincide:

| Literal model | Historical scalar matches | Median / maximum failed error |
|---|---:|---:|
| 20b_15c | 22/22 | — |
| 20b_20c | 20/22 | 3.23% / 3.43% |
| 20b_30c | 4/22 | 10.01% / 11.76% |
| 20b_35c | 18/22 | 4.22% / 4.90% |
| 10b_25c | 0/22; geometry conflict | 33.72% / 42.82% |
| 15b_25c | 0/22 | 8.42% / 9.47% |
| 20b_25c | 0/22 | 8.52% / 9.58% |

The 30%-chord and 20-inch-span differences are consistent in scale with the
input discrepancy suggested above, but the comparison does not demonstrate
that changing those inputs explains every error.

Two qualifications remain explicit. The `10b_25c` literal deck defines 15-inch
control spans; it is never silently repaired or paired as an authenticated
10-inch model. For the post-stall span tables, report Figure 17 labels 16° wing
incidence, while the plotted experimental columns came from a 12°-incidence
table. Both corresponding body-incidence candidates (12° and 8°) are retained
separately, without choosing one by its score. Stability axes for unpaired
tables remain a declared interpretation supported by the paired chord outputs,
not independently recovered run metadata.

All comparisons retain the existing 3%/original-absolute policy. Their
qualified historical counts do not alter the registered 42-row status table.

## Verification and reproduction

Ten reader tests pass, covering changed native column selections, labels,
units and legend ordering; rejected malformed native values; experimental
column exclusion; ODS cell addresses; setup qualifications; and solver-free
imports. A separate verifier checks all 308 selections against the older
source audit, verifies 2,244 decisions with decimal arithmetic, and reconstructs
the moment-axis transformation independently.

The initial reader stopped on the original misspelling `delfeciton` and the
capitalized `Coefficient` label. Both exact spellings are now retained and
tested. The first independent verification stopped because the final MATLAB
row's closing `]` was included in its raw token; the corrected verifier removes
only that syntax. Both attempts and their terminal results are retained.

```sh
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/isae_sa6_native_tables.py \
  --output /tmp/sa6-native-tables.json
```

Evidence: [catalogue](../../artifacts/isae/sa6-native-tables-20261101/catalog.json),
[comparison plan](../../artifacts/isae/sa6-native-tables-20261101/replay-plan.json),
[historical comparisons](../../artifacts/isae/sa6-native-tables-20261101/replay.json),
[verification](../../artifacts/isae/sa6-native-tables-20261101/verification.json),
[exact gain identities](../../artifacts/isae/sa6-native-tables-20261101/gain-identities.json),
[test log](../../artifacts/isae/sa6-native-tables-20261101/tests.log).
