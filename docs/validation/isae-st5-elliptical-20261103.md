# ST-5 original joined-wing elliptical-loading comparisons

All four unchanged elliptical-loading cases complete three initial grids and one
additional refinement. **All 16 solves and 16 fresh residual checks pass**.
The final refinement passes **56/56 mesh checks** at the unchanged 0.1% limit.
Archived ASWING agreement remains incomplete; no solver equation or tolerance changed.

The original three-grid comparison gives **13,583/25,920 qualified scalar matches**:
2,147/13,440 structural values, 9,600/9,600 conditional zeros and 1,836/1,920 input
echoes. The 960 unresolved reaction-display entries remain required; their 42 raw
coincidences are excluded from qualified matches. The saved-only independent summary
reproduces all 13,625 raw matches. Zeros and input echoes do not establish structural fidelity.

The original grids use 38/32, 76/64 and 152/128 forward/rear beam intervals.
Their last pair passes 44/56 mesh checks; lateral displacement, section bank and
twist fail in each case. One new 304/256 grid per case resolves all 12 mesh failures,
with maximum changes of 0.0634–0.0837%. Earlier grid failures remain recorded.
The added grid has 4,089/8,640 qualified matches and is reported separately from
the registered three-grid denominator. No completed coarse solve was repeated.

| Original case (lb / load split) | Initial Z median error | Initial twist median error | Final failed Z median error | Final failed twist median error | Final failed Mc median error | Maximum last mesh change |
|---|---:|---:|---:|---:|---:|---:|
| 20lb / 80 / 20 | 0.00386% | 0.00552% | 0.384% | 0.262% | 0.949% | 0.0634% |
| 20lb / 90 / 10 | 0.00559% | 0.00724% | 0.329% | 0.266% | 0.635% | 0.0836% |
| 30lb / 80 / 20 | 0.00222% | 0.00504% | 0.349% | 0.248% | 0.876% | 0.0639% |
| 30lb / 90 / 10 | 0.00266% | 0.00300% | 0.295% | 0.248% | 0.583% | 0.0837% |

Initial errors use all nonzero references; final errors use failed nonzero
references. Tiny/zero references retain their absolute printed-precision rules.
These percentages describe errors, not a new acceptance tolerance. Initial total
force and origin-moment checks pass 8/8; the 152/128 results pass 0/8 at original
printed precision. Refinement moves away from the archived solution while the
current discretization converges. This supports a historical finite-grid
contribution; it does not identify the original nodes or executable behavior.

The source models retain their 25-point elliptical Dmg tables, literal 80/20 and
90/10 multipliers at 20 and 30 lb, both beams' mg multiplier 1.1699, zero flow and
frame motion, and rigid joints with omitted KJtype. No filename-based force
normalization is applied. All 80 output rows and 27 fields are retained per grid.
Source arithmetic checks pass 502/504. Each 20 lb target has one printed root
weight discrepancy of about 5.2e-7 against the unchanged half-place limit 5e-7;
both failures remain in the decoded target rather than being rounded away.

The ordinary runner now registers **16 distinct ST-5 static snapshots** with
96,552 required slots, plus ST-3 for **17 structural jobs / 97,632 slots**.
All 66 focused adapter/summary tests pass. The new four runner jobs are terminal
and computed; command exit 1 correctly retains reference and initial mesh failures.
The twelve ordinary solve calls take 48.11 s; the complete command takes 179.10 s.
Four additional refinement children take 18.76–28.76 s each including recovery.
Jobs run serially with one BLAS thread and 180 s / 512 MiB limits.

A verified inventory maps all **24 complete original .asw/.sh/.txt triples** to
these 16 numerical cases: seven duplicate copies are byte-identical; one other
copy differs by a single extra space in the model while its driver and output
are identical. No duplicate copy creates an independent comparison. The other
14 of 38 model files lack a complete matching-name triple. Modal outputs and
other names/extensions still require source review; this is coverage accounting,
not proof that those models have no possible targets.

Historical node/exporter precision, reaction display, roller/forward-only mesh
failures, unpaired/modal models and complete family validation remain open.
This is CPython evidence; no new browser replay or app/package build is claimed.

Evidence: [three-grid assessment](../../artifacts/isae/st5-elliptical-20261103/assessment.json),
[refinement assessment](../../artifacts/isae/st5-elliptical-20261103/refinement/assessment.json),
[independent summary](../../artifacts/isae/st5-elliptical-20261103/summary/summary.json),
[source coverage map](../../artifacts/isae/st5-elliptical-20261103/static-triplet-coverage.json),
and [ordinary runner plan](../../artifacts/isae/st5-elliptical-20261103/run/plan.json).
