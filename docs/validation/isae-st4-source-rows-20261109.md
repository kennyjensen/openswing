# ST-4: source-row audit of the remaining discrepancies

Three of the six primary frequency failures have stronger evidence of source
row mismatches. This evidence comes from the paper's **experimental columns**
and the original CSV/spreadsheet positions, independently of OpenSwing's
predictions. Experimental frequencies are used here only to identify rows;
they do not become acceptance targets.

The primary result remains **66/72 against the paper**. Every original model
mapping, paper value and failed comparison is retained. The paired native
exports remain a separate **31/31** comparison.

## What the original sources establish

| Paper entry, Part III Table 6, p. 48 | Independent source evidence | Consequence |
|---|---|---|
| Weight IV / 7d at `y/b = 0.69` | The first experimental frequency, 4.2 Hz, belongs to 33 inches. Both upper experimental entries, 34.2 and 22.4 Hz, match the 39-inch row (34.2 and 22.45 Hz at source precision). The 33-inch row instead gives 33.25 and 23.5 Hz. | The paper combines different positions within one triplet. Moving the entire case to 39 inches would not resolve that mixture. |
| Weight VI / 7f at `y/b = 0.83` | All three printed experimental frequencies—4.4, 34.2 and 21.5 Hz—match the 32-inch row, whose values are 4.38, 34.2 and 21.5. None matches the 40-inch row at printed precision. The accompanying ASWING values and error percentages also resemble the 32-inch spreadsheet row. | The row contents correspond to 32 inches (`y/b = 2/3`), while its printed position corresponds to 40 inches. This identification does not rely on fitting a model to a frequency. |
| Weight VI / 7f at 24 inches | Spreadsheet cells `O31`, `S31`, `W31` are exactly `O14`, `W14`, `S14` from the 7c/21-inch row: 5.8244, 28.28, 22.2283 Hz. They are literal stored numbers, not formulas or cross-sheet links. The CSV repeats them. | This is a possible copied triplet, with its upper labels exchanged. The source contains no formula or original 24-inch modal listing from which to recover corrected values. It remains unresolved. |

The paper's experimental columns were checked visually against the original
PDF. Matching source precision allows half a printed unit, including the
22.45/22.4 boundary; this source-identification test is separate from the 5%
solver acceptance policy. The spreadsheet has one visible sheet and contains
no hidden alternate worksheet supplying the disputed triplet.

## Same-position CSV comparisons

The original CSV explicitly supplies mass positions. Comparing its ASWING
frequency sets with the **same-position, unchanged input files** gives:

| Model position | Largest reference error across both 64/128 meshes |
|---|---:|
| 7d, 33 inches | 0.11241% |
| 7d, 39 inches | 0.15146% |
| 7f, 24 inches | 5.62748% |
| 7f, 32 inches | 0.08104% |
| 7f, 40 inches | 0.15903% |

These are alternative-source diagnostics using already completed, authenticated
states. No new physical solve, model-property change, nearest-frequency
search or per-mode position reassignment was performed. They add no primary
passes. In particular, the unresolved 24-inch row remains visibly discrepant.

An additional check compares the CSV directly with the five original
`vaccum.txt` exports, with **no OpenSwing predictions involved**. Fourteen of
the fifteen first-three-frequency entries agree within their printed
precision. The exception is the 7f/48-inch third frequency: the CSV gives
**28.28 Hz**, while the paired native export gives **30.715302918 Hz**
(a **7.9286%** difference). This is a source-versus-source inconsistency,
not evidence that OpenSwing should be adjusted to the CSV value. The CSV's
28.28 is also the value present in the 7c/21-inch and 7f/24-inch rows.
The exact historical reason for the discrepancy is unproved.

![ST-4 source positions and frequency comparisons](../../artifacts/isae/st4-source-rows-20261109/source-comparison.png)

[Download the SVG](../../artifacts/isae/st4-source-rows-20261109/source-comparison.svg).
Lines connect the three ascending OpenSwing frequencies at original model
positions. They do not assert native bending/torsion identities. Green circles
retain original CSV values; red crosses retain paper positions and values.
The inconsistent 7f tip CSV frequency remains visible as the final green
circle below the upper blue curve; it is not filtered out.

## Public input history does not recover corrected files

The current-path history contains only the
[27 February 2025 folder rename](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/commit/a58ec61bbafb22f9915ed4188b34bc35727e05bc).
The old-path history also contains the
[26 February first structural upload](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/commit/8f368bb58255ea7c39390911b21cdae4a5e96363).
Both histories were fetched completely, with no pagination links.

All **69 original ST-4 file blobs** are byte-identical to that initial upload,
including every model, script, workbook and CSV. The missing `W0.asw` is absent
there too. Thus this public history supplies neither an earlier corrected
position table nor the missing unloaded input. The separate lower-inertia
unloaded diagnostic remains evidence of a likely input difference, not recovery
of the exact generating file.

These findings support retaining the current mechanics implementation while
keeping the source conflicts explicit. They do not prove full native startup
equivalence, identify native mode shapes, or validate ST-4 airflow/flutter.

Evidence: [source audit including native-export cross-check](../../artifacts/isae/st4-source-rows-20261109/audit-v2.json),
[read-only audit script](../../scripts/audit_st4_source_rows.py),
[history downloads](../../reference/isae-st4-source-history-20261109/),
[authoritative Part III](../../reference/aswing-authoritative-20261108/isae-part-3-structure.pdf),
[original CSV](<../../reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Eigen_data_save.csv>),
[original workbook](<../../reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Modal_analysis.xlsx>).
