# ST-1: first unchanged structural comparison and complete native target inventory

The original static `[45_0]_3a.asw` now solves without editing its input. Both
declared meshes complete and pass all **52 physical checks**. The 100-interval
calculation matches two of its three archived coordinates; the 200-interval
calculation matches none at the original printed precision. Neither is a complete
snapshot match, and ST-1 remains unfinished.

The complete **37-job batch finishes in 56.53 seconds**: two computed states and
35 blocked/inventory records. All **200 required scalar slots** are accounted for:
six numerically valid values, two printed-precision matches, 194 unavailable and
zero missing. The two matches are distinct X/Y cells on one mesh, not a family
pass. Worker times including imports are 11.49 and 11.54 seconds; each performs
one cold solve and one fresh residual after restoring the saved state. Both
processes are reaped, with zero retries.

| Body-anchor coordinate (m) | Archived ASWING | 100 nominal intervals | 200 nominal intervals | Printed tolerance |
|---|---:|---:|---:|---:|
| rx | −0.129671 | −0.129671038510 | −0.129679125110 | 0.0000005 |
| ry | −0.189497 | −0.189496845695 | −0.189493515411 | 0.0000005 |
| rz | −0.0949139 | −0.094914981735 | −0.094926270241 | 0.00000005 |

The coarse Z difference is 1.0817 micrometres. Fine-grid differences are 8.1251,
3.4846 and 12.3702 micrometres in X/Y/Z. Refinement moves this calculation away
from the finite-grid archive; the coarse grid is not selected as a preferred
result. Both grids and every discrepancy remain reported. Their differences do
not establish historical node identity or a new mesh-acceptance threshold.
The [CSV](isae-suite-st1-20261027.csv) retains all six predictions and original
decimal targets/tolerances.

The source section operator (`drela-steady-section-v1`) and source beam splines
(`drela-segspl-v1`) preserve the literal 0.4 kg tip mass at −0.28, gravity constant
9.81, zero distributed weight, clamp at +0.28, nonuniform twist, general-section
properties and sensor at −0.22. Body gravity [0,0,−9.81], no FlightCondition and
zero added loads are explicit current choices. The mandatory sensor station
produces 101/201 actual intervals and 102/202 nodes. The original driver requests
I100; the primary report says forty nodes. Neither recovers the actual historical
array, startup airflow, gravity direction or continuation.

The [sensor capability correction](source-sensor-availability-20261027.md)
retains position and other independent measurements despite the original parallel
sensor direction vectors. Undefined full-triad measurements remain null, with
diagnostics. No axis substitution, relocation, baseline subtraction, absolute
value, End insertion, scaler truncation or mass correction is made. The comparison
uses lowercase beam-anchor body positions, as identified by the original export.

| Retained native scope | Distinct targets | Required slots | Numerically valid slots |
|---|---:|---:|---:|
| One paired static position row on two meshes | 3 | 6 | 6 |
| Other native position rows | 42 | 42 | 0 |
| All 76 complex roots, real and imaginary parts | 152 | 152 | 0 |
| **Total** | **197** | **200** | **6** |

All 27 native files and 91 rows remain required, including 25 real-only roots.
Nine other original models remain explicit inventory records; their grammar and
setup errors are unresolved. The ten-model inventory also retains all 61 output
candidates. Additional embedded arrays, sweep groups and undecoded plots are
outside this native-scalar denominator and remain work. The supplemental mesh
tree duplicates 129 stored values and adds no independent targets.

Verification includes 387 adapter/integration/catalog tests and 39 construction
checks before execution. The sensor capability separately passes 182 Python and
70 JavaScript tests and an offline native/WASM fixture comparison. The archived
ST-1 equilibria themselves are native runs; that fixture is not a browser replay
of these loaded states. The new batch keeps its kernel separate from earlier
AE-1, AE-3 and AP-2 reports.

The [independent summary](../../artifacts/isae/st1-summary-20261027/summary.json)
revalidates every declared target and precision rule without a solver. The
[raw batch](../../artifacts/isae/st1-20261027/report.json),
[machine report](isae-suite-st1-20261027.json) and
[independent saved-result audit](isae-suite-st1-20261027/independent-audit.json)
retain source/code hashes and execution evidence. The runner exits 1 because
reference differences and unsupported scopes remain.

The [new full default plan](../../artifacts/isae/default-plan-st1-20261027/plan.json)
has **15 adapters, 4,029 jobs and 65,986 slots** across selected scopes in
25 of 41 families. Twenty-three families have an executable scope; 16 still lack
adapters. All 279 original hashes verify, 212 models import losslessly and 67
retain explicit import errors. These are coverage counts, not validation rates.
No whole family or full ASWING implementation is declared complete.
