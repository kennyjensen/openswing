# SA-8: a published lead for the body-flow discrepancy

2026-11-01. The ISAE authors describe an ASWING implementation issue that is
consistent with the previously isolated SA-8 body-flow difference. This provides
a concrete native-algorithm explanation to investigate, rather than evidence
for removing the published body physics from OpenSwing. It does not establish
which executable or settings produced the archived SA-8 results.

## Direct source evidence and its limit

In their SA-14 discussion on PDF page 43, the authors report that constant
fuselage cross-section can cause ASWING to suppress the induced doublet field.
They identify `aic.f`, routine `AICVL`, and a condition involving `ARAD` and
`DRAD`. They say correcting it restores the doublets, but do not present corrected
results because of remaining instabilities. The inspected PDF matches the
upstream Git blob and manifest hash; its rendered page was also checked.
[ISAE Part 1 report](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/blob/f62943df20e9e4d7d9f50e070477b22426b5f865/5%20-%20Technical%20Reports/Experimental_validation_of_ASWING_Part_1_Aerodynamics_V4.pdf).

This is an author-reported issue in SA-14, not a direct diagnosis of the SA-8
export. The printed condition alone does not reconstruct the routine's variable
definitions or control flow. Applying that explanation to SA-8 is an inference.

## Why it applies to the SA-8 investigation

Direct reading of the stored full-aircraft input confirms that body beam 3 has
constant radius **0.0645 m**, axis **x = −0.1 to 0.95 m**, **y = 0** and
**z = −0.0645 m**. It has no lifting-surface chord table. Its friction and
pressure coefficients are 0.005 and 0.012. Thus it has the constant-section
geometry described in the reported issue.

For this straight body in incompressible flow, steady equation (162) gives
zero source density but a nonzero doublet at nonzero incidence:

`sigma = 0`, `nu = 2 pi R² sin(alpha) ez` per unit freestream speed.

The constant radius does not remove the crossflow boundary condition.
OpenSwing retains this doublet and its equation-(163) field. The earlier
[independent integral audit](isae-sa8-body-volume-20261031.md) already verified
41,760 saved field vectors and added three permanent regression cases;
those tests were not rerun here.

The saved diagnostic suppresses only induced body velocity while preserving
the body geometry and loads. Re-scoring its complete 36-state comparison
against the original native decimal tokens reproduces:

| Fixed strength-20 full-aircraft scope | Passing checks |
|---|---:|
| Published body-induced flow retained | 220/252 |
| Body-induced flow omitted, diagnostic only | 244/252 |

There are **24 gains and no losses**. The eight remaining failures are Lift,
CL, CDi and CM at −4° on both meshes. Total drag already passes all 36 states
with either body-flow treatment. This supports the reported legacy issue as an
explanation for part of the full-aircraft difference. Stall strength 20 and the
historical mesh/settings remain unconfirmed.

## The isolated-wing drag difference remains separate

The stored fore-only model contains one lifting beam and no body. It retains
constant `Cdf+Cdp = 0.020`; the reported body issue cannot explain its drag
shortfall. Its separate strength-20 result remains **212/252**, with failed
fine-mesh CD errors typically **11.29%**, maximum **15.66%**.

The drag-definition review also found no basis to replace total near-field
drag by Trefftz drag. Krengel's DLR thesis explicitly describes that replacement
as a modification to ASWING, whose original total drag uses the direct vortex
integration contribution. [Krengel 2025, printed pages 73–74](https://elib.dlr.de/213003/1/Dissertation_Krengel_DLR-FB-2025-8_finalVersion.pdf).
This agrees with the retained distinction between OpenSwing's total CD and CDi.

No production behavior, input, tolerance or registered acceptance changes.
The default SA-8 row remains **373/504**. The new work is a source and saved-data
audit: no aircraft solves, numerical test runs, browser launches or full builds.
Next work should concentrate on the isolated-wing drag and the residual −4°
interaction, while preserving the published body equations. Full ASWING parity
and the complete project goal remain unfinished.

[Source pins and exact-token recheck](../../artifacts/isae/sa8-native-body-report-20261101/analysis.json),
[audit log](../../artifacts/isae/sa8-native-body-report-20261101/audit.log),
[inspected report page](../../artifacts/isae/sa8-native-body-report-20261101/report-page43.png).
