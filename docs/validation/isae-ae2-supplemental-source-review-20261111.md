# AE-2: supplemental export source review

Observed 2026-11-11 UTC. **The alleged supplemental span distribution is an
exact duplicate of an already tested sensor sweep.** It supplies no additional
span values or independent comparisons. AE-2 remains **2,068/2,200 at 5%**;
no denominator, acceptance gate, original input or production equation changed.

The [repeatable source audit](../../scripts/audit_isae_ae2_supplemental.py)
checks every one of the **98 original AE-2 files** against both the SHA-256 and
Git blob identifiers in the retained upstream manifest. The Part IV report
and extended manual, including their searchable text, also match the
[authoritative source catalog](aswing-authoritative-sources.json).

## What the archive contains

| Source | Finding | Effect on comparison coverage |
|---|---|---|
| Twelve `.sh` drivers and twelve sensor exports | Three layups, four commanded incidences; 275 original rows, each with four sensor channels | Already registered on both grids: 2,200 required values, including 96 unavailable zero-speed values |
| `[m15_02]_S_A15_dist.txt` | All 1,248 bytes are identical to `[m15_02]_S_A15.txt`, including the sensor header and initial NaNs | Duplicate provenance; zero additional comparisons |
| `Steady_deflection/Analysis.m` | Reads exactly the twelve registered native sensor exports; never reads `_dist.txt` | Confirms the native data used by the archived plotting script are covered |
| `[03_90]_flat.asw` | Horizontal variant with no paired shell driver/output in this case directory | Retain as an unpaired input; no native comparison can be inferred |
| `[0_3_90]_S/[03_90]_S.asw` | Different input ending with an unterminated `Engine` block; no paired shell driver/output here | Import/source ambiguity remains; no implicit repair or result substitution |

There are **13 native text exports but only twelve distinct contents**.
The remaining files include 36 CSVs, figures, a MATLAB script and the Dunn
paper. This audit verifies their original bytes; it does not classify every
figure or CSV as an independent ASWING reference. Experimental and other
numerical curves remain distinct from the native target.

## Reconciling the filename and command

The negative-coupling 15° driver selects sensor channels on lines 46–49,
writes `[m15_02]_S_A15.txt` on lines 51–52, and contains `ww` followed by
`[m15_02]_S_A15_dist.txt` on lines 54–55. Nevertheless, both retained files
have the same SHA-256:

`7e207ea0a6b4f03c76618a17efd40857c3f215c405492147b33be387bb7277e7`

Their header identifies an operating-point sequence with `RY`, `Psi`, `V`
and `beta` for sensor 1. Each has fifteen rows: one all-NaN initial record
and fourteen finite speeds. There are no beam station, loading or strain
columns in this file.

Drela's user documentation, **Time-Marching Calculation**, describes `WW`
as writing spanwise distributions; this is reproduced in the extended manual's
official-documentation chapter. That documented behavior conflicts with the
actual archived payload. Without an execution transcript or the original
executable, the cause is unknown. A filename and command cannot establish
reference data absent from the file.

Jan's **Part IV §3.2, pp. 8–12, Figure 3** evaluates tip deflection and twist
for these three layups. `Analysis.m` plots native sensor speed against negative
Earth Y and commanded incidence minus heading, using the twelve existing
files. The duplicate does not add a separate span validation requirement.
Independent span-field validation would need an actual native span export.

## Remaining numerical work

The [current complete sensor comparison](isae-ae2-beta15-complete-20261111.md)
is unchanged: **2,068 passes, 16 computed mismatches, 20 unresolved execution
outputs and 96 unavailable references**. All finite sensor conditions have
been attempted. The five unfinished conditions and branch discrepancies
remain the next numerical priority.

One of those conditions, negative coupling at 5°/18 m/s on nominal mesh160,
has a complete result in the earlier
[staged cold-solve study](isae-ae2-cold-stages-20261110.md). Its original plan's
180 source pins still match; a [saved-chain check](../../artifacts/isae/ae2-supplemental-source-review-20261111/saved-candidate-review.json)
also confirms that its original request matches the current job and that all
four checkpoint transitions are preserved. The earlier audit reports a fresh residual of
3.630e−14 and all 18 physical checks passing, but three of its four native
outputs disagree. It is still diagnostic: the current collector only accepts
the later, separately audited attempt-boundary route. Supporting the earlier
route requires its own checked chain provenance and integration into the
collector, followed by a current full audit. No result is promoted by this
source review, and the original execution receipts remain intact.
The old stages used a 30-second outer supervisor; this review does not relabel
them as runs under the current 25-second limit or make a new physics call.

Earlier source catalogs and dated reports used “supplemental span distribution”
based on the filename and `ww` command. Those immutable observations and
source-pinned execution plans remain retained. This review corrects that
interpretation in the current status and backlog. It does not remove any
registered reference value or mark the whole AE-2 family validated.

Evidence: [source assessment](../../artifacts/isae/ae2-supplemental-source-review-20261111/assessment.json).
