# AE-2: all registered sensor sweeps attempted

Observed 2026-11-11 UTC. AE-2 advances from **1,652/2,200 to 2,068/2,200**
at the existing 5% tolerance. All **416 available comparisons** in the three
15° sweeps pass. All **550 registered sensor records**, covering twelve sweeps,
now have terminal outcomes; **no finite sensor reference remains unrun**.
Production equations, defaults, original inputs and numerical gates are
unchanged. AE-2 remains open because earlier discrepancies, incomplete solves
and supplemental output coverage still need work.

## Agreement at 15°

The original vertical-wing models and drivers command literal `!B 15`.
Every archived finite speed was tested on nominal 80/160 meshes against the
four original exported channels: Earth Y, heading, sensor speed and local flow
angle. The target is the archived ASWING output, distinct from experiment.

| Layup | IAS range, m/s | Passes / required values | Median error | Maximum error | Maximum deflection/heading mesh change |
|---|---:|---:|---:|---:|---:|
| Uncoupled `[03_90]` | 1–17 | 136/144 | 1.69622% | 2.54920% | 0.01102% |
| Negative coupling `[m15_02]_S` | 1–14 | 112/120 | 2.43279% | 3.23281% | 0.01159% |
| Positive coupling `[p15_02]_S` | 1–21 | 168/176 | 1.25098% | 2.43611% | 0.03967% |
| All 15° sweeps | — | **416/440** | **1.67674%** | **3.23281%** | **0.03967%** |

Each layup retains eight unavailable original zero-speed values. These
subsets belong to the primary AE-2 total and are not added as independent
progress scopes.

![Complete AE-2 15-degree comparison with archived ASWING](../../artifacts/isae/ae2-beta15-sweeps-current-20261111/complete-review/beta15.png)

Jan's **Part IV §3.2, pp. 8–12**, describes the original composite properties,
symmetry-plane setup and ASWING's stall limitations. Agreement here supports
the stated native comparison; it does not remove those experimental-model
limitations or establish the unlogged historical startup settings.

## Numerical checks and execution

All **104 new cold solves** finish successfully and pass **1,872 physical
checks**, including a freshly rebuilt full residual, force/moment balance,
clamp and sensor reconstruction checks. All **52 new mesh pairs** pass. The
largest new fresh residual is **9.89044e−13**, below the unchanged 1e−12 gate.

Jobs ran serially with one BLAS thread, 512 MiB address space, 15 CPU seconds
and a 25-second wall deadline. Maximum CPU use was **8.31 seconds**. All 104
children were reaped; no retry or parameter adjustment was needed. Six
zero-speed records were classified without numerical processes, retaining
their 24 unavailable values. All 110 original 15° records are terminal.

The complete saved-file audit rehashes **4,927 files** and freshly checks
**4,995 path mappings** before publication. It finishes in **57.19 CPU
seconds / 242.77 wall seconds**, using 214,080 KiB peak RSS, under a
90-CPU-second, 360-wall-second, 512-MiB metadata limit. It imports no production
solver and makes no physics calls. The numerical worker limits and physical
acceptance gates remain unchanged.

## Complete registered sensor accounting

| Literal beta | Passes / required | Computed mismatches | Unresolved execution outputs | Finite unrun values | Unavailable references |
|---:|---:|---:|---:|---:|---:|
| 1° | 616/648 | 4 | 4 | 0 | 24 |
| 5° | 548/600 | 12 | 16 | 0 | 24 |
| 10° | 488/512 | 0 | 0 | 0 | 24 |
| 15° | 416/440 | 0 | 0 | 0 | 24 |
| Total | **2,068/2,200** | **16** | **20** | **0** | **96** |

The **521 accepted states / 2,084 computed values** pass **9,378 physical
checks** and **259 mesh pairs**. Maximum mesh change remains **0.04079%**;
maximum fresh residual remains **9.99455e−13**. All **1,668 earlier comparison
records are exactly unchanged**. Original failures, declared retries and
audited continuations remain retained; each comparison slot contributes once.

## Remaining work

The twelve negative-coupling 5° failures retain median error **249.161%**,
range **227.303–356.704%**. The four negative-coupling 1°/16 m/s failures
retain median **12.2094%**, range **8.6983–15.7294%**. These are unchanged
deformation/branch discrepancies, not failures introduced by the 15° sweep.

Five negatively coupled conditions still lack a complete accepted state:

| Literal beta | IAS, m/s | Unresolved nominal mesh |
|---:|---:|---:|
| 1° | 18 | 160 |
| 5° | 18 | 160 |
| 5° | 19 | 160 |
| 5° | 20 | 80 and 160 |

Their twenty sensor outputs remain unresolved. Completing these solves and
investigating the sixteen native mismatches are separate tasks; a converged
state does not automatically match the archived branch.

The registered adapter still excludes supplemental span exports and an
additional model missing its `End` record. The existing
[coverage backlog](isae-suite-backlog.md) calls for binding the original span
exports to their generating models and commands, starting with the negative-
coupling A15 distribution and its `ww` command. Completing the sensor sweeps
does not establish that broader coverage. The 96 unavailable sensor references
also remain in their declared denominators.

Next: bounded completion of the five unresolved conditions and source binding
for the supplemental span outputs, while preserving the existing sensor
results. Browser/build checks remain held. Exact historical startup settings
and executable provenance remain unresolved; see the
[authoritative reference index](aswing-authoritative-references.md).

Evidence: [full audit](../../artifacts/isae/ae2-beta15-sweeps-current-20261111/complete-review/assessment.json),
[summary](../../artifacts/isae/ae2-beta15-sweeps-current-20261111/complete-review/summary.json),
[source review](../../artifacts/isae/ae2-beta15-sweeps-current-20261111/source-review.json),
[execution receipts](../../artifacts/isae/ae2-beta15-sweeps-current-20261111/complete-review/attempts.json),
[complete original snapshot](../../artifacts/isae/ae2-beta15-sweeps-current-20261111/snapshot-0110/report.json).
