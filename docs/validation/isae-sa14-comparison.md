# SA-14 consolidated quantitative comparison

**The supplied numerical datasets have been compared; physical validation remains incomplete.** This consolidates the original-input pilot, extended lift polars, archived load exports and explicit incidence reconstructions. All 50 upstream case files and 97 solver modules retain their original hashes.

The case comes from [ISAE’s validation repository](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/tree/f62943df20e9e4d7d9f50e070477b22426b5f865), with experimental definitions from [NACA TN 3730](https://ntrs.nasa.gov/citations/19920075067). The report distinguishes measured pressure/balance data, interpolated lower-surface data, drawn curve endpoints and original ASWING calculations.

| Supplied data | Unique rows/points | Evidence |
|---|---:|---|
| iw=0 span loads, Figure7.csv | 48: 42 pressure stations, 6 drawn tips | [Original-input pilot](isae-sa14-pilot.md) |
| iw=4 span loads, Figure17.csv | 24: 18 standard pressure, 3 partly interpolated, 3 drawn tips | [Explicit incidence reconstruction](isae-sa14-incidence.md) |
| Global lift, Figure24.csv | 44: balance and exposed-wing pressure lift | [Extended polars](isae-sa14-polars.md) |
| Three original ASWING polars | 180: 116 flagged converged, 64 unconverged | [Archive comparison](isae-sa14-polars.md) |
| Two original load exports | 426 rows in 9 beam tables and 6 states | [Staggered-coordinate audit](isae-sa14-load-exports.md) |

The three identical copies of each CSV count once. All 107 pressure/global-lift points have predictions in the selected finite-mesh comparisons; nine drawn tip endpoints remain distinct, including null predictions outside native midpoint coverage. This does not supply missing uncertainty or establish a validation threshold. The iw=4 geometry is reconstructed, and its Figure15/17 mapping remains a documented inference.

## Numerical coverage

The studies contain 3,056 request observations: 3,008 computed and 48 rejected. Deduplication by source bytes and actual condition gives 3035 distinct conditions (2987 computed, 48 rejected); 21 repeated observations are explicitly linked and their coefficient agreement checked. Equivalent-coordinate inputs remain separate because their stored sources and frame angles differ.

The pilot, polar and incidence studies contain 146 WASM executions and 35 offline browser executions. These are replay counts, not additional experimental points. Expected domain rejections are retained. Independent body-field quadrature and 18 incidence frame pairs provide separate numerical checks.

## Findings and limits

Primary-Mach N100 global CL RMSE is 0.09217 for total wing/body lift, 0.09789 for exposed wing with body, and 0.06976 for exposed wing alone. At iw=4, local-load RMSE is 0.03043, 0.07339 and 0.14400 at wing angles 4.7°, 8.8° and 12.9°. Error definitions and sample counts remain in the linked studies; these values do not constitute a pass.

The [swept-force diagnosis](swept-lifting-line-limit.md) identifies a growing force-point velocity under mesh refinement. Higher-angle lift/stall discrepancies remain, even when integrated lift changes modestly with resolution. Original reference settings, moment origin, body geometry scale, incidence provenance and uncertainty also remain unresolved.

The source screenshots include additional primary-report context that has not been fully digitized. This consolidation covers every supplied numeric comparison table and CSV; it does not claim to reproduce every primary-report figure, or to validate the full family.

## Evidence and reproduction

- [Consolidated machine-readable report](isae-sa14-comparison.json) includes all 116 mapped points, source-file roles, duplicate-condition links and native cache hashes.
- [Family coverage audit](isae-sa14-family-checks.json) verifies the pinned studies and all source/cache bytes.
- Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/consolidate-isae-sa14.py` to rebuild this consolidation from existing results. It does not run new solves or alter source models.

SA-14 qualifies as a completed quantitative study of part of its scope. It remains **partial**, with every physical limitation above carried into the coverage ledger. This source report does not update the packaged SA-12 application.
