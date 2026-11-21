# FFWT-4 quarter-step comparison

The independently initialized quarter-step run passes **200/200** native
Fixed-1 root-moment comparisons at 5%. Median/max error is **0.523%/0.679%**.
All **796 steps** through 2.9651 s converge without rejection, with maximum
residual **9.817e-9**. Forty small serial jobs finish with exit code 0; none
times out. The fixed-wing scope remains **200/1,600 distinct targets**.

The next time refinement reduces the discrepancy, but strict root-moment
accuracy still passes only **1/2** gates. The gust-induced increment changes
**0.113288%**, just above the unchanged **0.1%** limit. Time accuracy is not
yet established; the earlier failed comparison remains part of the record.

| Half-step versus quarter-step quantity | Maximum change | Change / quarter-step scale | 0.1% gate |
|---|---:|---:|---|
| Total root moment, all 399 shared ticks | 0.000454457 N m | 0.039956% | Pass |
| Increment from t=0, all 399 shared ticks | 0.000454457 N m | 0.113288% | Fail |
| Increment from t=0, original 200 native ticks | 0.000442581 N m | 0.110328% | Fail |

The worst all-shared-tick difference occurs at **1.72095 s**, after gust exit,
between the original archive timestamps. The original 200-tick check still
fails independently; including the other shared ticks does not cause the
failure by itself. RMS increment difference is 0.041945% of the fine-grid
increment scale, but acceptance uses the maximum, not RMS.

The previous native-grid-to-half-step increment change was 0.181851%.
At the same 200 native ticks, its maximum absolute difference is 1.649 times
the next refinement's difference. This reduction is evidence of progress;
it is not a measured asymptotic order or an extrapolated solution.

![Three grids and their successive differences](../../artifacts/isae/ffwt4-refinement-20261106/plots-adjacent-d2-d4/comparison.png)

## Unchanged setup and independent audit

The three steps are 0.0149, 0.00745 and **0.003725 s**. Every history starts
independently from the same equilibrium. The literal physical model, gust,
nominal32 mesh, aerodynamic flags, equations and residual tolerance remain
unchanged. The BDF2 predecessor is retained across job boundaries; only the
first physical step uses BDF1. There is no phase alignment, fitted amplitude,
interpolation between samples or reuse of a coarser transient as the finer
initial condition.

The existing saved-history assessor audits all 797 quarter-grid states and
all source, request, result and checkpoint hashes. The new adjacent-grid
assessor verifies both completed assessment records and their input hashes,
checks the same initial model/equations, and compares exact common ticks.
Both the original 200-tick gates and the additional 399-tick gates must pass
for a quantity to pass the combined accuracy check. Seven targeted tests
cover missing states, nonfinite interleaved values, changed times, wrong grid
ratios and an error deliberately placed between archived timestamps.

These checks concern the archived root moment. They do not certify every
state variable, spatial convergence, the other seven fixed histories or the
hinged configurations. The declared numerical/default-setting qualifications
in the [initial study](isae-ffwt4-initial-20261106.md) remain applicable.

## Execution and retained evidence

Each job uses one BLAS thread, at most 20 steps, a 60-second process cap and
a 512 MiB address-space cap. Summed reported segment time is **1,134.68 s**
(18.9 minutes), including serialization and final evidence hashing. This is
not a controlled performance comparison or end-to-end elapsed time.

Sampled 20-step segments at steps 200 and 400 each build one Newton Jacobian
and perform 40 Newton iterations; the segment ending at 780 builds two and
performs 20 iterations. Matrix reuse is already active. These counters do
not identify the dominant runtime cost without profiling.

Evidence under `artifacts/isae/ffwt4-refinement-20261106/`:

- `assessment-d4-s796.json`: full quarter-grid audit and native comparisons.
- `assessment-adjacent-d2-d4.json`: both common-grid accuracy comparisons.
- `serial-terminal-d4.json`: all 40 observed successful process exits.
- `d4-s020` through `d4-s796`: complete requests, states, checkpoints and reports.
- `plots-adjacent-d2-d4/comparison.png` and `.svg`: original/half/quarter plots.

The [half-step study](isae-ffwt4-refinement-20261106.md), its timeout/retry
evidence and its original 1/2 accuracy result are preserved. Further time
refinement, spatial accuracy, broader reference coverage and shared-suite
registration remain open. No solver equation or physical parameter changed.
