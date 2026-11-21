# AE-2: all three 10° sweeps complete

Observed 2026-11-11 UTC. AE-2 advances from **1,324/2,200 to 1,652/2,200**
at the existing 5% tolerance. The negative- and positive-coupling wings add
**328 passing comparisons**, with no new mismatches or failed numerical jobs.
All **488 available values** across the three 10° sweeps now pass.
Production equations, defaults, model bytes, reference values and numerical
gates are unchanged.

## Agreement with archived ASWING

These are the original three composite models, the literal `!B 10` commands
for the vertical wings, all archived finite speeds, four sensor channels and
both nominal 80/160 meshes. The quantities are exported Earth Y, heading,
sensor speed and local flow angle. No experimental curve replaces the native
ASWING target.

| Layup | IAS range, m/s | Passes / required values | Median error | Maximum error | Maximum deflection/heading mesh change |
|---|---:|---:|---:|---:|---:|
| Uncoupled `[03_90]` | 1–20 | 160/168 | 0.16670% | 2.68729% | 0.01266% |
| Negative coupling `[m15_02]_S` | 1–15 | 120/128 | 1.34059% | 3.40459% | 0.01205% |
| Positive coupling `[p15_02]_S` | 1–26 | 208/216 | 0.21777% | 2.40041% | 0.04064% |
| All 10° sweeps | — | **488/512** | **0.21560%** | **3.40459%** | **0.04064%** |

Each layup retains eight unavailable original zero-speed values. These
subsets belong to the existing primary AE-2 scope and are not independently
added to progress totals. The two newly completed coupled sweeps have combined
median/max error **0.25929% / 3.40459%**.

![Complete AE-2 10-degree comparison with archived ASWING](../../artifacts/isae/ae2-beta10-sweeps-current-20261110/complete-review/beta10.png)

The agreement covers both signs of bending–torsion coupling. Jan's
**Part IV §3.2, pp. 8–12**, describes increasing tip incidence for negative
coupling and reducing it for positive coupling. Both original models reproduce
the archived trends here. This does not resolve the earlier 1°/5° discrepancies
or establish agreement with experiment beyond ASWING's documented limitations.

## Numerical and execution checks

All **82 new cold solves** finish successfully and pass **1,476 physical
checks**, including a fresh full residual, force/moment balance, clamp and
sensor reconstruction checks. All **41 new mesh pairs** pass. The largest new
fresh residual is **9.95512e−13**, below the unchanged 1e−12 gate.

Jobs ran serially with one BLAS thread, 512 MiB address space, 15 CPU seconds
and a 25-second wall deadline. Maximum CPU use was **10.81 seconds**. All 82
children were reaped; no new retry was needed. The four coupled zero-speed
records were classified without numerical processes, retaining sixteen
unavailable values.

All **128 original 10° records** now have terminal outcomes. The earlier
uncoupled 1 m/s timeout remains immutable, and its already-declared successful
retry still contributes to the same original slot once. The final report
reconciles that retry against the complete original snapshot; it does not pool
the earlier partial report with the new one.

The full saved-file audit rehashes **3,575 files** and freshly checks **3,639
path mappings** before publication. An initial metadata-only audit was killed
before final publication; the exact signal cause was not recorded. Its partial
files and exit record remain retained. The complete rerun used **40.45 CPU
seconds / 116.54 wall seconds** under a **45-CPU-second, 240-wall-second,
512-MiB metadata limit**. It imported no production solver and made no physics
calls. Numerical worker limits and acceptance gates did not change.

## Full AE-2 accounting

| Literal beta | Passes / required | Computed mismatches | Unresolved execution outputs | Finite unrun values | Unavailable references |
|---:|---:|---:|---:|---:|---:|
| 1° | 616/648 | 4 | 4 | 0 | 24 |
| 5° | 548/600 | 12 | 16 | 0 | 24 |
| 10° | 488/512 | 0 | 0 | 0 | 24 |
| 15° | 0/440 | 0 | 0 | 416 | 24 |
| Total | **1,652/2,200** | **16** | **20** | **416** | **96** |

The **417 accepted states / 1,668 computed values** pass **7,506 physical
checks** and **207 mesh pairs**. Maximum mesh change remains **0.04079%**;
maximum fresh residual remains **9.99455e−13**. All **1,340 earlier comparison
records are exactly unchanged**.

The twelve negative-coupling 5° failures retain median error **249.161%**,
range **227.303–356.704%**. The four negative-coupling 1°/16 m/s failures
retain median **12.2094%**, range **8.6983–15.7294%**. Five unresolved mesh
conditions retain twenty outputs. No earlier discrepancy is removed by this
coverage increase, and AE-2 remains open as a whole family.

Next: all three 15° sweeps, comprising 104 finite numerical conditions and
six unavailable zero-speed records. Keep the earlier branch/deformation
discrepancies and unfinished solves open. Browser/build checks remain held.
Exact historical startup settings and executable provenance remain unresolved;
see the [authoritative reference index](aswing-authoritative-references.md).

Evidence: [full audit](../../artifacts/isae/ae2-beta10-sweeps-current-20261110/complete-review/assessment-extended.json),
[summary](../../artifacts/isae/ae2-beta10-sweeps-current-20261110/complete-review/summary.json),
[original source review](../../artifacts/isae/ae2-beta10-sweeps-current-20261110/source-review.json),
[new execution receipts](../../artifacts/isae/ae2-beta10-sweeps-current-20261110/complete-review/attempts.json),
[complete original snapshot](../../artifacts/isae/ae2-beta10-sweeps-current-20261110/snapshot-0128/report.json),
[accepted report](../../artifacts/isae/ae2-beta10-sweeps-current-20261110/complete-review/accepted-run/report.json).
