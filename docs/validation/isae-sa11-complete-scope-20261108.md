# SA-11: all original archived polars

This is the retained pre-minimum-spacing result. The subsequent
[original-suite rerun](isae-sa11-original-minimum-spacing-20261108.md) passes
**1,060/9,184** with the same targets and the new minimum spacing.

This comparison passed **163/9,184 scalar checks at 5%**. It covers
all sixteen original polars across the four configurations with paired output.
This is a coverage expansion, with **no new numerical matches**. The previous
[baseline/extension scope](isae-sa11-focus-20261107.md) was 163/4,592.
All 328 executable requests were freshly run; predictions agree with the
previous results within 1.02e-15 scaled difference, with unchanged outcomes.

| Original configuration | Passing scalar checks | Computed states | Local-Mach rejections | Unavailable original requests |
|---|---:|---:|---:|---:|
| Wing alone | 21/2,296 | 21 | 143 | 164 |
| Wing extension | 142/2,296 | 26 | 138 | 164 |
| Upper winglet | 0/2,296 | 0 | 0 | 328 |
| Upper and lower winglets | 0/2,296 | 0 | 0 | 328 |
| **Total** | **163/9,184** | **47** | **281** | **984** |

Each configuration includes four Mach-labelled tables, 41 angles from 0° to
10°, seven fields (lift, drag, CL, CD, CDi, Cm and efficiency), and both declared
64/128 mesh requests. These are comparison slots, including mesh repeats, not
9,184 independent experiments. Mandatory breakpoints can increase actual mesh
size. The unpaired `wingtip_up_cant0.asw` has no archived polar; no output is
invented for it. Post-stall rows stay in the denominator while post-stall
repairs remain deferred.

## What prevents the additional comparisons

The [frozen plan](../../artifacts/isae/sa11-complete-scope-20261108/plan.json)
records an actual parse/mesh preflight for all four original models, exact
driver commands, raw output tokens, normalization intervals and file hashes.
It exposes three distinct issues:

- **Upper winglet:** original Joint line 32 has five multipliers,
  `* 1 1 0.1 0.1 1`. The documented format scales only the two station columns;
  the current parser rejects the extra values. See the original
  [user guide, Joint block](../../reference/aswing_doc.txt), lines 813–824,
  and multiplier rules at lines 185–189. Native acceptance of this exact row
  in the historical executable is unverified.
- **Upper/lower winglets:** the original Joint stations are ±12.426, but the
  scaled main-beam parameter domain is ±1.2426. Parsing succeeds; mandatory
  attachment meshing rejects the out-of-domain stations.
- **All eight .75/.78 tables:** force/coefficient/speed pairs imply reference
  area about 97.67 m² if the literal density is used, versus the input's
  0.9329 m². Only the density–area product is determined by this calculation;
  it does not recover the historical geometry or justify rescaling a model.
  The .70/.80 winglet tables are consistent with the literal normalization.

There are 656 normalization-blocked requests and 656 input-blocked requests,
with **328 overlapping**: 984 distinct unavailable requests. Each retains all
seven targets. No repaired bundled input, altered twist, inferred area or
experimental curve replaces an original reference. The reported blockers
describe the documented literal route in current OpenSwing; they do not prove
that the archived ASWING binary rejected the same files.

## Remaining numerical discrepancies

The executable baseline/extension scope is unchanged: 47 computed states,
281 local section-normal Mach rejections, and **no timeouts**. Across failed
computed checks, the relative errors are:

| Quantity | Median error | Maximum error |
|---|---:|---:|
| CL | 7.54% | 8.07% |
| CD | 11.92% | 25.62% |
| CDi | 14.88% | 16.05% |
| Cm | 7.36% | 7.99% |

These percentages exclude unavailable or rejected states, for which a valid
prediction and numerical error cannot be reported. Lift/drag errors follow
their corresponding coefficients. All 47 computed efficiency checks pass.

The [authoritative reference index](aswing-authoritative-references.md) and
[checksummed catalog](aswing-authoritative-sources.json) govern interpretation.
ISAE Part I Table 2, p. 23 calls SA-11 repeatable; p. 35 qualifies transonic
prediction and omits some numerical settings; Appendix D, pp. 65–68 provides
geometry. Those statements still need reconciliation with the original files.
Historical NODE, KK/MM and startup influence/PG settings remain unverified;
the existing declared current-wind, sea-level PG, natural-v1 and stall settings
are preserved. This refresh does not claim an exact historical setup.

The [report-derived upper-winglet diagnostic](isae-sa11-winglet-polar-20261108.md)
remains separate: report −4° twist gives native AVL lift/CDi within
0.561%/0.332% across 21 angles, but local production flow is rejected.
The [aligned-root analysis](isae-sa11-native-root-conformity-20261108.md) and
[shared-bound-corner analysis](isae-sa11-shared-bound-corner-20261108.md)
identify growing junction velocities even when integrated loads agree.
They establish neither new primary passes nor a valid production repair.

The next physical investigation remains **pre-stall winglet-junction local
velocity and section-force sampling**, alongside source/setup reconciliation.
SA-2 stall-region work remains deferred. Preserving the source conflicts makes
the remaining work visible; it does not resolve them.

## Execution and verification

- [Adapter](../../scripts/isae_suite_sa11.py): all sixteen tables and all four
  paired models, with explicit and overlapping blocker codes.
- [Run driver](../../scripts/refresh-sa11-complete-scope.py): 48 terminal,
  serial foreground batches, one BLAS thread, at most eight physical calls per
  batch, 30-second per-call limit and 768 MiB process address-space limit.
  Physical job records total 150.32 seconds, including adapter validation and
  assessment; the longest took 6.19 seconds. These are not browser timings.
- [Aggregate](../../artifacts/isae/sa11-complete-scope-20261108/analysis.json):
  all 1,312 result records rechecked, all 9,184 slots retained, old/new source
  and result hashes authenticated. Six production files had changed since the
  prior plan, so no prior numerical prediction was reused.
- [Aggregation receipt](../../artifacts/isae/sa11-complete-scope-20261108/aggregation-receipt.json):
  the immutable 18 MB plan digest was cached with identity checks and full
  before/after hashing; acceptance and result validation were recomputed.
- Focused adapter, summary and runner selection: **71 passed, 351 deselected**
  in 14.14 seconds. An earlier broader invocation reached its 60-second limit
  after over 162 passing checks; it is not claimed as a complete suite pass.
  Tests cover exact source pairing, both real import/mesh failures, overlap
  accounting, source-only planning and altered-job rejection.

No production aerodynamic equations changed in this expansion. No whole-family
validation or accuracy improvement is claimed. The timestamped progress update
records the increased scope without rewriting earlier observations.
