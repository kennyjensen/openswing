# ST-5: complete current static replay and published moment curves

The subsequent [five-grid mechanics assessment](isae-st5-mechanics-current-20261110.md)
now qualifies 16,687/16,688 native observations with all 224 final mesh checks
passing. This earlier two-grid record and its failed refinement checks remain
preserved below; its statements about primary adoption describe that earlier stage.

All **16 distinct archived static snapshots** have now run on two grids with
the current production structural equations. All **32 states pass** equilibrium,
support balance and the applicable clamp/joint checks. Thirty states are new;
two authenticated states from the earlier current-code pilot were reused.
No production equation, load, stiffness, geometry or native target changed.

| Original snapshot family | Archived-station matches | Subdivided-grid matches | First-pair mesh checks | Median relative error among finer-grid failures |
|---|---:|---:|---:|---:|
| Rigid joint, four cosine load cases | 4,479 / 4,480 | 4,315 / 4,480 | 0 / 56 | 10.69% |
| Literal type-2 roller, four load cases | 4,480 / 4,480 | 4,324 / 4,480 | 16 / 56 | 11.59% |
| Forward wing only, cosine/elliptical at 20/30 lb | 3,248 / 3,248 | 3,064 / 3,248 | 15 / 56 | 10.87% |
| Rigid joint, four elliptical load cases | 4,480 / 4,480 | 4,384 / 4,480 | 19 / 56 | 12.44% |
| **Same observations across all families** | **16,687 / 16,688** | **16,087 / 16,688** | **50 / 224** | — |

The numerical allowance is 5% relative plus each original printed
half-last-place. These counts cover the 14 computed structural fields at every
archived row, including both traces at duplicate stations. Prescribed zeros,
input echoes and unresolved `f_reac` display values remain separately recorded
among all 27 fields. Two grids repeat the same observations and must not be
added as independent evidence. The primary historical ledger is unchanged:
this replay has not yet met the existing **0.1%** refinement requirement.

The sole archived-station miss is forward-wing normal force in rigid
`30lb_80_20`, at t = 1.795828 (original output line 67): **−0.000328058 lb**
versus **−0.000290 lb**, a difference of **0.000038058 lb (13.12%)**. Its opposite
wing sample is +0.00033 lb in the archive and +0.000328055 lb in OpenSwing.
This near-zero asymmetry is evidence to investigate, not grounds to remove
the target, assert an archive error or enlarge the absolute allowance.

Subdivision increases the differences in every family. Across cases, median
errors for vertical deflection, twist and chordwise moment remain respectively
0.141–0.306%, 0.059–0.736% and 0.186–0.766%. The 601 failing finer-grid values
include small force/moment/strain denominators; the largest percentage is
7,899%. All dimensional and pointwise errors are retained. Close typical
agreement does not erase these failures or establish mesh convergence.

## Direct comparison with the authoritative report

The original vector paths in [Jan, Part III](../../reference/aswing-authoritative-20261108/isae-part-3-structure.pdf),
**Figures 28(b–d) and 29(a–c), pp. 43–44**, supply 225 visible vertices across
12 joined-wing moment curves. The plot below compares those actual PDF
coordinates with current body-x moments at the corresponding archived
stations. It does not substitute experimental data or normalize the loads.

![Current OpenSwing and published ASWING body-x moments](../../artifacts/isae/st5-family-current-20261109/paper-moments.png)

On the archived-station grid, maximum discrepancies normalized by each curve's
peak range from **0.026% to 0.571%**. On the subdivided grid, they range from
**0.075% to 0.451%**. This is a descriptive curve-scale measure, not a claim
that every point meets a 5% relative gate or a new primary acceptance scope.
The black cantilever curves are outside this particular PDF extraction;
the four original forward-only snapshots are included in the full replay above.

The original plotting scripts apply the output header exponents to Euler
angles as well as moments. Their moment transformation reproduces the PDF
curves to within **0.000367 N m**, with normalized span differences below
**0.00000571**. Physical angle decoding and current body-frame moments remain
separate; the production output is not changed to imitate that postprocessor.
Initial tighter source-precision checks remain recorded: 148 of 225 coordinate
checks and 206 of 225 moment checks meet their original 3e−6 / 0.0003 N m
bounds. These extraction diagnostics add no native passes.

Two source findings matter for future work:

- The archived rigid SVG named `JW1_30lb_90_10.svg` is labeled 30 lb but contains
  the 20 lb curve: its forward root is 15.9146 N m, whereas the original 30 lb
  table and actual report PDF give about 24.2623 N m. The direct PDF comparison
  preserves the proper published curve; the contradictory SVG is retained.
- Figure 29's curves closely reproduce the archived `Link_Joint` outputs,
  whose files specify the public **rotation-only type-2 roller**. The report's
  p. 42 description instead specifies a modified in-plane link with matched
  z translation and x/y rotations. This is a setup/version conflict. Matching
  the plotted data supports their lineage but cannot authenticate a modified
  executable or prove equivalence of the two joint laws. Do not change the
  production roller definition on this evidence.

The [saved joint checks](../../artifacts/isae/st5-family-current-20261109/joint-law-clarification.json)
also show relative body-z translation of 0.00307–0.01266 ft at the roller
connections, with exactly zero joint force and matched rotation. The difference
from the paper's z-translation constraint is exercised in these states. That
receipt corrects an old pilot-manifest prose typo: its rigid joints use the
literal **default type 0**, not type 1. The actual input and calculations were
rigid throughout; the frozen manifest and original evidence are preserved.

The authoritative report, original input/driver/output, literal joint settings,
physical output decoding and historical MATLAB plot conventions are all retained.

## Remaining work and evidence

Complete a fresh bounded convergence extension before promoting a mechanics
scope to accepted validation; the older finer-grid studies remain historical
evidence. Investigate the near-zero force miss and resolve the modified-link
interpretation without fitting parameters. Then integrate a declared mechanics
scope in the recurring runner, retaining all unavailable reference values and
legacy output limitations. No usable native modal target was recovered in the
earlier [ST-5 source inventory](isae-st5-source-review-20261104.md).

The [full assessment](../../artifacts/isae/st5-family-current-20261109/assessment.json)
authenticates source hashes, terminal receipts, original text tokens, all field
counts and every failure. The [PDF comparison](../../artifacts/isae/st5-family-current-20261109/report-curves.json)
preserves drawing indices, axes, source-row correspondences and both prediction
grids; the [SVG audit](../../artifacts/isae/st5-family-current-20261109/curve-audit.json)
retains the contradictory 30 lb asset. A [vector plot](../../artifacts/isae/st5-family-current-20261109/paper-moments.svg)
is available for export.

Every numerical job ran serially with one BLAS thread, a 512 MiB address-space
cap, 15 CPU seconds and 25 wall seconds. All children exited normally and were
reaped; none remains running. Peak recorded RSS was 117,872 KiB. The 32 solves
themselves took 27.20 seconds in total; imports, source checks, restoration and
evidence writes add substantial wall time. No numerical retry or background
solver was used. Browser/build jobs remain held.

Prepare a new directory with `scripts/prepare_st5_family_current.py`. Each
prepared case then runs through `scripts/verify_st5_current.py`, one `--level`
at a time, and `scripts/assess_st5_current.py`. The complete saved-only audit
and plot are produced by `scripts/assess_st5_family_current.py`. The earlier
two-state pilot and its original assessor are preserved byte-for-byte.
