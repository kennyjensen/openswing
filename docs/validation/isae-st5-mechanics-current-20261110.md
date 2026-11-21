# ST-5 mechanics: native agreement with independent convergence

**16,687 / 16,688 distinct structural observations pass at 5% plus original
printed precision.** All 16 original static cases now pass the physical and
mesh-convergence requirements: **80 physical states and 224 final field checks**.
The remaining native miss is retained. No production equation or model changed.

| Original cases | Qualified native matches | Final mesh checks | Largest final mesh change |
|---|---:|---:|---:|
| Four rigid joints with cosine loading | 4,479 / 4,480 | 56 / 56 | 0.03865% |
| Four literal type-2 rollers | 4,480 / 4,480 | 56 / 56 | 0.01318% |
| Four forward-only cosine/elliptical cases | 3,248 / 3,248 | 56 / 56 | 0.02993% |
| Four rigid joints with elliptical loading | 4,480 / 4,480 | 56 / 56 | 0.02094% |

## What this score measures

This is an **explicit change to the primary mechanics scope**, defined in the
[frozen declaration](isae-st5-mechanics-scope.json) and recorded by the
[adoption receipt](isae-st5-mechanics-adoption-20261110.json). The declaration's
status describes its preparation before refinement finished; the adoption
receipt records its subsequent promotion. Earlier progress observations and
the original strict totals are preserved.

The new scope counts each of the 14 computed structural fields at every original
row once. It compares OpenSwing's prediction on the archived-station grid with
that native finite-grid output. Each case must independently pass equilibrium,
support balance and clamp/joint checks on **all five grids**, plus the existing
**0.1%** maximum field-change gates on the final refinement pair. There is no
minimum-error selection across meshes. Prescribed zeros, echoes, mesh repeats
and unresolved scalar display values do not add mechanics votes.

The grid uses printed source stations and independently known exact anchors.
Original unrounded node coordinates and automatic ASWING node-generation
equivalence remain unproved. This qualification applies to the native match;
no coordinate, load or material property was fitted to make it pass.

The distinction matters because a converged continuum prediction need not equal
an archived finite-grid solution. All finer-grid/native discrepancies remain
visible rather than being discarded:

| Refinement level | Raw matches against the same 16,688 archived values |
|---|---:|
| Original station grid | 16,687 |
| First subdivision | 16,087 |
| Second subdivision | 15,931 |
| Third subdivision | 15,911 |
| Fourth subdivision | 15,905 |

These are overlapping comparisons, not five independent denominators. The
original strict ledgers remain rigid 13,833/25,920, roller 14,708/25,920,
forward-only 10,670/18,792 and elliptical 13,583/25,920, with their original
field definitions and historical kernels. They remain in `ISAE_STATUS.md`
but are excluded from the new primary total. Changing that weighting can lower
the overall pooled percentage even though ST-5's mechanics fraction increases;
it is a documented scope change, not a solver regression.

## Remaining native miss and setup limitations

The sole miss is rigid `30lb_80_20` forward-wing normal force at t = 1.795828,
original output line 67. OpenSwing gives **−0.000328058 lb** versus archived
**−0.000290 lb**: **0.000038058 lb absolute error, 13.12% relative**. Its opposite
wing sample agrees closely. The original printed-precision allowance is
unchanged; the target remains required. This does not establish an archive error.

The [focused force audit](isae-st5-force-audit-20261110.md) confirms source
decoding and the small archived left/right asymmetry. Four predeclared
coordinate-precision probes explain at most 9.44% of the absolute miss; all
remain outside the original allowance. The complete force-vector error is
0.00375%, which provides scale without replacing the scalar comparison.
The nominal fresh residual is already about 6.1e-14. No production fix or
additional pass follows from these diagnostics.

The [source audit](isae-st5-family-current-20261109.md) also retains the report's
modified in-plane-link description versus the archived literal roller law,
the mislabeled 30 lb SVG, original exporter/reaction-display uncertainties,
unbound outputs and unavailable native modal evidence. The
[recurring runner](isae-st5-recurring-20261110.md) now implements this declared
scope; four representative fresh cases and independent import are verified.
These remaining source/setup limits,
and the remaining native miss, prevent declaring the whole ST-5 family or the
full OpenSwing goal complete.

The [distributed normal-load follow-up](isae-st5-reaction-display-20261110.md)
now checks the static `f_reac` definition: existing gravity forces and physical
midpoint normals match all 992 actual interval values within 0.01966%. The 200
duplicate/terminal display rows retain separate treatment; exact historical
interpolation remains unproved. This supplementary output audit does not alter
the primary mechanics scope or resolve the internal `Fn` miss.

## Current refined comparison with the paper

![Archived-grid and converged OpenSwing moments against the report](../../artifacts/isae/st5-convergence-current-20261109/converged-paper-moments.png)

The same 225 PDF vertices from the twelve joined-wing curves in Part III
Figures 28–29 are retained, with the same source-row correspondence. The
finest-grid moment discrepancy is at most **0.412% of each curve's peak**.
This describes the curve agreement; it does not replace the pointwise native
acceptance allowance or establish the paper's modified joint implementation.
[Vector plot](../../artifacts/isae/st5-convergence-current-20261109/converged-paper-moments.svg).

## Verification and reproduction

The extension adds **48 cold solves and fresh saved-state residual checks** to
the 32 authenticated current states. Joined-wing meshes end at 304/256 and
608/512 intervals; forward-only meshes end at 304 and 608. Exact subdivision,
all original rows and every original output field remain intact.

All numerical jobs ran serially with one BLAS thread and the same 512 MiB,
15 CPU-second and 25 wall-second caps. The largest new child used 12.93 CPU
seconds, 16.21 wall seconds and 187,164 KiB peak RSS. No numerical attempt
failed or was retried. Full-source checks run in the supervisor; kernel,
source and target identities are also checked inside each verifier.

Compact JSON removes whitespace only. Round-trip checks preserve all retained
result values, and the generated verifier differs from its parent only at that
serialization expression. All 141 production Python modules remain unchanged.
The independent audit rechecks saved residual arrays and positions, model
identities, original text tokens, field counts and every mesh difference.
Six acceptance-accounting tests cover retained misses, missing grids, failed
intermediate states and missing/failed convergence fields. All six pass.

The [full summary](../../artifacts/isae/st5-convergence-current-20261109/summary.json)
links the per-case audits and terminal receipts. The
[prior replay](isae-st5-family-current-20261109.md) and all earlier failed mesh
pairs remain preserved. No solver remains running; browser/build checks remain
held following the earlier UserLAnd failures.

Use `scripts/extend_st5_current.py prepare` for a selected original case in a
new output directory, followed by separate `run --level 2`, `3`, and `4`
invocations. `scripts/assess_st5_convergence.py --case CASE` audits a completed
case without solving. After all sixteen audits, `scripts/summarize_st5_mechanics.py`
produces the summary and plot. All scripts accept `--help`.
