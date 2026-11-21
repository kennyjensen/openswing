# SA-11: original suite rerun with minimum horseshoe spacing

The requested rerun passes **1,060/9,184 scalar comparisons at 5% (11.54%)**,
up from **163/9,184 (1.77%)**: **897 gained, none lost**. All 328 executable
requests were freshly solved in small serial jobs. Complete states increase
from 47 to 322; local-Mach rejections decrease from 281 to six. There were no
timeouts or interrupted solver jobs in this rerun.

| Original configuration | Passing comparisons | Complete states | Local-Mach rejections | Unavailable requests |
|---|---:|---:|---:|---:|
| Wing alone | 158/2,296 | 158 | 6 | 164 |
| Wing extension | 902/2,296 | 164 | 0 | 164 |
| Upper winglet | 0/2,296 | 0 | 0 | 328 |
| Upper and lower winglets | 0/2,296 | 0 | 0 | 328 |
| **Total** | **1,060/9,184** | **322** | **6** | **984** |

These are scalar comparisons including repeated mesh requests, not 9,184
independent cases. The original sixteen tables, four configurations, 41 angles
from 0° to 10°, seven fields and two mesh requests remain required.

## What changed

Only the mesh gains the previously established minimum material interval:
**0.0164659927127284 m**, applied throughout every logical beam. Original
cosine 64/128 requests and mandatory stations are retained, with coarsening
where needed. The fixed minimum was transferred unchanged from the preceding
winglet investigation; it was not adjusted to the results of this rerun.

| Original model | Requested intervals | Actual intervals | Smallest interval |
|---|---:|---:|---:|
| Wing alone | 64 | 62 | 16.946 mm |
| Wing alone | 128 | 106 | 16.946 mm |
| Wing extension | 64 | 60 | 18.081 mm |
| Wing extension | 128 | 108 | 17.074 mm |

The original files, section data, density, operating points, natural-v1 beam
interpolation, current-wind influences, true-speed compressibility, stall
settings, force conventions and numerical/5% acceptance gates are unchanged.
No production aerodynamic equation changed. This does not establish the
unrecorded historical ASWING mesh or startup settings.

## What still fails

For the **extended wing**, every computed lift, CL, CDi, Cm and span-efficiency
check passes. Total drag is the remaining discrepancy: failed CD checks have
median error **8.11%**, ranging **5.04–13.69%**. Forty-one of its 164 computed
states pass all seven scalar comparisons.

For the **baseline wing**, only span efficiency passes. Failed-check errors
are CL **7.71% median (6.49–9.89%)**, CD **15.03% (5.64–28.71%)**, CDi
**16.73% (14.05–22.39%)**, and Cm **7.23% (5.73–9.17%)**. Its six rejected
states are the 128-interval requests at 272 m/s and 8.75°–10°. The existing
section-slope/source discrepancy remains unresolved; the mesh change does
not repair it.

Across both configurations, failed-check medians/maxima are CL
**7.71%/9.89%**, CD **10.34%/28.71%**, CDi **16.73%/22.39%**, and Cm
**7.23%/9.17%**. These statistics cover valid computed results only. The much
larger number of computed states means their population differs from the
previous run.

The **984 unavailable requests** remain in the denominator:

- The original upper-winglet file has too many Joint scaling multipliers.
- The original upper/lower-winglet attachment stations lie outside the scaled
  main-beam domain.
- All eight .75/.78 tables conflict with literal force normalization.

Input blockers affect 656 requests and normalization blockers affect 656,
with 328 overlapping. Details and original user-guide references are retained
in the [original-scope audit](isae-sa11-complete-scope-20261108.md). Minimum
spacing cannot correct these file/settings inconsistencies. No repaired input
or rescaled reference was silently substituted.

The separate [report-derived upper-winglet result](isae-sa11-minimum-spacing-20261108.md)
remains **294/294**, and the [upper/lower diagnostic](isae-sa11-two-winglet-spacing-20261108.md)
remains **11/42**. Neither is added to this original-input score.

## Evidence and verification

- [Frozen plan](../../artifacts/isae/sa11-original-minimum-spacing-20261108/plan.json)
  authenticates the original jobs, references, settings and fixed mesh change.
- [Rerun driver](../../scripts/rerun-sa11-minimum-spacing.py) executed 118 serial
  foreground batches: at most three physical calls or 128 blocked records per
  process, one BLAS thread, 512 MiB address space, 15 CPU seconds and 25 wall
  seconds. Peak observed RSS was 254.45 MiB; longest batch 8.38 seconds.
  Physical-call records total 283.50 seconds, maximum 3.50 seconds per request;
  these include adapter assessment and are not browser timings.
- [Aggregate](../../artifacts/isae/sa11-original-minimum-spacing-20261108/analysis.json)
  authenticates and rechecks all 1,312 results against the previous full suite.
- [Independent saved-result audit](../../artifacts/isae/sa11-original-minimum-spacing-20261108/verification.json)
  checks all original job identities, 188 source hashes, source-table tokens,
  5% decisions, force/moment normalization, actual mesh intervals, unchanged
  settings and rejected/unavailable accounting. Maximum accepted circulation
  residual is **6.09e-13**, below the unchanged 1e-8 gate.

The primary SA-11 progress curve now uses this full-scope result. Its mesh
policy is explicitly recorded in the progress scope file; earlier observations
are preserved. SA-11 remains partially matched, not validated as a family.
